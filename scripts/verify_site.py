#!/usr/bin/env python3
"""Validate the static site before deployment.

Checks:
- required files exist
- no root-absolute asset URLs
- internal relative links resolve to files under site/
- each HTML page has title, description, canonical, hreflang, and Open Graph basics
- robots.txt and sitemap.xml list the public canonical URLs
- the home pages link a Windows .exe and a macOS .dmg, and every download link responds
- pages use no scripts except JSON-LD, the JSON-LD parses, and content images have alt text
- the generated files match copy/ (scripts/build_pages.py --check)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.parse import unquote
from urllib.request import Request, urlopen

SITE = Path(__file__).resolve().parents[1] / "site"
PUBLIC_ORIGIN = "https://aoraw.org"
CANONICAL_PAGES = (
    f"{PUBLIC_ORIGIN}/",
    f"{PUBLIC_ORIGIN}/features/",
    f"{PUBLIC_ORIGIN}/zh-cn/",
    f"{PUBLIC_ORIGIN}/zh-cn/features/",
)

REQUIRED_FILES = (
    "index.html",
    "features/index.html",
    "zh-cn/index.html",
    "zh-cn/features/index.html",
    "404.html",
    "robots.txt",
    "sitemap.xml",
    "llms.txt",
    "llms-full.txt",
    "zh-cn/llms-full.txt",
    ".nojekyll",
    "assets/site.css",
    "assets/social-card.png",
    "assets/social-card-zh.png",
    "assets/icon-32.png",
    "assets/icon-180.png",
    "assets/icon-512.png",
    "assets/shots/home-en-1920.webp",
    "assets/shots/home-en-2560.avif",
)
HOME_PAGES = ("index.html", "zh-cn/index.html")

errors: list[str] = []
warnings: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def check_required_files() -> None:
    for rel in REQUIRED_FILES:
        if not (SITE / rel).is_file():
            err(f"missing required file: {rel}")


def check_robots_and_sitemap() -> None:
    robots = (SITE / "robots.txt").read_text(encoding="utf-8")
    if f"Sitemap: {PUBLIC_ORIGIN}/sitemap.xml" not in robots:
        err("robots.txt must point to the public sitemap URL")
    if "Allow: /" not in robots:
        err("robots.txt must allow crawling")

    sitemap = (SITE / "sitemap.xml").read_text(encoding="utf-8")
    for url in CANONICAL_PAGES:
        if f"<loc>{url}</loc>" not in sitemap:
            err(f"sitemap.xml missing canonical URL: {url}")


DOWNLOAD_HOST = "https://static.aoraw.org/"


def check_download_links() -> None:
    """Download links are maintained by hand in scripts/build_pages.py; make sure they work."""
    links: set[str] = set()
    for rel in HOME_PAGES:
        found = [u for u in HREF_SRC_RE.findall((SITE / rel).read_text(encoding="utf-8")) if u.startswith(DOWNLOAD_HOST)]
        if not any(u.endswith(".exe") for u in found):
            err(f"{rel}: no Windows .exe download link")
        if not any(u.endswith(".dmg") for u in found):
            err(f"{rel}: no macOS .dmg download link")
        links.update(found)
    for url in sorted(links):
        request = Request(url, method="HEAD", headers={"User-Agent": "alcedo-site-verify"})
        try:
            with urlopen(request, timeout=20) as response:
                if response.status != 200:
                    err(f"download link returned {response.status}: {url}")
        except (OSError, URLError, TimeoutError) as exc:
            err(f"download link does not respond: {url} ({exc})")


def strip_query_fragment(href: str) -> str:
    return href.split("#", 1)[0].split("?", 1)[0]


def resolve_local(page: Path, href: str) -> Path | None:
    """Return expected filesystem path for a relative in-site link, or None if external/skip."""
    href = strip_query_fragment(href.strip())
    if not href or href.startswith(("http://", "https://", "mailto:", "data:", "javascript:")):
        return None
    if href.startswith("//"):
        return None
    if href.startswith("/"):
        if page.name == "404.html":
            return SITE / unquote(href.lstrip("/"))
        err(f"{page.relative_to(SITE)}: root-absolute path is not portable: {href}")
        return None

    target = (page.parent / unquote(href)).resolve()
    try:
        target.relative_to(SITE.resolve())
    except ValueError:
        err(f"{page.relative_to(SITE)}: link escapes site root: {href}")
        return None
    return target


def path_exists_for_url(target: Path) -> bool:
    if target.is_file():
        return True
    # Directory URL → index.html
    if target.is_dir() and (target / "index.html").is_file():
        return True
    # href without trailing slash that maps to a directory
    if not target.suffix and (target / "index.html").is_file():
        return True
    if not target.suffix and target.with_suffix(".html").is_file():
        return True
    return False


HREF_SRC_RE = re.compile(
    r"""(?:href|src)\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE,
)
SRCSET_RE = re.compile(r"""srcset\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
CSS_URL_RE = re.compile(r"""url\(\s*['"]?([^'")]+)['"]?\s*\)""", re.IGNORECASE)


def check_html_page(page: Path) -> None:
    rel = page.relative_to(SITE).as_posix()
    text = page.read_text(encoding="utf-8")

    # 404.html is served for missing paths at any depth, so it uses root-relative URLs.
    if rel != "404.html" and re.search(r"""(?:href|src)\s*=\s*["']/(?!/)""", text):
        err(f"{rel}: contains root-absolute href/src")

    # SEO requirements for content pages (not 404)
    if page.name != "404.html":
        if "<title>" not in text:
            err(f"{rel}: missing <title>")
        if 'name="description"' not in text:
            err(f"{rel}: missing meta description")
        if 'rel="canonical"' not in text:
            err(f"{rel}: missing canonical")
        for hreflang in ("en", "zh-CN", "x-default"):
            if f'hreflang="{hreflang}"' not in text:
                err(f"{rel}: missing hreflang {hreflang}")
        for prop in ("og:title", "og:description", "og:type", "og:url", "og:image"):
            if f'property="{prop}"' not in text and f"property='{prop}'" not in text:
                err(f"{rel}: missing Open Graph {prop}")
        if 'name="twitter:card"' not in text:
            err(f"{rel}: missing twitter:card")
        # Canonical must use public origin
        m = re.search(r'rel="canonical"\s+href="([^"]+)"', text)
        if m and not m.group(1).startswith(PUBLIC_ORIGIN):
            err(f"{rel}: canonical not under public origin: {m.group(1)}")

    # No scripts: the site is HTML and CSS only. JSON-LD blocks must parse.
    for m in re.finditer(r"<script([^>]*)>(.*?)</script>", text, re.S):
        if 'type="application/ld+json"' not in m.group(1):
            err(f"{rel}: contains a script; the site uses HTML and CSS only")
            continue
        try:
            json.loads(m.group(2))
        except json.JSONDecodeError as exc:
            err(f"{rel}: JSON-LD does not parse: {exc}")

    # Screenshots need a description; only decorative logos may have alt="".
    for m in re.finditer(r"<img[^>]*>", text):
        tag = m.group(0)
        alt = re.search(r'alt="([^"]*)"', tag)
        if alt is None:
            err(f"{rel}: <img> without alt: {tag[:80]}")
        elif not alt.group(1) and "/shots/" in tag:
            err(f"{rel}: screenshot without alt text: {tag[:80]}")

    if "待确认" in text:
        err(f"{rel}: contains an unconfirmed fact marker")

    # Home pages need SoftwareApplication JSON-LD
    if rel in ("index.html", "zh-cn/index.html"):
        if "SoftwareApplication" not in text:
            err(f"{rel}: missing SoftwareApplication JSON-LD")

    for m in HREF_SRC_RE.finditer(text):
        href = m.group(1)
        target = resolve_local(page, href)
        if target is None:
            continue
        if not path_exists_for_url(target):
            # allow pure fragment already stripped; empty after strip means same page
            if strip_query_fragment(href) == "":
                continue
            err(f"{rel}: broken local link -> {href}")

    for m in SRCSET_RE.finditer(text):
        for part in m.group(1).split(","):
            file_part = part.strip().split()[0] if part.strip() else ""
            if not file_part:
                continue
            target = resolve_local(page, file_part)
            if target is not None and not target.is_file():
                err(f"{rel}: broken srcset asset -> {file_part}")


def check_css() -> None:
    css_path = SITE / "assets" / "site.css"
    if not css_path.is_file():
        return
    text = css_path.read_text(encoding="utf-8")
    for m in CSS_URL_RE.finditer(text):
        url = m.group(1).strip()
        if url.startswith(("data:", "http://", "https://")):
            continue
        if url.startswith("/"):
            err(f"site.css: root-absolute url() is not portable: {url}")


def check_generated() -> None:
    script = Path(__file__).resolve().parent / "build_pages.py"
    result = subprocess.run([sys.executable, str(script), "--check"], capture_output=True, text=True)
    if result.returncode != 0:
        err((result.stdout + result.stderr).strip() or "build_pages.py --check failed")


def main() -> int:
    if not SITE.is_dir():
        print(f"ERROR: site directory missing: {SITE}", file=sys.stderr)
        return 1

    check_required_files()
    check_generated()
    check_robots_and_sitemap()
    check_download_links()
    check_css()

    for page in sorted(SITE.rglob("*.html")):
        check_html_page(page)

    for w in warnings:
        print(f"WARNING: {w}")
    if errors:
        print(f"verify_site: {len(errors)} error(s)")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"verify_site: OK ({len(list(SITE.rglob('*.html')))} HTML pages)")
    print(f"  public origin: {PUBLIC_ORIGIN}")
    print(f"  deploy root:   {SITE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
