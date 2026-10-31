"""Create, compress and archive database backups.

Local backups remain plain SQL so the restore endpoint can replay them with
``psql``. Every manual/automatic backup that is sent to ArvanCloud S3 is first
gzipped, stored in the private bucket and pruned to a fixed number of objects.
"""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import logging
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.engine import make_url
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.errors import AppError
from app.services import storage

logger = logging.getLogger(__name__)

BACKUP_NAME_RE = re.compile(
    r"^nomax-\d{8}T\d{12}Z-(?:manual|auto|uploaded|pre-restore)\.sql$"
)
REMOTE_NAME_RE = re.compile(
    r"^nomax-\d{8}T\d{12}Z-(?:manual|auto)\.sql\.gz$"
)
BACKUP_LOCK = asyncio.Lock()
KIND_LABELS = {
    "manual": "دستی",
    "auto": "خودکار",
    "uploaded": "بارگذاری‌شده",
    "pre-restore": "ایمنی قبل از بازیابی",
}
CLOUD_KINDS = {"manual", "auto"}


def backup_dir() -> Path:
    directory = Path(settings.BACKUP_DIR)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        directory.chmod(0o700)
    except OSError as exc:
        logger.exception("Cannot prepare backup directory")
        raise AppError("backup_unavailable", "backup_directory_unavailable", 503) from exc
    return directory


def backup_path(filename: str) -> Path:
    if not BACKUP_NAME_RE.fullmatch(filename):
        raise AppError("backup_not_found", "backup_not_found", 404)
    path = backup_dir() / filename
    if not path.is_file():
        raise AppError("backup_not_found", "backup_not_found", 404)
    return path


