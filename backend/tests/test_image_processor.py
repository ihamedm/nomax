"""Crop / filter / resize / compression pipeline for user uploads."""

import io

import pytest
from PIL import Image

from app.services.image_processor import (
    CROP_PRESETS,
    InvalidImage,
    process_image,
)


def _png(width: int = 2000, height: int = 1000, color=(180, 90, 40)) -> bytes:
    image = Image.new("RGB", (width, height), color)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def _decoded(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGB")


def test_square_main_and_named_crops():
    processed = process_image(_png(), crop="square")

    assert (processed.main.width, processed.main.height) == (800, 800)
    assert set(processed.variants) == set(CROP_PRESETS)
    assert (processed.variants["card"].width, processed.variants["card"].height) == (640, 360)
    assert (processed.variants["wide"].width, processed.variants["wide"].height) == (1200, 600)
    assert (processed.variants["thumb"].width, processed.variants["thumb"].height) == (200, 200)
    assert processed.main.size <= 350 * 1024
    assert processed.variants["thumb"].size <= 40 * 1024


def test_original_main_is_resized_but_not_cropped():
    processed = process_image(_png(3000, 2000), crop="original")
    assert processed.main.width <= 1600
    assert processed.main.height <= 1600
    assert processed.main.width / processed.main.height == pytest.approx(1.5, rel=0.01)


def test_filter_is_applied_to_main_and_variants():
    processed = process_image(_png(), filter="mono")
    main = _decoded(processed.main.data)
    red, green, blue = main.getpixel((10, 10))
    assert red == green == blue

    warm = process_image(_png(), filter="warm").main.data
    assert warm != processed.main.data


def test_invalid_image_and_invalid_options():
    with pytest.raises(InvalidImage):
        process_image(b"not-an-image")
    with pytest.raises(ValueError):
        process_image(_png(), crop="does-not-exist")
    with pytest.raises(ValueError):
        process_image(_png(), filter="does-not-exist")
    with pytest.raises(ValueError):
        process_image(_png(), anchor="does-not-exist")


def test_anchor_changes_the_crop():
    image = Image.new("RGB", (1000, 1000), (255, 255, 255))
    image.paste((255, 0, 0), (0, 0, 1000, 200))  # red band at the top
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    data = buffer.getvalue()

    top = _decoded(process_image(data, crop="card", anchor="top").main.data)
    bottom = _decoded(process_image(data, crop="card", anchor="bottom").main.data)
    assert top.getpixel((320, 10))[0] > 200
    assert top.getpixel((320, 10))[1] < 60
    assert bottom.getpixel((320, 10))[1] > 200
    assert top.tobytes() != bottom.tobytes()


def test_small_images_are_not_upscaled():
    processed = process_image(_png(300, 300), crop="square")
    assert (processed.main.width, processed.main.height) == (300, 300)
    assert (processed.variants["card"].width, processed.variants["card"].height) == (300, 169)
    assert (processed.variants["wide"].width, processed.variants["wide"].height) == (300, 150)
