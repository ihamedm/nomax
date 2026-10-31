"""Superadmin database backup and restore.

Local backups are portable PostgreSQL SQL dumps in ``BACKUP_DIR``. Manual and
automatic dumps are also gzipped into the private ArvanCloud S3 bucket. Restores
are always preceded by a safety backup and run in a single transaction, so a
failed restore leaves the current database untouched.
"""

import logging

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import require_superadmin
from app.core.errors import AppError
from app.db.session import AsyncSessionLocal, engine, get_db
from app.models.admin import AuditLog
from app.models.user import User
from app.services import database_backups as backups

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/backups", tags=["admin-backups"])


async def _audit_restore(actor_id, source: str, safety_backup: str) -> None:
    try:
        async with AsyncSessionLocal() as session:
            session.add(
                AuditLog(
                    actor_id=actor_id,
                    action="database.restore",
                    entity_type="database",
                    entity_id=source,
                    after={"safety_backup": safety_backup},
                )
            )
            await session.commit()
    except Exception:  # noqa: BLE001 - restore already succeeded
        logger.exception("Could not write restore audit log")


async def _restore_from(path, actor_id, session: AsyncSession) -> dict:
    await backups.validate_dump(path)

    async with backups.BACKUP_LOCK:
        safety = await backups.create_backup("pre-restore")

        # End the request transaction before DDL so it cannot hold ACCESS
        # SHARE locks that block pg_restore's DROP TABLE statements.
        await session.rollback()
        command = [
            "psql",
            "--no-password",
            "--quiet",
            "--dbname",
            backups.database_url(),
            "--single-transaction",
            "--set",
            "ON_ERROR_STOP=1",
            "--file",
            str(path),
        ]
        returncode, _, stderr = await backups.run_pg(command)
        if returncode != 0:
            backups.command_error("psql restore", stderr)
            raise AppError(
                "restore_failed",
                "restore_failed",
                500,
                {"safety_backup": safety["filename"]},
            )

        # Old pooled connections still carry prepared statements for the
        # replaced schema. Recreate the pool before serving more requests.
        await engine.dispose()
        await _audit_restore(actor_id, path.name, safety["filename"])
        return {
            "restored": path.name,
            "safety_backup": safety["filename"],
            "restart_recommended": True,
        }


@router.get("")
async def list_backups(actor: User = Depends(require_superadmin)) -> dict:
    del actor
    directory = backups.backup_dir()
    items = sorted(
        (
            backups.backup_entry(path)
            for path in directory.iterdir()
            if path.is_file() and backups.BACKUP_NAME_RE.fullmatch(path.name)
        ),
        key=lambda item: item["created_at"],
        reverse=True,
    )
    snapshot = await backups.remote_snapshot()
    remote_keys = set(snapshot.get("items", {}))
    for item in items:
        item["remote"] = f"{item['filename']}.gz" in remote_keys
    return {
        "data": {
            "items": items,
            "max_upload_mb": settings.BACKUP_MAX_UPLOAD_MB,
            "restart_recommended": True,
            "s3": backups.remote_info(snapshot),
        }
    }


@router.post("")
async def create_backup(actor: User = Depends(require_superadmin)) -> dict:
    del actor
    async with backups.BACKUP_LOCK:
        entry = await backups.create_backup("manual")
        upload = await backups.upload_backup(
            backups.backup_dir() / entry["filename"], "manual"
        )
        entry["remote"] = upload["status"] == "uploaded"
        entry["upload"] = upload
        return {"data": entry}


@router.post("/sync-s3")
async def sync_s3(actor: User = Depends(require_superadmin)) -> dict:
    del actor
    if not backups.s3_configured():
        raise AppError("backup_s3_not_configured", "backup_s3_not_configured", 503)
    async with backups.BACKUP_LOCK:
        return {"data": await backups.sync_backups()}


@router.get("/{filename}/download")
async def download_backup(
    filename: str,
    actor: User = Depends(require_superadmin),
) -> FileResponse:
    del actor
    path = backups.backup_path(filename)
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=path.name,
        headers={"Cache-Control": "no-store"},
    )


@router.delete("/{filename}")
async def delete_backup(
    filename: str,
    actor: User = Depends(require_superadmin),
) -> dict:
    del actor
    async with backups.BACKUP_LOCK:
        path = backups.backup_path(filename)
        path.unlink()
    return {"data": {"filename": filename, "deleted": True}}


@router.post("/{filename}/restore")
async def restore_saved_backup(
    filename: str,
    confirm: str = Form(...),
    actor: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if confirm.strip() != "RESTORE":
        raise AppError("restore_confirmation_required", "restore_confirmation_required", 422)
    path = backups.backup_path(filename)
    return {"data": await _restore_from(path, actor.id, session)}


@router.post("/restore-upload")
async def restore_uploaded_backup(
    file: UploadFile = File(...),
    confirm: str = Form(...),
    actor: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if confirm.strip() != "RESTORE":
        raise AppError("restore_confirmation_required", "restore_confirmation_required", 422)

    directory = backups.backup_dir()
    destination = directory / backups.new_backup_name("uploaded")
    temporary = directory / f".{destination.name}.part"
    maximum = settings.BACKUP_MAX_UPLOAD_MB * 1024 * 1024
    total = 0
    try:
        with temporary.open("wb") as handle:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > maximum:
                    raise AppError("backup_too_large", "backup_too_large", 413)
                handle.write(chunk)
        await file.close()
        if total == 0:
            raise AppError("invalid_backup_file", "invalid_backup_file", 422)
        temporary.chmod(0o600)
        temporary.replace(destination)
        return {"data": await _restore_from(destination, actor.id, session)}
    except Exception:
        temporary.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise
