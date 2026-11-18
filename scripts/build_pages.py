#!/usr/bin/env python3
"""Generate the site's HTML pages from the reviewed copy.

Usage:
    python scripts/build_pages.py           write the pages into site/
    python scripts/build_pages.py --check   exit 1 if site/ differs from the copy

Inputs: copy/en.md and copy/zh-CN.md (the text, reviewed by the maintainer)
and the screenshots in site/assets/shots (made by scripts/build_images.py).
Outputs: the four pages, 404.html, sitemap.xml, llms.txt, llms-full.txt, and
zh-cn/llms-full.txt. The generated files are committed; do not edit them by hand.
"""

from __future__ import annotations

import html
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
COPY = ROOT / "copy"
ORIGIN = "https://aoraw.org"

# Update these together for each release (and the date in home.release in copy/*.md).
VERSION = "0.3.6"
RELEASE_DATE = "2026-11-17"
UPDATED = "2026-11-17"  # sitemap lastmod
BUILDS = "https://static.aoraw.org/updates/v1/stable/builds/3009"
DOWNLOAD = {
    "windows": f"{BUILDS}/windows-x86_64/AlcedoStudio-0.3.6-Windows-AMD64.exe",
    "mac": f"{BUILDS}/macos-arm64/AlcedoStudio-0.3.6-Darwin-arm64.dmg",
}
CHECKSUMS = {
    "windows": f"{BUILDS}/windows-x86_64/SHA256SUMS-windows-x86_64.txt",
    "mac": f"{BUILDS}/macos-arm64/SHA256SUMS-macos-arm64.txt",
}

REPO = "https://github.com/zidage/AlcedoStudio"
RELEASES = f"{REPO}/releases"
LICENSE = f"{REPO}/blob/main/LICENSE"
CLI_REFERENCE = "https://github.com/zidage/alcedo-skills/blob/main/skills/alcedo/references/README.md"

# Sections without a screenshot are plain text. The order of the sections comes from the copy.
SHOT_IDS = ("home", "top", "raw", "nodes", "tools", "masks", "film", "luts", "engine", "library", "search", "history", "export")
# Feature areas that go into the featureList of the structured data.
FEATURE_LIST_SKIP = {"app", "requirements", "components", "credits"}
WIDTHS = (1280, 1920, 2560)


@dataclass
class Section:
    id: str
    title: str
    lead: str = ""
    alt: str = ""
    rows: list[tuple[str, str | None, str]] = field(default_factory=list)


@dataclass
class Lang:
    code: str  # html lang
    tag: str  # screenshot tag
    prefix: str  # URL path prefix
    og_locale: str
    docs: str
    card: str
    strings: dict[str, str] = field(default_factory=dict)
    sections: list[Section] = field(default_factory=list)


LANGS = {
    "en": Lang("en", "en", "/", "en_US", "https://zidage.github.io/AlcedoStudio_docs/en/docs/intro", "social-card.png"),
    "zh-CN": Lang("zh-CN", "zh", "/zh-cn/", "zh_CN", "https://zidage.github.io/AlcedoStudio_docs/docs/intro", "social-card-zh.png"),
}
COPY_FILES = {"en": "en.md", "zh-CN": "zh-CN.md"}


# --------------------------------------------------------------------------- copy

def parse_copy(lang: Lang) -> None:
    path = COPY / COPY_FILES[lang.code]
    text = path.read_text(encoding="utf-8")
    if "待确认" in text.split("\n## ", 1)[1]:
        raise SystemExit(f"{path.name}: unconfirmed facts ([待确认]) must be resolved before building")
    current: Section | None = None
    for line in text.splitlines():
        if m := re.match(r"^### (\w+): (.+)$", line):
            current = Section(m[1], m[2])
            lang.sections.append(current)
        elif line.startswith("## "):
            current = None
        elif current and line.startswith("> "):
            current.alt = line[2:].strip()
        elif current and (m := re.match(r"^- \*\*(.+?)\*\*\s*(?:[(（](\d+\.\d+\.\d+)[)）])?\s*[:：]\s*(.+)$", line)):
            current.rows.append((m[1], m[2], m[3]))
        elif not current and (m := re.match(r"^- ([a-z][\w.]+): (.+)$", line)):
            lang.strings[m[1]] = m[2]
        elif current and line.strip() and not line.startswith("-") and not current.rows:
            current.lead = f"{current.lead} {line.strip()}".strip()


def fill(text: str) -> str:
    return text.replace("{version}", VERSION)


def inline(text: str) -> str:
    """Copy markup to HTML: `code` and [text](url)."""
    out = html.escape(fill(text), quote=False)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', out)