def new_backup_name(kind: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"nomax-{stamp}-{kind}.sql"


def backup_kind(filename: str) -> str:
    if filename.endswith("-pre-restore.sql"):
        return "pre-restore"
    if filename.endswith("-uploaded.sql"):
        return "uploaded"
    if filename.endswith("-auto.sql"):
        return "auto"
    return "manual"


def backup_entry(path: Path) -> dict:
    stat = path.stat()
    kind = backup_kind(path.name)
    return {
        "filename": path.name,
        "size": stat.st_size,
        "created_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "kind": kind,
        "kind_label": KIND_LABELS[kind],
    }


def database_url() -> str:
    url = make_url(settings.DATABASE_URL)
    if url.get_backend_name() != "postgresql":
        raise AppError("backup_unavailable", "backup_requires_postgresql", 503)
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


async def run_pg(command: list[str], *, timeout: int | None = None) -> tuple[int, bytes, bytes]:
    env = os.environ.copy()
    env.setdefault("PGCONNECT_TIMEOUT", "10")
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
    except FileNotFoundError as exc:
        raise AppError("backup_unavailable", "backup_tools_unavailable", 503) from exc

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout or settings.BACKUP_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        process.kill()
        await process.wait()
        raise AppError("backup_timeout", "backup_operation_timeout", 504) from exc
    return process.returncode, stdout, stderr


def command_error(action: str, stderr: bytes) -> None:
    logger.error("%s failed: %s", action, stderr.decode("utf-8", "replace")[-2000:])


def plain_dump_is_compatible(path: Path) -> bool:
    """Reject unrelated uploads and keep the dump runnable on PostgreSQL 16.

    pg_dump 17 emits a few session settings/meta-commands that PostgreSQL 16
    and older psql clients do not understand. They are not part of the schema
    or data, so they are removed from the downloaded SQL file.
    """
    temporary = path.with_name(f".{path.name}.compatible")
    markers = {
        "pg_dump": False,
        "alembic": False,
        "users": False,
        "businesses": False,
        "users_data": False,
        "businesses_data": False,
    }
    removed_prefixes = (
        "SET transaction_timeout = ",
        "\\restrict ",
        "\\unrestrict ",
    )
    try:
        with path.open("r", encoding="utf-8", errors="replace") as source, temporary.open(
            "w", encoding="utf-8"
        ) as destination:
            for line in source:
                if line.startswith(removed_prefixes):
                    continue
                if "PostgreSQL database dump" in line:
                    markers["pg_dump"] = True
                elif "CREATE TABLE public.alembic_version" in line:
                    markers["alembic"] = True
                elif "CREATE TABLE public.users" in line:
                    markers["users"] = True
                elif "CREATE TABLE public.businesses" in line:
                    markers["businesses"] = True
                elif "COPY public.users " in line:
                    markers["users_data"] = True
                elif "COPY public.businesses " in line:
                    markers["businesses_data"] = True
                destination.write(line)
        if not all(markers.values()):
            return False
        temporary.chmod(0o600)
        temporary.replace(path)
        return True
    finally:
        temporary.unlink(missing_ok=True)


async def create_backup(kind: str = "manual") -> dict:
    directory = backup_dir()
    filename = new_backup_name(kind)
    destination = directory / filename
    temporary = directory / f".{filename}.part"
    command = [
        "pg_dump",
        "--format=plain",
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-acl",
        "--no-password",
        "--dbname",
        database_url(),
        "--file",
        str(temporary),
    ]

    try:
        returncode, _, stderr = await run_pg(command)
        if returncode != 0 or not temporary.is_file() or temporary.stat().st_size == 0:
            command_error("pg_dump", stderr)
            raise AppError("backup_failed", "backup_failed", 500)
        if not plain_dump_is_compatible(temporary):
            raise AppError("backup_failed", "backup_failed", 500)
        temporary.replace(destination)
        return backup_entry(destination)
    finally:
        temporary.unlink(missing_ok=True)


async def validate_dump(path: Path) -> None:
    if not plain_dump_is_compatible(path):
        raise AppError("invalid_backup_file", "invalid_backup_file", 422)


def s3_prefix() -> str:
    raw = (settings.BACKUP_S3_PREFIX or "").strip().strip("/")
    if not raw:
        return ""
    parts = raw.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise AppError("backup_unavailable", "invalid_backup_prefix", 503)
    return "/".join(parts) + "/"


def s3_bucket() -> str:
    return settings.BACKUP_S3_BUCKET or settings.S3_BUCKET_PRIVATE


def s3_configured() -> bool:
    return storage.storage_configured() and bool(s3_bucket())


def remote_key(filename: str) -> str:
    return f"{s3_prefix()}{filename}.gz"


def _list_remote_sync() -> dict[str, dict]:
    client = storage.s3_client()
    prefix = s3_prefix()
    found: dict[str, dict] = {}
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=s3_bucket(), Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj.get("Key", "")
            name = key[len(prefix) :]
            if not REMOTE_NAME_RE.fullmatch(name):
                continue
            found[name] = {
                "key": key,
                "size": obj.get("Size", 0),
                "last_modified": obj["LastModified"].isoformat()
                if obj.get("LastModified")
                else None,
            }
    return found


async def list_remote_backups() -> dict[str, dict]:
    return await run_in_threadpool(_list_remote_sync)


def _delete_remote_sync(keys: list[str]) -> None:
    client = storage.s3_client()
    for index in range(0, len(keys), 1000):
        batch = [{"Key": key} for key in keys[index : index + 1000]]
        client.delete_objects(Bucket=s3_bucket(), Delete={"Objects": batch})


def _prune_remote_sync(keep: int) -> list[str]:
    items = _list_remote_sync()
    # Backup names start with a UTC timestamp, so descending filename order is
    # also newest-first and does not depend on S3 LastModified clock skew.
    ordered = sorted(items, reverse=True)
    stale = ordered[keep:]
    if stale:
        _delete_remote_sync([items[name]["key"] for name in stale])
    return stale


async def prune_remote_backups() -> list[str]:
    return await run_in_threadpool(_prune_remote_sync, settings.BACKUP_KEEP_REMOTE)


def _gzip_backup_sync(path: Path, destination: Path) -> tuple[int, str]:
    sha256 = hashlib.sha256()
    with path.open("rb") as source, destination.open("wb") as raw:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw,
            compresslevel=6,
            mtime=0,
        ) as compressed:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                sha256.update(chunk)
                compressed.write(chunk)
    destination.chmod(0o600)
    return destination.stat().st_size, sha256.hexdigest()


