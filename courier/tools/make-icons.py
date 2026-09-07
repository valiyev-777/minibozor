#!/usr/bin/env python3
"""Draw the app icons.

The mark is the design system's own ``box`` glyph (``design/icons.json``) —
the same parcel the customer app puts on an order — drawn here with primitives
rather than rasterised from the path data, because the shape is four lines and
pulling in an SVG rasteriser to place them would be the larger dependency.

Colours come from the same tokens as the application: the brand blue and white.
A courier finds this icon on a home screen full of other icons, in sunlight, so
it is a solid field of one saturated colour with a white shape on it and no
gradient, no shadow and no text.

    python3 tools/make-icons.py         # writes public/*.png

Needs Pillow. The backend's environment already has it.
"""

from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw

BRAND = (19, 69, 214, 255)
WHITE = (255, 255, 255, 255)
OUT = pathlib.Path(__file__).resolve().parent.parent / "public"


def parcel(draw: ImageDraw.ImageDraw, size: int, inset: float) -> None:
    """A taped parcel: a box, a band of tape across it, and the strap over the lid.

    Drawn rather than lettered. At 48 pixels on a home screen a glyph reads and
    a word does not, and the word would be the wrong one in two of the three
    languages this company already ships in.
    """
    pad = size * inset
    width = max(2, round(size * 0.06))
    left, right = pad, size - pad
    top, bottom = pad * 1.15, size - pad * 1.15

    draw.rounded_rectangle(
        [left, top, right, bottom], radius=size * 0.04, outline=WHITE, width=width
    )
    # The tape, running the full width. This is the line that makes the shape a
    # parcel instead of a window: it crosses the outline rather than dividing
    # the inside into panes.
    band = top + (bottom - top) * 0.42
    draw.line([left - width * 0.4, band, right + width * 0.4, band], fill=WHITE, width=width)
    # The strap over the lid, from the top edge down to the tape only.
    middle = (left + right) / 2
    draw.line([middle, top - width * 0.4, middle, band], fill=WHITE, width=width)


def write(name: str, size: int, inset: float, radius_ratio: float) -> None:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    radius = size * radius_ratio
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=BRAND)
    parcel(draw, size, inset)
    image.save(OUT / name)
    print(f"{name}  {size}×{size}")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    # The two the manifest lists, plus a maskable one. A maskable icon is
    # cropped to whatever shape the launcher likes, so its mark sits inside the
    # 80% safe zone and its background runs to the edge.
    write("icon-192.png", 192, inset=0.26, radius_ratio=0.22)
    write("icon-512.png", 512, inset=0.26, radius_ratio=0.22)
    write("maskable-512.png", 512, inset=0.34, radius_ratio=0.0)
