import gzip
from datetime import datetime, timezone

import pytest

from app.core.config import settings
from app.services import backup_scheduler, database_backups, storage


@pytest.fixture
def backup_dir(tmp_path, monkeypatch):
    directory = tmp_path / "backups"
    directory.mkdir()
    monkeypatch.setattr(settings, "BACKUP_DIR", str(directory))
    return directory


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.uploads: list[dict] = []
        self.deleted: list[str] = []

    def upload_file(self, filename, bucket, key, ExtraArgs=None):
        data = open(filename, "rb").read()
        self.objects[key] = data
        self.uploads.append(
            {"bucket": bucket, "key": key, "data": data, "extra": ExtraArgs or {}}
        )

    def get_paginator(self, operation):
        assert operation == "list_objects_v2"
        fake = self

        class Paginator:
            def paginate(self, **kwargs):
                prefix = kwargs.get("Prefix", "")
                contents = [
                    {
                        "Key": key,
                        "Size": len(data),
                        "LastModified": datetime(2026, 10, 1, tzinfo=timezone.utc),
                    }
                    for key, data in sorted(fake.objects.items())
                    if key.startswith(prefix)
                ]
                return [{"Contents": contents}]

        return Paginator()

    def delete_objects(self, Bucket, Delete):
        for item in Delete["Objects"]:
            self.deleted.append(item["Key"])
            self.objects.pop(item["Key"], None)


@pytest.fixture
def fake_s3(monkeypatch):
    client = FakeS3()
    monkeypatch.setattr(storage, "_client", lambda: client)
    monkeypatch.setattr(settings, "S3_ACCESS_KEY", "key")
    monkeypatch.setattr(settings, "S3_SECRET_KEY", "secret")
    monkeypatch.setattr(settings, "S3_BUCKET_PRIVATE", "nomax-private")
    monkeypatch.setattr(settings, "BACKUP_S3_BUCKET", "")
    monkeypatch.setattr(settings, "BACKUP_S3_PREFIX", "database-backups")
    monkeypatch.setattr(settings, "BACKUP_KEEP_REMOTE", 30)
    return client


@pytest.mark.asyncio
async def test_manual_backup_is_gzipped_uploaded_and_pruned(backup_dir, fake_s3):
    for index in range(30):
        name = f"database-backups/nomax-202609{index + 1:02d}T030000000000Z-auto.sql.gz"
        fake_s3.objects[name] = b"old"

    local = backup_dir / "nomax-20261031T120000123456Z-manual.sql"
    local.write_bytes(b"CREATE TABLE public.users (id int);\n" * 100)
    result = await database_backups.upload_backup(local, "manual")

    assert result["status"] == "uploaded"
    assert result["key"].endswith("-manual.sql.gz")
    remote = fake_s3.uploads[0]
    assert remote["bucket"] == "nomax-private"
    assert gzip.decompress(remote["data"]) == local.read_bytes()
    assert remote["extra"]["ContentType"] == "application/gzip"
    assert len(remote["extra"]["Metadata"]["sha256"]) == 64

    assert len(fake_s3.objects) == 30
    assert remote["key"] in fake_s3.objects
    assert len(fake_s3.deleted) == 1
    assert "nomax-20260901T030000000000Z-auto.sql.gz" in fake_s3.deleted[0]


@pytest.mark.asyncio
async def test_safety_backup_is_not_uploaded(backup_dir, fake_s3):
    local = backup_dir / "nomax-20261031T120000123456Z-pre-restore.sql"
    local.write_bytes(b"backup")
    result = await database_backups.upload_backup(local, "pre-restore")

    assert result["status"] == "skipped"
    assert fake_s3.uploads == []


@pytest.mark.asyncio
async def test_daily_backup_is_idempotent_and_retries_cloud(
    backup_dir, monkeypatch
):
    monkeypatch.setattr(settings, "BACKUP_DAILY_ENABLED", True)
    monkeypatch.setattr(settings, "BACKUP_DAILY_HOUR", 3)
    monkeypatch.setattr(settings, "BACKUP_DAILY_MINUTE", 0)
    monkeypatch.setattr(settings, "BACKUP_TIMEZONE", "Asia/Tehran")

    filename = "nomax-20261031T120000123456Z-auto.sql"
    created: list[str] = []
    sync_calls: list[int] = []
    sync_failures = [1, 0]

    async def create(kind):
        created.append(kind)
        (backup_dir / filename).write_bytes(b"auto")
        return database_backups.backup_entry(backup_dir / filename)

    async def sync():
        sync_calls.append(1)
        failed = sync_failures.pop(0)
        return {
            "configured": True,
            "uploaded": [],
            "failed": [{"filename": filename, "status": "failed"}] if failed else [],
            "pruned": [],
        }

    monkeypatch.setattr(database_backups, "create_backup", create)
    monkeypatch.setattr(database_backups, "sync_backups", sync)

    now = datetime(2026, 10, 31, 0, 30, tzinfo=timezone.utc)  # 04:00 Tehran
    first = await backup_scheduler.run_daily_backup(now)
    assert first["status"] == "created"
    assert created == ["auto"]
    assert first["cloud"]["failed"]

    # The local dump exists but upload failed: retry the sync, not another dump.
    second = await backup_scheduler.run_daily_backup(now)
    assert second["status"] == "synced"
    assert created == ["auto"]
    assert len(sync_calls) == 2

    third = await backup_scheduler.run_daily_backup(now)
    assert third["status"] == "already_done"
    assert created == ["auto"]


@pytest.mark.asyncio
async def test_daily_backup_waits_for_scheduled_time(backup_dir, monkeypatch):
    monkeypatch.setattr(settings, "BACKUP_DAILY_ENABLED", True)
    monkeypatch.setattr(settings, "BACKUP_DAILY_HOUR", 3)
    monkeypatch.setattr(settings, "BACKUP_DAILY_MINUTE", 0)
    monkeypatch.setattr(settings, "BACKUP_TIMEZONE", "Asia/Tehran")

    async def fail_create(kind):
        raise AssertionError("backup must not run before the daily time")

    monkeypatch.setattr(database_backups, "create_backup", fail_create)
    now = datetime(2026, 10, 30, 22, 0, tzinfo=timezone.utc)  # 01:30 Tehran
    result = await backup_scheduler.run_daily_backup(now)
    assert result["status"] == "not_due"


@pytest.mark.asyncio
async def test_sync_uploads_only_missing_backups(backup_dir, fake_s3):
    already = "nomax-20261031T120000000001Z-manual.sql"
    missing = "nomax-20261031T120000000002Z-auto.sql"
    (backup_dir / already).write_bytes(b"already")
    (backup_dir / missing).write_bytes(b"missing")
    fake_s3.objects[f"database-backups/{already}.gz"] = b"existing"

    result = await database_backups.sync_backups()

    assert result["configured"] is True
    assert [item["filename"] for item in result["uploaded"]] == [missing]
    assert result["failed"] == []
    assert [item["key"] for item in fake_s3.uploads] == [
        f"database-backups/{missing}.gz"
    ]
    assert len(fake_s3.objects) == 2