def _upload_compressed_sync(path: Path, key: str) -> int:
    temporary = path.with_name(f".{path.name}.gz.part")
    try:
        compressed_size, sha256 = _gzip_backup_sync(path, temporary)
        storage.s3_client().upload_file(
            str(temporary),
            s3_bucket(),
            key,
            ExtraArgs={
                "ContentType": "application/gzip",
                "ContentDisposition": f'attachment; filename="{path.name}.gz"',
                "Metadata": {
                    "original-filename": path.name,
                    "sha256": sha256,
                },
            },
        )
        return compressed_size
    finally:
        temporary.unlink(missing_ok=True)


async def upload_backup(
    path: Path,
    kind: str,
    *,
    known_remote: set[str] | None = None,
    prune: bool = True,
) -> dict:
    """Gzip one local backup and put it in the private ArvanCloud bucket.

    Upload failures are reported in the result instead of failing the local
    backup operation; the dashboard can retry with the sync action.
    """
    if kind not in CLOUD_KINDS:
        return {"status": "skipped", "reason": "kind_not_archived"}
    if not s3_configured():
        return {"status": "not_configured"}
    key = remote_key(path.name)
    if known_remote is not None and key in known_remote:
        return {"status": "already_uploaded", "key": key}

    try:
        compressed_size = await run_in_threadpool(_upload_compressed_sync, path, key)
        pruned = await prune_remote_backups() if prune else []
    except (BotoCoreError, ClientError, OSError) as exc:
        logger.exception("Could not archive backup %s in S3", path.name)
        return {"status": "failed", "error": type(exc).__name__}
    except Exception as exc:  # noqa: BLE001 - never lose the local backup
        logger.exception("Unexpected backup upload failure")
        return {"status": "failed", "error": type(exc).__name__}

    return {
        "status": "uploaded",
        "key": key,
        "size": compressed_size,
        "pruned": pruned,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }


def _local_cloud_backups() -> list[Path]:
    directory = backup_dir()
    return sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file()
            and BACKUP_NAME_RE.fullmatch(path.name)
            and backup_kind(path.name) in CLOUD_KINDS
        ),
        key=lambda path: path.name,
    )


async def sync_backups() -> dict:
    """Upload every local manual/automatic backup missing from S3."""
    if not s3_configured():
        return {
            "configured": False,
            "uploaded": [],
            "failed": [],
            "pruned": [],
        }

    remote = await list_remote_backups()
    remote_object_keys = {
        item.get("key", "") for item in remote.values() if item.get("key")
    }
    uploaded: list[dict] = []
    failed: list[dict] = []
    for path in _local_cloud_backups():
        remote_name = f"{path.name}.gz"
        if remote_name in remote:
            continue
        result = await upload_backup(
            path,
            backup_kind(path.name),
            known_remote=remote_object_keys,
            prune=False,
        )
        if result["status"] == "uploaded":
            uploaded.append({"filename": path.name, **result})
            remote[remote_name] = {"key": remote_key(path.name)}
            remote_object_keys.add(result["key"])
        else:
            failed.append({"filename": path.name, **result})

    pruned = await prune_remote_backups()
    return {
        "configured": True,
        "uploaded": uploaded,
        "failed": failed,
        "pruned": pruned,
    }


async def remote_snapshot(timeout: float = 6.0) -> dict:
    if not s3_configured():
        return {"configured": False, "items": {}, "error": None}
    try:
        items = await asyncio.wait_for(list_remote_backups(), timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - local list must stay usable
        logger.warning("Could not list S3 backups: %s", exc)
        return {"configured": True, "items": {}, "error": type(exc).__name__}
    return {"configured": True, "items": items, "error": None}


def remote_info(snapshot: dict | None = None) -> dict:
    snapshot = snapshot or {"configured": s3_configured(), "error": None}
    return {
        "configured": bool(snapshot.get("configured")),
        "bucket": s3_bucket() if snapshot.get("configured") else "",
        "prefix": s3_prefix(),
        "keep_remote": settings.BACKUP_KEEP_REMOTE,
        "daily_enabled": settings.BACKUP_DAILY_ENABLED,
        "daily_time": f"{settings.BACKUP_DAILY_HOUR:02d}:{settings.BACKUP_DAILY_MINUTE:02d}",
        "daily_timezone": settings.BACKUP_TIMEZONE,
        "error": snapshot.get("error"),
    }