def plain(text: str) -> str:
    """Copy markup to plain text, for attributes and structured data."""
    out = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", fill(text))
    return out.replace("`", "")


def attr(text: str) -> str:
    return html.escape(plain(text), quote=True)


# --------------------------------------------------------------------------- pages

@dataclass
class Page:
    lang: Lang
    kind: str  # "home" or "features"

    @property
    def path(self) -> str:
        return self.lang.prefix + ("features/" if self.kind == "features" else "")

    @property
    def file(self) -> Path:
        return SITE / self.path.lstrip("/") / "index.html"

    @property
    def url(self) -> str:
        return ORIGIN + self.path

    def rel(self, target: str) -> str:
        """Relative URL from this page to a site path such as /assets/x.css or /zh-cn/."""
        depth = self.path.count("/") - 1
        return "../" * depth + target.lstrip("/") if target != "/" or depth else "./"

    def counterpart(self) -> "Page":
        other = LANGS["zh-CN" if self.lang.code == "en" else "en"]
        return Page(other, self.kind)


def shot_tag(shot: str, lang: Lang) -> str:
    for tag in (lang.tag, "en"):
        if (SITE / "assets" / "shots" / f"{shot}-{tag}-1920.webp").is_file():
            return tag
    raise SystemExit(f"missing screenshot: assets/shots/{shot}-en-*.avif (run scripts/build_images.py)")


def picture(page: Page, shot: str, alt: str, sizes: str, eager: bool = False) -> str:
    tag = shot_tag(shot, page.lang)
    base = f"/assets/shots/{shot}-{tag}"
    with Image.open(SITE / f"{base.lstrip('/')}-2560.avif") as im:
        width, height = im.size
    srcset = ", ".join(f"{page.rel(f'{base}-{w}.avif')} {w}w" for w in WIDTHS)
    loading = 'fetchpriority="high"' if eager else 'loading="lazy"'
    return (
        f'<picture><source type="image/avif" srcset="{srcset}" sizes="{sizes}">'
        f'<img src="{page.rel(f"{base}-1920.webp")}" width="{width}" height="{height}" alt="{attr(alt)}" {loading} decoding="async"></picture>'
    )


ICONS = {
    "download": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12m-5-5 5 5 5-5M4 20h16"/></svg>',
    "docs": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h6a2 2 0 0 1 2 2v13a2 2 0 0 0-2-2H4zM20 5h-6a2 2 0 0 0-2 2v13a2 2 0 0 1 2-2h6z"/></svg>',
    "source": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m8 7-5 5 5 5M16 7l5 5-5 5M14 4l-4 16"/></svg>',
}


def json_ld(data: dict) -> str:
    text = json.dumps(data, ensure_ascii=False, indent=2).replace("</", "<\\/")
    return f'<script type="application/ld+json">\n{text}\n</script>'


def structured_data(page: Page, title: str, description: str) -> str:
    lang, s = page.lang, page.lang.strings
    home = Page(lang, "home")
    app_id = f"{ORIGIN}/#software"
    website = {"@type": "WebSite", "@id": f"{ORIGIN}/#website", "name": "Alcedo Studio", "url": f"{ORIGIN}/",
               "inLanguage": ["en", "zh-CN"]}
    if page.kind == "home":
        features = [f"{plain(x.title)}: {plain(x.lead)}" for x in lang.sections if x.id not in FEATURE_LIST_SKIP]
        app = {
            "@type": "SoftwareApplication",
            "@id": app_id,
            "name": "Alcedo Studio",
            "description": plain(description),
            "url": home.url,
            "applicationCategory": "MultimediaApplication",
            "applicationSubCategory": plain(s["home.tagline"]),
            "operatingSystem": "Windows 10, Windows 11, macOS 13.3 or later (Apple Silicon)",
            "softwareVersion": VERSION,
            "datePublished": RELEASE_DATE,
            "downloadUrl": [DOWNLOAD["windows"], DOWNLOAD["mac"]],
            "releaseNotes": RELEASES,
            "softwareHelp": {"@type": "CreativeWork", "url": lang.docs},
            "license": "https://www.gnu.org/licenses/gpl-3.0.html",
            "isAccessibleForFree": True,
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
            "image": f"{ORIGIN}/assets/icon-512.png",
            "screenshot": f"{ORIGIN}/assets/shots/home-{shot_tag('home', lang)}-2560.avif",
            "featureList": features,
            "sameAs": [REPO],
            "inLanguage": lang.code,
        }
        code = {
            "@type": "SoftwareSourceCode",
            "name": "Alcedo Studio source code",
            "codeRepository": REPO,
            "programmingLanguage": ["C++", "QML"],
            "license": "https://www.gnu.org/licenses/gpl-3.0.html",
            "targetProduct": {"@id": app_id},
        }
        graph = [website, app, code]
    else:
        graph = [
            website,
            {"@type": "WebPage", "@id": page.url, "url": page.url, "name": plain(title), "description": plain(description),
             "inLanguage": lang.code, "about": {"@id": app_id}, "isPartOf": {"@id": f"{ORIGIN}/#website"}},
            {"@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Alcedo Studio", "item": home.url},
                {"@type": "ListItem", "position": 2, "name": plain(s["features.title"]), "item": page.url},
            ]},
        ]
    return json_ld({"@context": "https://schema.org", "@graph": graph})


