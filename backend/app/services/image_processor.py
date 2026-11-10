"""Image processing for user uploads.

The original file is never stored. The pipeline applies an optional filter,
resizes/compresses the main image and produces named center-cropped variants
for the UI (square profile, card, wide, thumbnail). Admin file-manager uploads
do not go through this module.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageEnhance, ImageOps

MAX_MAIN_DIMENSION = 1600
MAX_SOURCE_PIXELS = 40_000_000

CROP_PRESETS: dict[str, tuple[int, int]] = {
    "square": (800, 800),
    "card": (640, 360),
    "wide": (1200, 600),
    "thumb": (200, 200),
}
VARIANT_NAMES: tuple[str, ...] = tuple(CROP_PRESETS)
MAIN_MAX_KB = 350
VARIANT_MAX_KB: dict[str, int] = {
    "square": 220,
    "card": 120,
    "wide": 220,
    "thumb": 40,
}

FILTERS = ("none", "warm", "cool", "vivid", "mono", "soft")
ANCHORS: dict[str, tuple[float, float]] = {
    "center": (0.5, 0.5),
    "top": (0.5, 0.0),
    "bottom": (0.5, 1.0),
    "left": (0.0, 0.5),
    "right": (1.0, 0.5),
}


class InvalidImage(ValueError):
    pass


@dataclass(frozen=True)
class RenderedImage:
    data: bytes
    width: int
    height: int
    size: int


@dataclass(frozen=True)
class ProcessedImage:
    main: RenderedImage
    variants: dict[str, RenderedImage]
    crop: str
    filter: str


def _open_image(data: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as exc:  # noqa: BLE001 - any decoder error is a bad upload
        raise InvalidImage("invalid_image") from exc
    if image.width <= 0 or image.height <= 0:
        raise InvalidImage("invalid_image")
    if image.width * image.height > MAX_SOURCE_PIXELS:
        raise InvalidImage("image_too_large")
    return ImageOps.exif_transpose(image) or image


def _rgb(image: Image.Image) -> Image.Image:
    if image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        background = Image.new("RGB", image.size, (255, 255, 255))
        rgba = image.convert("RGBA")
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def apply_filter(image: Image.Image, name: str) -> Image.Image:
    if name == "none":
        return image
    if name == "mono":
        return ImageOps.grayscale(image).convert("RGB")
    if name == "vivid":
        image = ImageEnhance.Color(image).enhance(1.25)
        return ImageEnhance.Contrast(image).enhance(1.08)
    if name == "soft":
        image = ImageEnhance.Brightness(image).enhance(1.04)
        return ImageEnhance.Contrast(image).enhance(0.94)
    if name in ("warm", "cool"):
        overlay_color = (255, 176, 92) if name == "warm" else (92, 168, 255)
        overlay = Image.new("RGB", image.size, overlay_color)
        return Image.blend(image, overlay, 0.08)
    raise ValueError("invalid_filter")


def _encode_jpeg(image: Image.Image, max_size_kb: int) -> RenderedImage:
    data = b""
    for quality in (90, 85, 80, 75, 70, 65, 60, 55, 50, 45):
        buffer = io.BytesIO()
        image.save(
            buffer,
            "JPEG",
            quality=quality,
            optimize=True,
            progressive=True,
            subsampling=2,
        )
        data = buffer.getvalue()
        if len(data) <= max_size_kb * 1024:
            break
    return RenderedImage(data=data, width=image.width, height=image.height, size=len(data))


def _resize_longest_side(image: Image.Image, max_dimension: int) -> Image.Image:
    if max(image.size) <= max_dimension:
        return image.copy()
    resized = image.copy()
    resized.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
    return resized


def _crop_to_preset(
    image: Image.Image, preset: str, anchor: tuple[float, float]
) -> Image.Image:
    max_width, max_height = CROP_PRESETS[preset]
    aspect = max_width / max_height
    if image.width / image.height > aspect:
        # Source is wider: height is the limiting dimension.
        height = min(max_height, image.height)
        width = max(1, round(height * aspect))
    else:
        width = min(max_width, image.width)
        height = max(1, round(width / aspect))
    return ImageOps.fit(
        image,
        (width, height),
        method=Image.Resampling.LANCZOS,
        centering=anchor,
    )


def process_image(
    data: bytes,
    *,
    crop: str = "square",
    filter: str = "none",
    anchor: str = "center",
) -> ProcessedImage:
    """Process an uploaded image and return the main file plus named crops."""
    if crop not in (*CROP_PRESETS, "original"):
        raise ValueError("invalid_crop")
    if filter not in FILTERS:
        raise ValueError("invalid_filter")
    if anchor not in ANCHORS:
        raise ValueError("invalid_anchor")

    image = _rgb(_open_image(data))
    image = apply_filter(image, filter)
    centering = ANCHORS[anchor]

    if crop == "original":
        main_image = _resize_longest_side(image, MAX_MAIN_DIMENSION)
    else:
        main_image = _crop_to_preset(image, crop, centering)

    main = _encode_jpeg(main_image, MAIN_MAX_KB)
    variants: dict[str, RenderedImage] = {}
    for name in VARIANT_NAMES:
        variant_image = _crop_to_preset(image, name, centering)
        variants[name] = _encode_jpeg(variant_image, VARIANT_MAX_KB[name])

    return ProcessedImage(main=main, variants=variants, crop=crop, filter=filter)


def compress_image(data: bytes, max_size_kb: int = 150) -> bytes:
    """Backward-compatible helper: resize the original and compress to a JPEG."""
    image = _rgb(_open_image(data))
    resized = _resize_longest_side(image, MAX_MAIN_DIMENSION)
    return _encode_jpeg(resized, max_size_kb).data
