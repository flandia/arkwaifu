"""Create the one thumbnail rendition published for each final artwork image."""

from __future__ import annotations

from io import BytesIO
from urllib.parse import quote

from PIL import Image

from .domain import ArtworkCategory, PngImage

_MAX_SIZE = (512, 512)
_QUALITY = 75


def make_thumbnail(source: PngImage) -> bytes:
    """Fit one PNG within 512 pixels and encode it as WebP without upscaling."""

    encoded = source.path if source.path is not None else BytesIO(source.content)
    with Image.open(encoded) as image:
        image.load()
        result = image.convert("RGBA")
    result.thumbnail(_MAX_SIZE, Image.Resampling.LANCZOS, reducing_gap=3.0)
    output = BytesIO()
    result.save(output, format="WEBP", quality=_QUALITY, lossless=False)
    return output.getvalue()


def thumbnail_object_key(
    *,
    res_version: str,
    category: ArtworkCategory,
    identifier: str,
) -> str:
    """Return the mutable object key for one versioned artwork thumbnail."""

    if not isinstance(res_version, str) or not res_version:
        raise ValueError("artwork resVersion cannot be empty")
    if category not in {"illustration", "background", "item", "character"}:
        raise ValueError(f"unknown artwork object category: {category}")
    segments = ("ART", res_version, "thumbnail", category, f"{identifier}.webp")
    return "/".join(quote(segment, safe="") for segment in segments)
