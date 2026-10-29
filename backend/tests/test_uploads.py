"""Business image upload: processing, named crops and sharded storage."""

import io
import re

from PIL import Image

from app.core.config import settings
from app.core.security import create_access_token
from app.models.user import UserRole


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


def _jpeg(width: int = 1600, height: int = 1200) -> bytes:
    image = Image.new("RGB", (width, height), (40, 120, 90))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=90)
    return buffer.getvalue()


async def test_business_image_upload_processes_and_shards(
    client, create_user, monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "S3_ACCESS_KEY", "")
    monkeypatch.setattr(settings, "S3_SECRET_KEY", "")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    owner = await create_user("09180000001", UserRole.OWNER)

    response = await client.post(
        "/api/v1/uploads/image",
        data={"crop": "square", "filter": "warm", "anchor": "center"},
        files={"file": ("shop.jpg", _jpeg(), "image/jpeg")},
        headers=auth(owner),
    )
    assert response.status_code == 200
    data = response.json()["data"]

    assert (data["width"], data["height"]) == (800, 800)
    assert data["crop"] == "square"
    assert data["filter"] == "warm"
    assert set(data["variants"]) == {"square", "card", "wide", "thumb"}
    assert (data["variants"]["card"]["width"], data["variants"]["card"]["height"]) == (
        640,
        360,
    )
    assert data["size"] <= 350 * 1024

    expected_prefix = rf"^/uploads/businesses/{owner.id}/\d{{4}}/\d{{2}}/"
    assert re.match(expected_prefix, data["url"])
    for name, variant in data["variants"].items():
        assert re.match(expected_prefix, variant["url"]), name
        assert (tmp_path / variant["key"].removeprefix("uploads/")).exists()
    assert (tmp_path / data["key"].removeprefix("uploads/")).exists()

    # Main and variants are grouped under one UUID and never dumped at root.
    assert len(list(tmp_path.iterdir())) == 1
    assert list(tmp_path.iterdir())[0].name == "businesses"


async def test_business_image_upload_rejects_invalid_options_and_payload(
    client, create_user, monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "S3_ACCESS_KEY", "")
    monkeypatch.setattr(settings, "S3_SECRET_KEY", "")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    owner = await create_user("09180000002", UserRole.OWNER)

    bad_crop = await client.post(
        "/api/v1/uploads/image",
        data={"crop": "panorama"},
        files={"file": ("shop.jpg", _jpeg(), "image/jpeg")},
        headers=auth(owner),
    )
    assert bad_crop.status_code == 422
    assert bad_crop.json()["error"]["code"] == "invalid_crop"

    bad_filter = await client.post(
        "/api/v1/uploads/image",
        data={"filter": "sepia"},
        files={"file": ("shop.jpg", _jpeg(), "image/jpeg")},
        headers=auth(owner),
    )
    assert bad_filter.status_code == 422
    assert bad_filter.json()["error"]["code"] == "invalid_filter"

    invalid = await client.post(
        "/api/v1/uploads/image",
        files={"file": ("shop.jpg", b"not-an-image", "image/jpeg")},
        headers=auth(owner),
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_image"

    wrong_type = await client.post(
        "/api/v1/uploads/image",
        files={"file": ("shop.txt", b"text", "text/plain")},
        headers=auth(owner),
    )
    assert wrong_type.status_code == 422
    assert wrong_type.json()["error"]["code"] == "validation_error"


async def test_admin_file_upload_stays_raw(client, create_user, monkeypatch, tmp_path):
    """Admin file-manager uploads bypass the image processor."""
    from app.api.v1 import files as files_api

    admin = await create_user(
        "09180000003", UserRole.ADMIN, permissions=["storage.manage"]
    )
    captured = {}

    async def fake_upload(bucket, prefix, filename, data, content_type):
        captured["data"] = data
        return {"type": "file", "name": filename, "key": f"{prefix}{filename}", "size": len(data)}

    monkeypatch.setattr(files_api.storage, "upload_file", fake_upload)
    original = _jpeg(500, 400)

    response = await client.post(
        "/api/v1/admin/files/upload",
        data={"bucket": "public", "prefix": "manual/"},
        files={"file": ("raw.jpg", original, "image/jpeg")},
        headers=auth(admin),
    )
    assert response.status_code == 200
    assert captured["data"] == original
