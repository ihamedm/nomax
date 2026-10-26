import io

from PIL import Image


class InvalidImage(ValueError):
    pass


def compress_image(data: bytes, max_size_kb: int = 150) -> bytes:
    try:
        image = Image.open(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001 - any decoder error is a bad upload
        raise InvalidImage("invalid_image") from exc
    if image.mode != "RGB":
        image = image.convert("RGB")
    if max(image.size) > 1200:
        image.thumbnail((1200, 1200))
    buffer = io.BytesIO()
    for quality in (85, 75, 65, 55, 45):
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=quality, optimize=True)
        if buffer.tell() <= max_size_kb * 1024:
            return buffer.getvalue()
    return buffer.getvalue()
