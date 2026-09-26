#!/usr/bin/env python3
"""Compress raw screenshots into the AVIF / WebP files the site serves.

Usage:
    python scripts/build_images.py [SOURCE_DIR]

SOURCE_DIR defaults to ./screenshots (git-ignored). Each entry in IMAGES below
names a source file (PNG or JPEG, extension optional) and the widths to emit.
Missing sources are reported and skipped, so screenshots can be replaced one
at a time. Requires Pillow 11.3+ (built-in AVIF support).
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None  # full-resolution camera exports

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "site" / "assets"

# output name -> (source stem, widths[, aspect, focus_y]). One width means a
# single file named "<name>.<ext>"; several widths emit "<name>-<width>.<ext>"
# for srcset. With an aspect ratio the source is center-cropped to it first,
# keeping the row at focus_y (0 = top, 1 = bottom) in view.
IMAGES: dict[str, tuple] = {
    # Home page — full-bleed "cinema" photographs, cropped to 2.2:1
    "cinema-color": ("photo-1", (1280, 1920, 2560), 2.2, 0.45),
    "cinema-free": ("photo-2", (1280, 1920, 2560), 2.2, 0.5),
    # Home page — full-bleed stages (16:9 screenshots, cropped with object-fit)
    "stage-hero": ("hero", (1280, 1920, 2560)),
    "stage-nodes": ("nodes", (1280, 1920, 2560)),
    "stage-masks": ("masks", (1280, 1920, 2560)),
    "stage-color": ("color", (1280, 1920, 2560)),
    # Home page — three full-window screenshots stacked so that only the
    # right-hand adjustment panel of the back two shows (not cropped: the
    # stack geometry in site.css depends on the panel's share of the width)
    "tool-color": ("tool-color", (1280, 1920, 2560)),
    "tool-curve": ("tool-curve", (1280, 1920, 2560)),
    "tool-film": ("tool-film", (1280, 1920, 2560)),
    # Home page — the two workspaces, side by side
    "ws-library": ("library", (960, 1600)),
    "ws-editor": ("editor", (960, 1600)),
    # Detail tiles (home page and features page)
    "detail-copy": ("detail-copy", (1040,)),
    "detail-keys": ("detail-keys", (1040,)),
    "detail-lens": ("detail-lens", (1040,)),
    "detail-contrast": ("detail-contrast", (1040,)),
    # Features page
    "feature-heatmap": ("heatmap", (1600,)),
    "feature-search": ("search", (1600,)),
    "feature-engine": ("engine", (1600,)),
    "feature-film": ("film", (1600,)),
    "feature-ai": ("ai", (1600,)),
    "feature-export": ("export", (1600,)),
}

WEBP_QUALITY = 80
AVIF_QUALITY = 60


def find_source(src_dir: Path, stem: str) -> Path | None:
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        path = src_dir / f"{stem}{ext}"
        if path.is_file():
            return path
    return None


def crop(image: Image.Image, aspect: float, focus_y: float) -> Image.Image:
    width, height = image.size
    if width / height > aspect:
        new_width = round(height * aspect)
        left = (width - new_width) // 2
        return image.crop((left, 0, left + new_width, height))
    new_height = round(width / aspect)
    top = round((height - new_height) * focus_y)
    return image.crop((0, top, width, top + new_height))


def emit(image: Image.Image, width: int, out_stem: Path) -> list[str]:
    if image.width > width:
        height = round(image.height * width / image.width)
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    image.save(out_stem.with_suffix(".webp"), "WEBP", quality=WEBP_QUALITY, method=6)
    image.save(out_stem.with_suffix(".avif"), "AVIF", quality=AVIF_QUALITY, speed=4)
    return [
        f"{p.name} {p.stat().st_size // 1024} KB"
        for p in (out_stem.with_suffix(".avif"), out_stem.with_suffix(".webp"))
    ] + [f"({image.width}x{image.height})"]


def main() -> int:
    src_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "screenshots"
    if not src_dir.is_dir():
        print(f"source directory not found: {src_dir}", file=sys.stderr)
        return 1

    missing = []
    for name, (stem, widths, *framing) in IMAGES.items():
        source = find_source(src_dir, stem)
        if source is None:
            missing.append(stem)
            continue
        image = Image.open(source).convert("RGB")
        if framing:
            image = crop(image, *framing)
        for width in widths:
            out = ASSETS / (name if len(widths) == 1 else f"{name}-{width}")
            print("  ".join(emit(image, width, out)))

    if missing:
        print(f"skipped (no source): {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
