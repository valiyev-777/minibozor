"""Putting a picture where the catalogue can serve it.

Until now an image reached the catalogue as a string: ``image_url`` was typed
in, and whatever it pointed at had to already be on the disk. That worked
while the only pictures were the seeded ones, and stops working the moment a
seller writes a card for something they have photographed.

The endpoint takes a file and hands back the same kind of relative path the
seeded images carry, so everything downstream — the image list, the category
picture, a colour's swatch — takes it without knowing where it came from.

What it will not do is store what it was given. The bytes are decoded, shrunk
and written out again by us, under a name we chose; see ``app.images`` for why
each of those is not a nicety.
"""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from app import i18n, images
from app import schemas as s
from app import services as sv
from app.deps import MediaUploader

router = APIRouter(tags=["media"])


@router.post(
    "/media",
    response_model=s.MediaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a picture and get its media path",
)
def upload(
    user: MediaUploader,
    file: UploadFile = File(description="A photograph. Any format Pillow reads."),
    square: bool = Query(
        False, description="Pad onto a white square — for product photographs"
    ),
) -> s.MediaOut:
    """The office, the receiving desk and a courier at a door.

    A pile sorted out of a sack is photographed where it is sorted, and a card
    with no picture never reaches the apps. A courier photographs a doorstep,
    which is the evidence a delivery happened — the same pipeline, and there
    was no reason to build a second one that decodes and shrinks pictures
    slightly differently.

    ``square`` is what keeps a catalogue looking like a catalogue: phone
    photographs arrive portrait and landscape and a grid where every tile
    crops differently looks broken. It is off by default because a doorstep is
    not a product.

    Declared ``def`` rather than ``async def`` on purpose: decoding and
    re-encoding a four-megapixel photograph is a second of CPU, and on the
    event loop that second is a second nobody else is served in. Sync
    endpoints run in the threadpool, which is where this belongs.
    """
    try:
        data = images.read_within_limit(file.file)
        path, width, height, size = images.store(data, square=square)
    except images.EmptyUpload:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, i18n.label("file_empty")
        ) from None
    except images.ImageTooLarge:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            i18n.label("file_too_large", limit=images.MAX_BYTES // (1024 * 1024)),
        ) from None
    except images.NotAnImage:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, i18n.label("not_an_image")
        ) from None

    return s.MediaOut(
        media_url=sv.media_url(path), width=width, height=height, bytes=size
    )
