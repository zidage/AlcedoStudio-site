#!/usr/bin/env python3
"""Compress the raw screenshots and the logo into the files the site serves.

Usage:
    python scripts/build_images.py [NAME ...]

Sources live in ./screenshots (git-ignored):

    screenshots/site/<id>.en.png      editor screenshot with the English interface
    screenshots/site/<id>.zh-CN.png   the same screenshot with the Chinese interface
    screenshots/logo.png              the 1024 x 1024 application icon

Outputs go to site/assets:

    shots/<id>-<lang>-<width>.avif    1280, 1920, and 2560 px wide, for srcset
    shots/<id>-<lang>-1920.webp       fallback for browsers without AVIF
    icon-32.png, icon-180.png, icon-512.png
    social-card.png, social-card-zh.png

<id> is the section id in copy/*.md (plus "home" and "top"). When a Chinese
screenshot is missing, the Chinese pages use the English one. Give NAMEs
(shot ids, "icons", or "cards") to rebuild only those. Requires Pillow 11.3+
(built-in AVIF support). The social cards use the Windows fonts Segoe UI and
Microsoft YaHei.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "screenshots"
ASSETS = ROOT / "site" / "assets"
SHOTS = ASSETS / "shots"

WIDTHS = (1280, 1920, 2560)
FALLBACK_WIDTH = 1920
LANGS = {"en": "en", "zh-CN": "zh"}  # source suffix -> output tag
# Screenshot text is small, so the quality is higher than for photographs.
AVIF_QUALITY = 72
WEBP_QUALITY = 84

FONTS = Path("C:/Windows/Fonts")


def shot_ids() -> list[str]:
    ids = {p.name.split(".")[0] for p in (SOURCES / "site").glob("*.png")}
    return sorted(ids)


def resize(image: Image.Image, width: int) -> Image.Image:
    if image.width <= width:
        return image
    return image.resize((width, round(image.height * width / image.width)), Image.Resampling.LANCZOS)


def build_shot(shot: str) -> None:
    for suffix, tag in LANGS.items():
        source = SOURCES / "site" / f"{shot}.{suffix}.png"
        if not source.is_file():
            continue
        image = Image.open(source).convert("RGB")
        report = []
        for width in WIDTHS:
            out = SHOTS / f"{shot}-{tag}-{width}"
            resized = resize(image, width)
            resized.save(out.with_suffix(".avif"), "AVIF", quality=AVIF_QUALITY, speed=4)
            report.append(f"{width}: {out.with_suffix('.avif').stat().st_size // 1024} KB")
            if width == FALLBACK_WIDTH:
                resized.save(out.with_suffix(".webp"), "WEBP", quality=WEBP_QUALITY, method=6)
        print(f"{shot}-{tag}  " + ", ".join(report))


def build_icons() -> None:
    logo = Image.open(SOURCES / "logo.png").convert("RGBA")
    for size in (32, 180, 512):
        logo.resize((size, size), Image.Resampling.LANCZOS).save(ASSETS / f"icon-{size}.png", optimize=True)
    print("icons: 32, 180, 512")


def build_card(lang: str, out_name: str, title_font: str, text_font: str, tagline: str) -> None:
    width, height = 1200, 630
    card = Image.new("RGB", (width, height), (13, 14, 16))
    shot_source = SOURCES / "site" / f"home.{lang}.png"
    if not shot_source.is_file():
        shot_source = SOURCES / "site" / "home.en.png"
    shot = Image.open(shot_source).convert("RGB")
    shot = shot.resize((1000, round(shot.height * 1000 / shot.width)), Image.Resampling.LANCZOS)
    card.paste(shot, (150, 250))
    # Fade the bottom of the screenshot into the background.
    fade = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(fade)
    for y in range(400, height):
        draw.line([(0, y), (width, y)], fill=round(255 * (y - 400) / (height - 400)))
    card.paste(Image.new("RGB", (width, height), (13, 14, 16)), (0, 0), fade)

    logo = Image.open(SOURCES / "logo.png").convert("RGBA").resize((112, 112), Image.Resampling.LANCZOS)
    card.paste(logo, (150, 70), logo)
    draw = ImageDraw.Draw(card)
    draw.text((290, 74), "Alcedo Studio", font=ImageFont.truetype(str(FONTS / title_font), 64), fill=(255, 255, 255))
    draw.text((292, 152), tagline, font=ImageFont.truetype(str(FONTS / text_font), 34), fill=(200, 205, 212))
    card.save(ASSETS / out_name, optimize=True)
    print(f"{out_name}: {(ASSETS / out_name).stat().st_size // 1024} KB")


def build_cards() -> None:
    build_card("en", "social-card.png", "seguisb.ttf", "segoeui.ttf", "Modern RAW editor for Windows and macOS")
    build_card("zh-CN", "social-card-zh.png", "seguisb.ttf", "msyh.ttc", "现代 RAW 修图软件，支持 Windows 和 macOS")


def main() -> int:
    if not (SOURCES / "site").is_dir():
        print(f"source directory not found: {SOURCES / 'site'}", file=sys.stderr)
        return 1
    SHOTS.mkdir(parents=True, exist_ok=True)
    ids = shot_ids()
    only = set(sys.argv[1:])
    unknown = only - set(ids) - {"icons", "cards"}
    if unknown:
        print(f"unknown names: {', '.join(sorted(unknown))}", file=sys.stderr)
        return 1
    for shot in ids:
        if not only or shot in only:
            build_shot(shot)
    if not only or "icons" in only:
        build_icons()
    if not only or "cards" in only:
        build_cards()
    return 0


if __name__ == "__main__":
    sys.exit(main())