def head(page: Page, title: str, description: str) -> str:
    lang = page.lang
    en, zh = Page(LANGS["en"], page.kind), Page(LANGS["zh-CN"], page.kind)
    other = page.counterpart()
    card = f"{ORIGIN}/assets/{lang.card}"
    t, d = attr(title), attr(description)
    return f"""<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<meta name="theme-color" content="#0d0e10">
<title>{t}</title>
<meta name="description" content="{d}">
<link rel="canonical" href="{page.url}">
<link rel="alternate" hreflang="en" href="{en.url}">
<link rel="alternate" hreflang="zh-CN" href="{zh.url}">
<link rel="alternate" hreflang="x-default" href="{en.url}">
<meta property="og:site_name" content="Alcedo Studio">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:type" content="website">
<meta property="og:url" content="{page.url}">
<meta property="og:image" content="{card}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="{lang.og_locale}">
<meta property="og:locale:alternate" content="{other.lang.og_locale}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{t}">
<meta name="twitter:description" content="{d}">
<meta name="twitter:image" content="{card}">
<link rel="icon" href="{page.rel('/assets/icon-32.png')}" type="image/png" sizes="32x32">
<link rel="apple-touch-icon" href="{page.rel('/assets/icon-180.png')}">
<link rel="alternate" type="text/plain" href="{page.rel('/llms.txt')}" title="llms.txt">
<link rel="stylesheet" href="{page.rel('/assets/site.css')}">
{structured_data(page, title, description)}
</head>"""


def header(page: Page) -> str:
    s = page.lang.strings
    home, features = Page(page.lang, "home"), Page(page.lang, "features")
    other = page.counterpart()
    current = lambda kind: ' aria-current="page"' if page.kind == kind else ""
    return f"""<a class="skip-link" href="#main">{inline(s["nav.skip"])}</a>
<header class="bar"><div class="bar__in">
<a class="brand" href="{page.rel(home.path)}"><img src="{page.rel('/assets/icon-180.png')}" width="30" height="30" alt="">Alcedo Studio</a>
<nav aria-label="{attr(s['nav.label'])}">
<a href="{page.rel(features.path)}"{current("features")}>{inline(s["nav.features"])}</a>
<a href="{page.lang.docs}">{inline(s["nav.docs"])}</a>
<a href="{REPO}">{inline(s["nav.source"])}</a>
<a href="{page.rel(other.path)}?lang={other.lang.code}" lang="{other.lang.code}" hreflang="{other.lang.code}">{inline(s["nav.language"])}</a>
<a class="bar__download" href="{page.rel(home.path)}#download">{inline(s["nav.download"])}</a>
</nav>
</div></header>"""


def footer(page: Page) -> str:
    s = page.lang.strings
    home, features = Page(page.lang, "home"), Page(page.lang, "features")
    other = page.counterpart()
    return f"""<footer class="foot">
<nav aria-label="{attr(s['footer.label'])}">
<a href="{page.rel(home.path)}">{inline(s["nav.home"])}</a>
<a href="{page.rel(features.path)}">{inline(s["nav.features"])}</a>
<a href="{page.lang.docs}">{inline(s["nav.docs"])}</a>
<a href="{REPO}">{inline(s["nav.source"])}</a>
<a href="{REPO}/issues">{inline(s["footer.issues"])}</a>
<a href="{LICENSE}">{inline(s["footer.license"])}</a>
<a href="{page.rel(features.path)}#credits">{inline(s["footer.credits"])}</a>
<a href="{page.rel(other.path)}?lang={other.lang.code}" lang="{other.lang.code}" hreflang="{other.lang.code}">{inline(s["nav.language"])}</a>
</nav>
<p>{inline(s["footer.background"])}</p>
<p>{inline(s["footer.copyright"])}</p>
</footer>"""


