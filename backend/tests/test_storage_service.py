from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.core.config import settings
from app.services import storage


def test_prefix_and_name_normalization():
    assert storage.normalize_prefix(None) == ""
    assert storage.normalize_prefix("/docs/") == "docs/"
    assert storage.normalize_prefix("a/b") == "a/b/"
    assert storage.safe_name("folder/file.jpg") == "file.jpg"
    with pytest.raises(storage.StorageValidationError):
        storage.normalize_prefix("../etc")
    with pytest.raises(storage.StorageValidationError):
        storage.safe_name("..")


def test_public_url_path_style(monkeypatch):
    monkeypatch.setattr(settings, "S3_ENDPOINT_URL", "https://s3.example.ir")
    monkeypatch.setattr(settings, "S3_PUBLIC_URL", "")
    monkeypatch.setattr(settings, "S3_ADDRESSING_STYLE", "path")
    monkeypatch.setattr(settings, "S3_BUCKET_PUBLIC", "nomax-public")
    assert storage.public_url("uploads/a b.jpg") == (
        "https://s3.example.ir/nomax-public/uploads/a%20b.jpg"
    )


def test_list_entries_maps_folders_and_files(monkeypatch):
    class FakeClient:
        def list_objects_v2(self, **kwargs):
            return {
                "CommonPrefixes": [{"Prefix": "docs/images/"}],
                "Contents": [
                    {"Key": "docs/", "Size": 0},
                    {"Key": "docs/readme.txt", "Size": 12},
                ],
            }

    monkeypatch.setattr(storage, "_client", lambda: FakeClient())
    items = storage._list_entries_sync("public", "docs/")
    assert [item["name"] for item in items] == ["images", "readme.txt"]
    assert items[0]["type"] == "folder"
    assert items[1]["type"] == "file"


def test_file_link_public_and_private(monkeypatch):
    monkeypatch.setattr(settings, "S3_ENDPOINT_URL", "https://s3.example.ir")
    monkeypatch.setattr(settings, "S3_PUBLIC_URL", "")
    monkeypatch.setattr(settings, "S3_ADDRESSING_STYLE", "path")
    monkeypatch.setattr(settings, "S3_BUCKET_PUBLIC", "nomax-public")
    monkeypatch.setattr(settings, "S3_BUCKET_PRIVATE", "nomax-private")
    monkeypatch.setattr(settings, "S3_PRESIGN_TTL_SECONDS", 600)

    public = storage._file_link_sync("public", "docs/readme.txt")
    assert public == {
        "url": "https://s3.example.ir/nomax-public/docs/readme.txt",
        "expires_in": None,
    }

    class FakeClient:
        def generate_presigned_url(self, operation, Params, ExpiresIn):
            assert operation == "get_object"
            assert Params == {"Bucket": "nomax-private", "Key": "docs/readme.txt"}
            assert ExpiresIn == 600
            return "https://signed.example/readme"

    monkeypatch.setattr(storage, "_client", lambda: FakeClient())
    private = storage._file_link_sync("private", "docs/readme.txt")
    assert private == {"url": "https://signed.example/readme", "expires_in": 600}


def test_public_uploads_get_public_read_acl(monkeypatch):
    calls = []

    class FakeClient:
        def put_object(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(storage, "_client", lambda: FakeClient())
    monkeypatch.setattr(settings, "S3_PUBLIC_READ_ACL", True)

    storage._upload_file_sync("public", "docs/", "a.txt", b"a", "text/plain")
    storage._upload_file_sync("private", "docs/", "b.txt", b"b", "text/plain")

    assert calls[0]["ACL"] == "public-read"
    assert "ACL" not in calls[1]


def test_user_upload_prefix_shards_by_kind_user_and_month():
    user_id = UUID("aaaaaaaa-1111-4111-8111-111111111111")
    prefix = storage.user_upload_prefix(
        "businesses",
        user_id,
        now=datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc),
    )
    assert prefix == f"uploads/businesses/{user_id}/2026/10/"


def test_local_image_bundle_keeps_nested_prefix(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "S3_ACCESS_KEY", "")
    monkeypatch.setattr(settings, "S3_SECRET_KEY", "")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

    prefix = "uploads/businesses/user-1/2026/10/"
    saved = storage._save_image_bundle_sync(
        b"main-image",
        {"square": b"square-image", "thumb": b"thumb-image"},
        prefix,
    )

    assert saved["key"].startswith(prefix)
    assert saved["url"].startswith("/uploads/businesses/user-1/2026/10/")
    assert set(saved["variants"]) == {"square", "thumb"}

    main_path = tmp_path / saved["key"].removeprefix("uploads/")
    assert main_path.read_bytes() == b"main-image"
    assert (tmp_path / saved["variants"]["square"]["key"].removeprefix("uploads/")).exists()
    assert len(list((tmp_path / "businesses/user-1/2026/10").iterdir())) == 3


def test_local_save_upload_keeps_nested_prefix(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "S3_ACCESS_KEY", "")
    monkeypatch.setattr(settings, "S3_SECRET_KEY", "")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

    url = storage._save_upload_sync(
        b"raw", "file.txt", "uploads/businesses/user-1/2026/10/"
    )
    assert url.startswith("/uploads/businesses/user-1/2026/10/")
    assert (tmp_path / url.removeprefix("/uploads/")).read_bytes() == b"raw"
