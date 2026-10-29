from app.core.security import create_access_token
from app.models.user import UserRole


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


async def test_file_manager_requires_permission(client, create_user):
    admin = await create_user("09170000001", UserRole.ADMIN, permissions=[])
    response = await client.get("/api/v1/admin/files", headers=auth(admin))
    assert response.status_code == 403


async def test_file_manager_list_create_and_delete(client, create_user, monkeypatch):
    from app.api.v1 import files as files_api

    admin = await create_user(
        "09170000002", UserRole.ADMIN, permissions=["storage.manage"]
    )

    async def fake_list(bucket, prefix):
        return {
            "bucket": bucket,
            "prefix": "docs/",
            "items": [
                {"type": "folder", "name": "images", "key": "docs/images/", "size": 0},
                {"type": "file", "name": "readme.txt", "key": "docs/readme.txt", "size": 12},
            ],
        }

    async def fake_create(bucket, prefix, name):
        return {"type": "folder", "name": name, "key": f"{prefix}{name}/", "size": 0}

    async def fake_delete(bucket, key):
        return None

    async def fake_link(bucket, key):
        return {"url": "https://cdn.example/docs/readme.txt", "expires_in": None}

    monkeypatch.setattr(files_api.storage, "list_entries", fake_list)
    monkeypatch.setattr(files_api.storage, "create_folder", fake_create)
    monkeypatch.setattr(files_api.storage, "delete_entry", fake_delete)
    monkeypatch.setattr(files_api.storage, "file_link", fake_link)

    listed = await client.get(
        "/api/v1/admin/files?bucket=public&prefix=docs%2F", headers=auth(admin)
    )
    assert listed.status_code == 200
    assert listed.json()["data"]["items"][0]["name"] == "images"

    folder = await client.post(
        "/api/v1/admin/files/folder",
        json={"bucket": "public", "prefix": "docs/", "name": "new-folder"},
        headers=auth(admin),
    )
    assert folder.status_code == 200
    assert folder.json()["data"]["key"] == "docs/new-folder/"

    deleted = await client.delete(
        "/api/v1/admin/files?bucket=public&key=docs%2Freadme.txt", headers=auth(admin)
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted"] is True

    link = await client.get(
        "/api/v1/admin/files/link?bucket=public&key=docs%2Freadme.txt", headers=auth(admin)
    )
    assert link.status_code == 200
    assert link.json()["data"]["url"] == "https://cdn.example/docs/readme.txt"


async def test_file_manager_upload(client, create_user, monkeypatch):
    from app.api.v1 import files as files_api

    admin = await create_user(
        "09170000003", UserRole.ADMIN, permissions=["storage.manage"]
    )
    captured = {}

    async def fake_upload(bucket, prefix, filename, data, content_type):
        captured.update(
            {
                "bucket": bucket,
                "prefix": prefix,
                "filename": filename,
                "data": data,
                "content_type": content_type,
            }
        )
        return {"type": "file", "name": filename, "key": f"{prefix}{filename}", "size": len(data)}

    monkeypatch.setattr(files_api.storage, "upload_file", fake_upload)

    response = await client.post(
        "/api/v1/admin/files/upload",
        data={"bucket": "private", "prefix": "licenses/"},
        files={"file": ("license.txt", b"hello", "text/plain")},
        headers=auth(admin),
    )
    assert response.status_code == 200
    assert captured["bucket"] == "private"
    assert captured["prefix"] == "licenses/"
    assert captured["data"] == b"hello"