def document(page: Page, title: str, description: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="{page.lang.code}">
{head(page, title, description)}
<body>
{header(page)}
<main id="main">
{body}
</main>
{footer(page)}
</body>
</html>
"""


def home_page(page: Page) -> str:
    s = page.lang.strings
    t = lambda key: inline(s[key])
    features = Page(page.lang, "features")
    body = f"""<section class="hero">
<h1><img src="{page.rel('/assets/icon-180.png')}" width="68" height="68" alt="">Alcedo Studio</h1>
<p class="hero__tagline">{t("home.tagline")}</p>
<p class="hero__release">{t("home.release")} <a href="{RELEASES}">{t("home.release.notes")}</a></p>
<div class="actions" id="download">
<a class="action action--primary" href="{DOWNLOAD['windows']}">{ICONS["download"]}<span><b>{t("home.download.windows")}</b><small>{t("home.download.windows.note")}</small></span></a>
<a class="action action--primary" href="{DOWNLOAD['mac']}">{ICONS["download"]}<span><b>{t("home.download.mac")}</b><small>{t("home.download.mac.note")}</small></span></a>
<a class="action" href="{page.lang.docs}">{ICONS["docs"]}<span><b>{t("home.docs")}</b><small>{t("home.docs.note")}</small></span></a>
<a class="action" href="{REPO}">{ICONS["source"]}<span><b>{t("home.source")}</b><small>{t("home.source.note")}</small></span></a>
</div>
<p class="more"><span>{t("home.checksums")}: <a href="{CHECKSUMS['windows']}">Windows</a> · <a href="{CHECKSUMS['mac']}">macOS</a></span><a href="{RELEASES}">{t("home.older")}</a><a href="{page.rel(features.path)}">{t("home.features")}</a><a href="{CLI_REFERENCE}">{t("home.cli")}</a></p>
<figure class="shot">{picture(page, "home", s["home.screenshot.alt"], "(min-width: 1760px) 1712px, calc(100vw - 48px)", eager=True)}<figcaption>{t("home.screenshot.caption")}</figcaption></figure>
</section>"""
    return document(page, s["home.meta.title"], s["home.meta.description"], body)


SIZES = "(max-width: 960px) 100vw, 72vw"


def facts(section: Section) -> str:
    rows = "".join(
        f'<div><dt>{inline(term)}{f"<span class=since>{since}</span>" if since else ""}</dt><dd>{inline(text)}</dd></div>'
        for term, since, text in section.rows
    )
    return f'<dl class="facts">{rows}</dl>'


def section_head(section: Section) -> str:
    return (f'<h2 class="section-title">{inline(section.title)}<a href="#{section.id}" aria-label="#">#</a></h2>'
            f'<p class="lead">{inline(section.lead)}</p>')


def features_page(page: Page) -> str:
    s = page.lang.strings
    t = lambda key: inline(s[key])
    toc = "".join(f'<li><a href="#{x.id}">{inline(x.title)}</a></li>' for x in page.lang.sections)
    parts = [f"""<section class="split split--top">
<div class="split__text"><h1 class="page-title">{t("features.title")}</h1><p class="lead">{t("features.summary")}</p>
<nav class="toc" aria-labelledby="toc-title"><h2 id="toc-title">{t("features.contents")}</h2><ol>{toc}</ol></nav></div>
<div class="split__media">{picture(page, "top", s["features.image.alt"], SIZES, eager=True)}</div>
</section>"""]
    flip = True
    for section in page.lang.sections:
        if section.id in SHOT_IDS:
            if not section.alt:
                raise SystemExit(f"{COPY_FILES[page.lang.code]}: section {section.id} has a screenshot but no '> ' description")
            parts.append(
                f'<section class="split{" split--flip" if flip else ""}" id="{section.id}">'
                f'<div class="split__text">{section_head(section)}</div>'
                f'<div class="split__media">{picture(page, section.id, section.alt, SIZES)}</div>'
                f"{facts(section)}</section>")
            flip = not flip
        else:
            parts.append(f'<section class="plain" id="{section.id}">{section_head(section)}{facts(section)}</section>')
    title = s["features.meta.title"]
    return document(page, title, s["features.meta.description"], "\n".join(parts))


def not_found_page() -> str:
    en, zh = LANGS["en"].strings, LANGS["zh-CN"].strings
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<meta name="robots" content="noindex">
<title>{attr(en["notfound.title"])} | Alcedo Studio</title>
<!-- Root-relative URLs: this page is served for missing paths at any depth. -->
<link rel="icon" href="/assets/icon-32.png" type="image/png" sizes="32x32">
<link rel="stylesheet" href="/assets/site.css">
</head>
<body>
<header class="bar"><div class="bar__in"><a class="brand" href="/"><img src="/assets/icon-180.png" width="30" height="30" alt="">Alcedo Studio</a></div></header>
<main id="main" class="not-found">
<section><h1>{inline(en["notfound.title"])}</h1><p>{inline(en["notfound.text"])}</p>
<p><a href="/">{inline(en["nav.home"])}</a> · <a href="/features/">{inline(en["nav.features"])}</a></p></section>
<section lang="zh-CN"><h2>{inline(zh["notfound.title"])}</h2><p>{inline(zh["notfound.text"])}</p>
<p><a href="/zh-cn/">{inline(zh["nav.home"])}</a> · <a href="/zh-cn/features/">{inline(zh["nav.features"])}</a></p></section>
</main>
</body>
</html>
"""


# --------------------------------------------------------------------------- text files

def sitemap() -> str:
    urls = []
    for kind in ("home", "features"):
        for code in ("en", "zh-CN"):
            page = Page(LANGS[code], kind)
            links = "".join(
                f'\n    <xhtml:link rel="alternate" hreflang="{c}" href="{Page(LANGS[c], kind).url}"/>' for c in ("en", "zh-CN"))
            links += f'\n    <xhtml:link rel="alternate" hreflang="x-default" href="{Page(LANGS["en"], kind).url}"/>'
            urls.append(f"  <url>\n    <loc>{page.url}</loc>\n    <lastmod>{UPDATED}</lastmod>{links}\n  </url>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            + "\n".join(urls) + "\n</urlset>\n")


def features_markdown(lang: Lang) -> str:
    s = lang.strings
    out = [f"# {plain(s['features.meta.title'])}", "", plain(s["features.summary"]), "",
           f"Source: {Page(lang, 'features').url}", ""]
    for x in lang.sections:
        out += [f"## {fill(x.title)}", "", fill(x.lead), ""]
        out += [f"- **{fill(term)}**{f' ({since})' if since else ''}: {fill(text)}" for term, since, text in x.rows]
        out.append("")
    return "\n".join(out)


def llms_txt() -> str:
    s = LANGS["en"].strings
    return f"""# Alcedo Studio

> {plain(s["home.meta.description"])} Current version: {VERSION}, released on {RELEASE_DATE}. License: GPL-3.0.

Alcedo Studio runs on Windows 10 or 11 (x64; CUDA or OpenCL) and on Apple Silicon Macs with macOS 13.3 or later (Metal).

## Download

- [Windows installer]({DOWNLOAD['windows']}): Alcedo Studio {VERSION}, .exe
- [macOS installer]({DOWNLOAD['mac']}): Alcedo Studio {VERSION}, .dmg for Apple Silicon
- [SHA-256 checksums for Windows]({CHECKSUMS['windows']})
- [SHA-256 checksums for macOS]({CHECKSUMS['mac']})
- [Release notes and older versions]({RELEASES})

## Documentation

- [Feature list]({ORIGIN}/features/): all features of the current version
- [Feature list as Markdown]({ORIGIN}/llms-full.txt)
- [User guide]({LANGS['en'].docs})
- [alcedo-cli command reference]({CLI_REFERENCE}): commands for scripts and AI agents

## Source code

- [GitHub repository]({REPO})
- [License: GPL-3.0]({LICENSE})

## Optional

- [Chinese website]({ORIGIN}/zh-cn/)
- [Chinese feature list as Markdown]({ORIGIN}/zh-cn/llms-full.txt)
"""


# --------------------------------------------------------------------------- main

def outputs() -> dict[Path, str]:
    for lang in LANGS.values():
        parse_copy(lang)
    files: dict[Path, str] = {}
    for lang in LANGS.values():
        files[Page(lang, "home").file] = home_page(Page(lang, "home"))
        files[Page(lang, "features").file] = features_page(Page(lang, "features"))
    files[SITE / "404.html"] = not_found_page()
    files[SITE / "sitemap.xml"] = sitemap()
    files[SITE / "llms.txt"] = llms_txt()
    files[SITE / "llms-full.txt"] = features_markdown(LANGS["en"])
    files[SITE / "zh-cn" / "llms-full.txt"] = features_markdown(LANGS["zh-CN"])
    return files


def main() -> int:
    check = "--check" in sys.argv
    stale = []
    for path, text in outputs().items():
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current == text:
            continue
        if check:
            stale.append(path.relative_to(SITE).as_posix())
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
            print(f"wrote {path.relative_to(ROOT).as_posix()}")
    if stale:
        print("out of date with copy/ (run python scripts/build_pages.py): " + ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
