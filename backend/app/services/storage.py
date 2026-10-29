import mimetypes
import time
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from starlette.concurrency import run_in_threadpool

from app.core.config import settings

UPLOAD_PREFIX = "uploads"


class StorageNotConfigured(RuntimeError):
    pass


class StorageValidationError(ValueError):
    pass


def storage_configured() -> bool:
    return bool(
        settings.S3_ENDPOINT_URL and settings.S3_ACCESS_KEY and settings.S3_SECRET_KEY
    )


def bucket_name(bucket: str) -> str:
    if bucket == "public":
        return settings.S3_BUCKET_PUBLIC
    if bucket == "private":
        return settings.S3_BUCKET_PRIVATE
    raise StorageValidationError("invalid_bucket")


@lru_cache(maxsize=1)
def _client():
    if not storage_configured():
        raise StorageNotConfigured("storage_not_configured")
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        region_name=settings.S3_REGION,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": settings.S3_ADDRESSING_STYLE},
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=5,
            read_timeout=15,
        ),
    )


def upload_dir() -> Path:
    path = Path(settings.UPLOAD_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def public_url(key: str) -> str:
    encoded = quote(key, safe="/")
    if settings.S3_PUBLIC_URL:
        return f"{settings.S3_PUBLIC_URL.rstrip('/')}/{encoded}"
    endpoint = settings.S3_ENDPOINT_URL.rstrip("/")
    if settings.S3_ADDRESSING_STYLE == "path":
        return f"{endpoint}/{settings.S3_BUCKET_PUBLIC}/{encoded}"
    host = endpoint.split("://", 1)[-1]
    scheme = endpoint.split("://", 1)[0] if "://" in endpoint else "https"
    return f"{scheme}://{settings.S3_BUCKET_PUBLIC}.{host}/{encoded}"


def normalize_prefix(prefix: str | None) -> str:
    raw = (prefix or "").strip().strip("/")
    if not raw:
        return ""
    parts = raw.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise StorageValidationError("invalid_prefix")
    return "/".join(parts) + "/"


def safe_name(name: str) -> str:
    value = (name or "").strip().replace("\\", "/").split("/")[-1]
    if value in ("", ".", ".."):
        raise StorageValidationError("invalid_name")
    return value


def user_upload_prefix(
    kind: str, user_id: uuid.UUID | str, *, now: datetime | None = None
) -> str:
    """Shard user uploads by kind, owner and month.

    Example: ``uploads/businesses/<user-id>/2026/10/``. This keeps the bucket
    root and the local upload directory readable instead of collecting every
    user's files in one folder.
    """
    bucket_kind = safe_name((kind or "misc").replace("\\", "/"))
    if bucket_kind in ("", ".", ".."):
        raise StorageValidationError("invalid_kind")
    moment = now or datetime.now(timezone.utc)
    return f"{UPLOAD_PREFIX}/{bucket_kind}/{user_id}/{moment:%Y/%m}/"


def _save_upload_sync(data: bytes, filename: str, prefix: str) -> str:
    ext = Path(filename).suffix.lower() or ".bin"
    key = f"{normalize_prefix(prefix)}{uuid.uuid4().hex}{ext}"
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return _store_bytes_sync(key, data, content_type)["url"]


def _store_bytes_sync(key: str, data: bytes, content_type: str) -> dict:
    """Write one object locally or to S3 and return its key/url/size."""
    if not storage_configured():
        # Local URLs are mounted at /uploads, so strip the duplicated key prefix.
        local_key = key[len(UPLOAD_PREFIX) + 1 :] if key.startswith(f"{UPLOAD_PREFIX}/") else key
        path = upload_dir() / local_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return {
            "key": key,
            "url": f"/uploads/{quote(local_key, safe='/')}",
            "size": len(data),
        }

    extra = {"ACL": "public-read"} if settings.S3_PUBLIC_READ_ACL else {}
    _client().put_object(
        Bucket=settings.S3_BUCKET_PUBLIC,
        Key=key,
        Body=data,
        ContentType=content_type,
        **extra,
    )
    return {"key": key, "url": public_url(key), "size": len(data)}


async def save_upload(
    data: bytes, filename: str, *, prefix: str = UPLOAD_PREFIX
) -> str:
    return await run_in_threadpool(_save_upload_sync, data, filename, prefix)


def _save_image_bundle_sync(
    main: bytes, variants: dict[str, bytes], prefix: str
) -> dict:
    normalized = normalize_prefix(prefix)
    stem = uuid.uuid4().hex
    main_item = _store_bytes_sync(f"{normalized}{stem}.jpg", main, "image/jpeg")
    variant_items: dict[str, dict] = {}
    for name, data in variants.items():
        variant_items[name] = _store_bytes_sync(
            f"{normalized}{stem}_{safe_name(name)}.jpg", data, "image/jpeg"
        )
    return {
        **main_item,
        "variants": variant_items,
    }


async def save_image_bundle(
    main: bytes, variants: dict[str, bytes], *, prefix: str
) -> dict:
    """Save a processed main image plus its named crops in one UUID group."""
    return await run_in_threadpool(_save_image_bundle_sync, main, variants, prefix)


def _list_entries_sync(bucket: str, prefix: str) -> list[dict]:
    target = bucket_name(bucket)
    response = _client().list_objects_v2(Bucket=target, Prefix=prefix, Delimiter="/")
    items: list[dict] = []

    for common in response.get("CommonPrefixes", []):
        key = common["Prefix"]
        name = key[len(prefix):].rstrip("/")
        if name:
            items.append({"type": "folder", "name": name, "key": key, "size": 0})

    for obj in response.get("Contents", []):
        key = obj["Key"]
        if key == prefix:
            continue
        name = key[len(prefix):]
        if not name or name.endswith("/"):
            continue
        items.append(
            {
                "type": "file",
                "name": name,
                "key": key,
                "size": obj.get("Size", 0),
                "last_modified": obj["LastModified"].isoformat()
                if obj.get("LastModified")
                else None,
            }
        )

    items.sort(key=lambda item: (item["type"] != "folder", item["name"].lower()))
    return items


async def list_entries(bucket: str, prefix: str | None = None) -> dict:
    normalized = normalize_prefix(prefix)
    items = await run_in_threadpool(_list_entries_sync, bucket, normalized)
    return {"bucket": bucket, "prefix": normalized, "items": items}


def _folder_key(name: str) -> str:
    return f"{safe_name(name)}/"


def _create_folder_sync(bucket: str, prefix: str, name: str) -> dict:
    target = bucket_name(bucket)
    key = f"{prefix}{_folder_key(name)}"
    _client().put_object(Bucket=target, Key=key, Body=b"", ContentType="application/x-directory")
    return {"type": "folder", "name": name.strip(), "key": key, "size": 0}



async def create_folder(bucket: str, prefix: str | None, name: str) -> dict:
    normalized = normalize_prefix(prefix)
    return await run_in_threadpool(_create_folder_sync, bucket, normalized, name)


def _upload_file_sync(
    bucket: str, prefix: str, filename: str, data: bytes, content_type: str
) -> dict:
    target = bucket_name(bucket)
    key = f"{prefix}{safe_name(filename)}"
    extra = {"ACL": "public-read"} if bucket == "public" and settings.S3_PUBLIC_READ_ACL else {}
    _client().put_object(
        Bucket=target,
        Key=key,
        Body=data,
        ContentType=content_type or "application/octet-stream",
        **extra,
    )
    return {
        "type": "file",
        "name": safe_name(filename),
        "key": key,
        "size": len(data),
    }


async def upload_file(
    bucket: str,
    prefix: str | None,
    filename: str,
    data: bytes,
    content_type: str | None,
) -> dict:
    normalized = normalize_prefix(prefix)
    guessed = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return await run_in_threadpool(
        _upload_file_sync,
        bucket,
        normalized,
        filename,
        data,
        content_type or guessed,
    )


def _delete_entry_sync(bucket: str, key: str) -> None:
    target = bucket_name(bucket)
    client = _client()
    if not key.endswith("/"):
        client.delete_object(Bucket=target, Key=key)
        return

    paginator = client.get_paginator("list_objects_v2")
    batch: list[dict] = []
    for page in paginator.paginate(Bucket=target, Prefix=key):
        for obj in page.get("Contents", []):
            batch.append({"Key": obj["Key"]})
            if len(batch) == 1000:
                client.delete_objects(Bucket=target, Delete={"Objects": batch})
                batch = []
    if batch:
        client.delete_objects(Bucket=target, Delete={"Objects": batch})


async def delete_entry(bucket: str, key: str) -> None:
    if not key or key == "/":
        raise StorageValidationError("invalid_key")
    await run_in_threadpool(_delete_entry_sync, bucket, key)


def _file_link_sync(bucket: str, key: str) -> dict:
    if not key or key.endswith("/"):
        raise StorageValidationError("invalid_key")
    target = bucket_name(bucket)
    if bucket == "public":
        return {"url": public_url(key), "expires_in": None}
    expires_in = settings.S3_PRESIGN_TTL_SECONDS
    url = _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": target, "Key": key},
        ExpiresIn=expires_in,
    )
    return {"url": url, "expires_in": expires_in}


async def file_link(bucket: str, key: str) -> dict:
    return await run_in_threadpool(_file_link_sync, bucket, key)


_health_cache: tuple[float, str] | None = None


def _health_sync() -> str:
    client = _client()
    for bucket in (settings.S3_BUCKET_PUBLIC, settings.S3_BUCKET_PRIVATE):
        client.list_objects_v2(Bucket=bucket, MaxKeys=1)
    return "ok"


async def health() -> str:
    """Return ok / error / not_configured, cached to avoid hammering S3."""
    global _health_cache
    if not storage_configured():
        return "not_configured"

    now = time.monotonic()
    if _health_cache and now - _health_cache[0] < settings.S3_HEALTHCHECK_TTL_SECONDS:
        return _health_cache[1]

    try:
        status = await run_in_threadpool(_health_sync)
    except (BotoCoreError, ClientError):
        status = "error"
    except Exception:
        status = "error"
    _health_cache = (now, status)
    return status


def reset_health_cache() -> None:
    global _health_cache
    _health_cache = None
