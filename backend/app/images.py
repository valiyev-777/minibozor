"""Taking a photograph in and making it a catalogue image.

A picture arrives from somebody's phone: four megabytes, four thousand pixels
across, called ``IMG_20260907_113045.jpg``, and — for all the request says —
possibly not a picture at all. What the catalogue actually holds is between
169 and 641 pixels and is served straight off disk to two apps. This module is
the step between the two.

Three things the uploader writes are not trusted: the file name, its
extension, and the declared content type. All three are theirs to make up. The
bytes are the only honest part of the request, so the test is simply whether
they decode as an image — a ``.jpg`` that is really a shell script does not,
and is refused for that reason rather than for how it is spelt.

Nor is the name kept. A stored file is named after a fresh uuid, which settles
the whole class of questions about ``../``, about two people uploading
``photo.jpg``, and about a name that means something to a filesystem it was
never meant to reach.
"""

from __future__ import annotations

import uuid
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageOps, UnidentifiedImageError

# Served by the StaticFiles mount in ``app.main``, which imports this rather
# than the other way round: the directory is a property of how media is
# stored, and the app is what happens to expose it.
MEDIA_DIR = Path(__file__).resolve().parent.parent / "media"

# Uploads go in their own drawer. The seeded catalogue lives in
# ``products/`` and ``categories/`` and is checked against the design; mixing
# what somebody sent this morning in among it makes neither set legible.
UPLOAD_SUBDIR = "uploads"

# Eight megabytes in, sixteen hundred pixels out. The limit is on what we will
# read rather than on what the client claims to be sending: a Content-Length
# is a promise, and the body is the thing that actually arrives.
MAX_BYTES = 8 * 1024 * 1024
MAX_SIDE = 1600
QUALITY = 82
CHUNK = 64 * 1024


class ImageTooLarge(Exception):
    """More bytes than we will read, whatever they turn out to be."""


class NotAnImage(Exception):
    """The bytes do not decode as a picture."""


class EmptyUpload(Exception):
    """No bytes at all."""


def read_within_limit(stream: BinaryIO, limit: int = MAX_BYTES) -> bytes:
    """The whole upload, or ``ImageTooLarge`` before it is all in memory.

    Read in chunks and stopped at the first byte past the limit, so an
    oversized file costs the limit and not its own size — which is the point
    of having one.
    """
    parts: list[bytes] = []
    total = 0
    while chunk := stream.read(CHUNK):
        total += len(chunk)
        if total > limit:
            raise ImageTooLarge
        parts.append(chunk)
    if total == 0:
        raise EmptyUpload
    return b"".join(parts)


def store(data: bytes) -> tuple[str, int, int, int]:
    """Re-encode, shrink, and write. Returns ``(path, width, height, bytes)``.

    The path is relative — ``uploads/<uuid>.webp`` — which is the shape the
    rest of the catalogue stores and ``services.media_url`` passes through
    unchanged, so an uploaded picture and a seeded one are the same kind of
    string by the time an app reads it.

    Re-encoding is not only about size. Whatever arrived is decoded and written
    out again from pixels, so the file on disk is one this process produced:
    metadata, trailing bytes, and anything hidden behind a valid image header
    do not survive the round trip.
    """
    try:
        with Image.open(BytesIO(data)) as opened:
            # Phones record which way up the camera was instead of rotating the
            # pixels. Applied now, because the tag is dropped on the way out.
            image = ImageOps.exif_transpose(opened) or opened
            image.load()
            image = _flatten(image)
            # ``thumbnail`` is a no-op on a picture already inside the box, so
            # a 640px catalogue image is re-encoded but never enlarged.
            image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
            width, height = image.size

            directory = MEDIA_DIR / UPLOAD_SUBDIR
            directory.mkdir(parents=True, exist_ok=True)
            name = f"{uuid.uuid4().hex}.webp"
            path = directory / name
            image.save(path, "WEBP", quality=QUALITY, method=6)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        # A decompression bomb declares a size in its header that nothing sane
        # would send; it is refused with everything else that will not open,
        # because the answer to the uploader is the same either way.
        raise NotAnImage from None

    return f"{UPLOAD_SUBDIR}/{name}", width, height, path.stat().st_size


def _flatten(image: Image.Image) -> Image.Image:
    """A mode WebP can write, keeping transparency where there was any.

    A palette image with a transparent index, a greyscale-with-alpha, a CMYK
    scan out of a print workflow: all of them open, and none of them is a mode
    the encoder takes. Alpha is kept rather than filled — a product cut out
    against nothing is a photograph we want, and flattening it onto white
    would put a white box on a dark page.
    """
    if image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        return image.convert("RGBA")
    if image.mode != "RGB":
        return image.convert("RGB")
    return image
