"""Make phone photos of sketches safe and cheap to send to the VLM.

* Applies the phone's EXIF rotation so "portrait" photos aren't sideways.
* Shrinks very large photos (long side ≤ 2000 px). Claude rejects images
  over ~5 MB / 8000 px, and beyond ~2000 px there's no accuracy gain for
  pencil sketches — only cost and latency.
* ``rotate`` lets the user turn a sideways sketch with one button.
"""

from __future__ import annotations

import io

from PIL import Image, ImageOps

MAX_SIDE = 2000


def normalise(data: bytes, max_side: int = MAX_SIDE) -> tuple[bytes, str]:
    """Return (jpeg_bytes, "image/jpeg") — upright, ≤ max_side, RGB."""
    im = Image.open(io.BytesIO(data))
    im = ImageOps.exif_transpose(im)
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    if max(im.size) > max_side:
        im.thumbnail((max_side, max_side), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, format="JPEG", quality=90)
    return out.getvalue(), "image/jpeg"


def rotate(data: bytes, degrees_clockwise: int = 90) -> bytes:
    im = Image.open(io.BytesIO(data))
    im = im.rotate(-degrees_clockwise, expand=True)
    out = io.BytesIO()
    im.convert("RGB").save(out, format="JPEG", quality=90)
    return out.getvalue()
