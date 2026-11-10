"""Daily automatic database backup scheduler.

The quote worker calls :func:`run_backup_scheduler` once. A marker file in the
persistent backup volume makes the job idempotent across restarts and ensures a
failed cloud sync is retried without generating duplicate dumps.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import settings
from app.services import database_backups as backups

logger = logging.getLogger("nomax.backup_scheduler")

MARKER_NAME = ".daily-backup.json"
RETRY_SECONDS = 300
IDLE_SECONDS = 60


def _timezone() -> ZoneInfo:
    try:
        return ZoneInfo(settings.BACKUP_TIMEZONE)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown BACKUP_TIMEZONE %r; using UTC", settings.BACKUP_TIMEZONE)
        return ZoneInfo("UTC")


def _marker_path() -> Path:
    return backups.backup_dir() / MARKER_NAME


def _read_marker() -> dict:
    path = _marker_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_marker(data: dict) -> None:
    path = _marker_path()
    temporary = path.with_name(f".{MARKER_NAME}.part")
    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def _schedule_time() -> time:
    return time(hour=settings.BACKUP_DAILY_HOUR, minute=settings.BACKUP_DAILY_MINUTE)


async def run_daily_backup(now: datetime | None = None) -> dict:
    """Create and archive one automatic dump when the daily slot is due."""
    if not settings.BACKUP_DAILY_ENABLED:
        return {"status": "disabled"}

    local_now = (now or datetime.now(timezone.utc)).astimezone(_timezone())
    if local_now.time() < _schedule_time():
        return {"status": "not_due"}

    today = local_now.date().isoformat()
    marker = _read_marker()
    if marker.get("date") == today and marker.get("cloud_done"):
        return {"status": "already_done", "filename": marker.get("filename")}

    async with backups.BACKUP_LOCK:
        marker = _read_marker()

        if marker.get("date") == today:
            # The local dump exists but the previous S3 sync failed. Retry only
            # the upload so the day never gets two automatic dumps.
            filename = marker.get("filename")
            if not filename or not (backups.backup_dir() / filename).is_file():
                return {"status": "marker_missing_backup", "filename": filename}
            cloud = await backups.sync_backups()
            marker["cloud_done"] = not cloud["failed"]
            marker["cloud"] = cloud
            marker["updated_at"] = datetime.now(timezone.utc).isoformat()
            _write_marker(marker)
            return {"status": "synced", "filename": filename, "cloud": cloud}

        entry = await backups.create_backup("auto")
        marker = {
            "date": today,
            "filename": entry["filename"],
            "created_at": entry["created_at"],
            "cloud_done": False,
        }
        _write_marker(marker)

        cloud = await backups.sync_backups()
        marker["cloud_done"] = not cloud["failed"]
        marker["cloud"] = cloud
        marker["updated_at"] = datetime.now(timezone.utc).isoformat()
        _write_marker(marker)
        logger.info(
            "Daily database backup %s created (%s uploads, %s failures)",
            entry["filename"],
            len(cloud["uploaded"]),
            len(cloud["failed"]),
        )
        return {"status": "created", "filename": entry["filename"], "cloud": cloud}


async def run_backup_scheduler() -> None:
    """Sleep between schedule checks; retry sooner after a failed attempt."""
    logger.info(
        "daily database backup scheduler enabled for %02d:%02d %s",
        settings.BACKUP_DAILY_HOUR,
        settings.BACKUP_DAILY_MINUTE,
        settings.BACKUP_TIMEZONE,
    )
    while True:
        delay = IDLE_SECONDS
        try:
            result = await run_daily_backup()
            cloud = result.get("cloud")
            if cloud and cloud.get("failed"):
                delay = RETRY_SECONDS
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - worker must survive a bad backup run
            logger.exception("Daily database backup failed; will retry")
            delay = RETRY_SECONDS
        await asyncio.sleep(delay)
