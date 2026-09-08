#!/usr/bin/env python3
"""The courier PWA's icons, drawn rather than downloaded.

A parcel on the brand blue, at the two sizes an installed web app is asked
for. Here rather than committed as an opaque pair of PNGs: an icon nobody can
regenerate is an icon nobody can change, and "make it a shade darker" should
not mean opening an image editor.

    backend/.venv/bin/python tools/courier_icons.py

Re-runs are idempotent — same input, same bytes. The 24-unit grid is the one
lucide draws on, so this parcel and the `Package` glyph inside the app are the
same drawing at two sizes. The tab icon is `courier/public/icon.svg`, written
by hand from the same paths.

Requires Pillow, which the backend's virtualenv already has for its own image
pipeline; there is no separate dependency for this.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

BRAND = (29, 78, 216)   # --color-brand, as sRGB
WHITE = (255, 255, 255)
OUT = Path(__file__).resolve().parent.parent / "courier" / "public"


def parcel(size: int) -> Image.Image:
    """One parcel, filling a `size`×`size` square."""
    img = Image.new("RGB", (size, size), BRAND)
    draw = ImageDraw.Draw(img)
    unit = size / 24
    stroke = max(1, int(unit * 1.4))

    # The box, its lid, the tape down the middle, and the two flaps. Enough to
    # read as a parcel at 48 pixels on a home screen, which is the only size
    # that actually matters.
    draw.rectangle(
        [(6 * unit, 8 * unit), (18 * unit, 19 * unit)], outline=WHITE, width=stroke
    )
    draw.line([(6 * unit, 11.5 * unit), (18 * unit, 11.5 * unit)], fill=WHITE, width=stroke)
    draw.line([(12 * unit, 8 * unit), (12 * unit, 19 * unit)], fill=WHITE, width=stroke)
    draw.line([(8.5 * unit, 5 * unit), (15.5 * unit, 5 * unit)], fill=WHITE, width=stroke)
    draw.line([(8.5 * unit, 5 * unit), (6 * unit, 8 * unit)], fill=WHITE, width=stroke)
    draw.line([(15.5 * unit, 5 * unit), (18 * unit, 8 * unit)], fill=WHITE, width=stroke)
    return img


def main() -> None:
    for size in (192, 512):
        target = OUT / f"icon-{size}.png"
        parcel(size).save(target, "PNG")
        print(f"wrote {target.relative_to(OUT.parent.parent)}")


if __name__ == "__main__":
    main()
