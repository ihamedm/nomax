import pytest

from app.core.config import settings
from app.core.security import create_access_token
from app.models.user import UserRole


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


@pytest.fixture
def backup_dir(tmp_path, monkeypatch):
    directory = tmp_path / "backups"
    directory.mkdir()
    monkeypatch.setattr(settings, "BACKUP_DIR", str(directory))
    return directory


@pytest.mark.asyncio
async def test_backup_endpoints_require_superadmin(client, create_user, backup_dir):
    admin = await create_user(
        "09150000001", UserRole.ADMIN, permissions=["admin.settings.manage"]
    )
    response = await client.get("/api/v1/admin/backups", headers=auth(admin))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_list_download_and_delete_backup(client, create_user, backup_dir):
    superadmin = await create_user("09150000002", UserRole.SUPERADMIN)
    filename = "nomax-20261031T120000123456Z-manual.sql"
    path = backup_dir / filename
    path.write_bytes(b"test-backup")

    listed = await client.get("/api/v1/admin/backups", headers=auth(superadmin))
    assert listed.status_code == 200
    body = listed.json()["data"]
    assert body["items"][0]["filename"] == filename
    assert body["items"][0]["kind"] == "manual"
    assert body["items"][0]["size"] == 11

    downloaded = await client.get(
        f"/api/v1/admin/backups/{filename}/download", headers=auth(superadmin)
    )
    assert downloaded.status_code == 200
    assert downloaded.content == b"test-backup"
    assert downloaded.headers["cache-control"] == "no-store"

    deleted = await client.delete(f"/api/v1/admin/backups/{filename}", headers=auth(superadmin))
    assert deleted.status_code == 200
    assert not path.exists()


@pytest.mark.asyncio
async def test_unknown_backup_name_is_rejected(client, create_user, backup_dir):
    del backup_dir
    superadmin = await create_user("09150000003", UserRole.SUPERADMIN)
    for filename in ("not-a-backup.sql", "nomax-20261031T120000123456Z-other.sql"):
        response = await client.get(
            f"/api/v1/admin/backups/{filename}/download", headers=auth(superadmin)
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "backup_not_found"


@pytest.mark.asyncio
async def test_restore_requires_exact_confirmation(client, create_user, backup_dir):
    superadmin = await create_user("09150000004", UserRole.SUPERADMIN)
    filename = "nomax-20261031T120000123456Z-manual.sql"
    (backup_dir / filename).write_bytes(b"test-backup")

    response = await client.post(
        f"/api/v1/admin/backups/{filename}/restore",
        data={"confirm": "restore"},
        headers=auth(superadmin),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "restore_confirmation_required"


@pytest.mark.asyncio
async def test_invalid_backup_upload_is_rejected_and_removed(
    client, create_user, backup_dir
):
    superadmin = await create_user("09150000005", UserRole.SUPERADMIN)
    response = await client.post(
        "/api/v1/admin/backups/restore-upload",
        data={"confirm": "RESTORE"},
        files={"file": ("bad.sql", b"this is not a database dump", "text/plain")},
        headers=auth(superadmin),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_backup_file"
    assert list(backup_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_list_marks_backups_present_in_private_s3(
    client, create_user, backup_dir, monkeypatch
):
    from app.services import database_backups

    superadmin = await create_user("09150000006", UserRole.SUPERADMIN)
    filename = "nomax-20261031T120000123456Z-auto.sql"
    (backup_dir / filename).write_bytes(b"test-backup")

    async def snapshot(timeout=6.0):
        del timeout
        return {
            "configured": True,
            "items": {f"{filename}.gz": {"key": f"database-backups/{filename}.gz"}},
            "error": None,
        }

    monkeypatch.setattr(database_backups, "remote_snapshot", snapshot)
    monkeypatch.setattr(database_backups, "s3_configured", lambda: True)
    monkeypatch.setattr(database_backups.settings, "BACKUP_KEEP_REMOTE", 30)

    response = await client.get("/api/v1/admin/backups", headers=auth(superadmin))
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["items"][0]["kind"] == "auto"
    assert body["items"][0]["remote"] is True
    assert body["s3"]["configured"] is True
    assert body["s3"]["keep_remote"] == 30


@pytest.mark.asyncio
async def test_s3_sync_requires_configured_credentials(
    client, create_user, backup_dir, monkeypatch
):
    from app.services import database_backups

    del backup_dir
    superadmin = await create_user("09150000007", UserRole.SUPERADMIN)
    monkeypatch.setattr(database_backups, "s3_configured", lambda: False)

    response = await client.post(
        "/api/v1/admin/backups/sync-s3", headers=auth(superadmin)
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "backup_s3_not_configured"
