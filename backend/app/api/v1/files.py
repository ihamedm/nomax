from typing import Literal

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.core.deps import require_permissions
from app.core.errors import AppError
from app.models.user import User
from app.services import storage

router = APIRouter(tags=["storage"])

MAX_FILE_BYTES = 20 * 1024 * 1024


async def _guarded(coro):
    try:
        return await coro
    except storage.StorageNotConfigured:
        raise AppError("storage_not_configured", "storage_not_configured", 503)
    except storage.StorageValidationError as exc:
        raise AppError("validation_error", str(exc), 422)
    except ValueError as exc:
        raise AppError("storage_error", "invalid_storage_endpoint", 502, {"detail": str(exc)})
    except (BotoCoreError, ClientError) as exc:
        raise AppError("storage_error", "storage_operation_failed", 502, {"detail": str(exc)})


@router.get("/admin/files")
async def list_files(
    bucket: Literal["public", "private"] = "public",
    prefix: str = Query("", max_length=500),
    actor: User = Depends(require_permissions("storage.manage")),
) -> dict:
    del actor
    return {"data": await _guarded(storage.list_entries(bucket, prefix))}


@router.get("/admin/files/link")
async def file_link(
    bucket: Literal["public", "private"] = "public",
    key: str = Query(..., min_length=1, max_length=1000),
    actor: User = Depends(require_permissions("storage.manage")),
) -> dict:
    del actor
    return {"data": await _guarded(storage.file_link(bucket, key))}


@router.post("/admin/files/folder")
async def create_folder(
    payload: dict,
    actor: User = Depends(require_permissions("storage.manage")),
) -> dict:
    del actor
    return {
        "data": await _guarded(
            storage.create_folder(
                payload.get("bucket") or "public",
                payload.get("prefix") or "",
                payload.get("name") or "",
            )
        )
    }


@router.post("/admin/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    bucket: Literal["public", "private"] = Form("public"),
    prefix: str = Form(""),
    actor: User = Depends(require_permissions("storage.manage")),
) -> dict:
    del actor
    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise AppError("validation_error", "file_too_large", 413)
    return {
        "data": await _guarded(
            storage.upload_file(
                bucket,
                prefix,
                file.filename or "file",
                data,
                file.content_type,
            )
        )
    }


@router.delete("/admin/files")
async def delete_file(
    bucket: Literal["public", "private"] = "public",
    key: str = Query(..., min_length=1, max_length=1000),
    actor: User = Depends(require_permissions("storage.manage")),
) -> dict:
    del actor
    await _guarded(storage.delete_entry(bucket, key))
    return {"data": {"key": key, "deleted": True}}
