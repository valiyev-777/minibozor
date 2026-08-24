"""Generate a neutral product placeholder PNG (no third-party imaging deps).

Six of the design's product photos exceeded the 256 KiB per-file cap of the
Claude Design read API and could not be pulled down intact. Those slots get a
placeholder so the apps render correctly; replace them by exporting the real
files from the design project into ``backend/media/products/``.
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

SIZE = 640
BG = (0xF4, 0xF3, 0xF1)
SHAPE = (0xE6, 0xE7, 0xEB)
EDGE = (0xD7, 0xD9, 0xE0)


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def _rounded_box(x: int, y: int) -> tuple[int, int, int] | None:
    """A centred rounded square, the same silhouette the design uses for photos."""
    pad, radius = SIZE // 4, 56
    x0 = y0 = pad
    x1 = y1 = SIZE - pad
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        return None

    cx = min(max(x, x0 + radius), x1 - radius)
    cy = min(max(y, y0 + radius), y1 - radius)
    dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
    if dist > radius:
        return None
    return EDGE if dist > radius - 3 else SHAPE


def render(path: Path) -> None:
    rows = bytearray()
    for y in range(SIZE):
        rows.append(0)  # filter type 0
        for x in range(SIZE):
            rows.extend(_rounded_box(x, y) or BG)

    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 2, 0, 0, 0))
    png += _chunk(b"IDAT", zlib.compress(bytes(rows), 9))
    png += _chunk(b"IEND", b"")
    path.write_bytes(png)


if __name__ == "__main__":
    for name in sys.argv[1:]:
        target = Path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        render(target)
        print(f"placeholder -> {target}")
