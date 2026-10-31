import json
import os
import shutil
import tempfile

import pytest_asyncio
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.redis import get_redis
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app import models  # noqa: F401  (register every table on Base.metadata)
from app.models.user import User, UserRole
from app.services.otp_service import OtpService
from app.services.sms_provider import ConsoleSmsProvider


_TEST_DIR = tempfile.mkdtemp(prefix="nomax-tests-")
_TEST_DB_PATH = os.path.join(_TEST_DIR, "test.db")

engine = create_async_engine(f"sqlite+aiosqlite:///{_TEST_DB_PATH}")
TestingSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict = {}
        self.sets: dict = {}
        self.ttls: dict = {}
        self.zsets: dict = {}
        self.streams: dict = {}
        self.stream_seq = 0

    async def ping(self) -> bool:
        return True

    async def get(self, key: str):
        return self.data.get(key)

    async def set(self, key: str, value, ex: int | None = None, px: int | None = None, nx: bool = False, xx: bool = False) -> bool:
        self.data[key] = value
        if ex is not None:
            self.ttls[key] = ex
        return True

    async def delete(self, *keys):
        count = 0
        for key in keys:
            if key in self.data:
                del self.data[key]
                count += 1
        return count

    async def incr(self, key: str) -> int:
        value = int(self.data.get(key, 0)) + 1
        self.data[key] = value
        return value

    async def expire(self, key: str, ttl: int) -> int:
        self.ttls[key] = ttl
        return 1

    async def ttl(self, key: str) -> int:
        return int(self.ttls.get(key, -2))

    async def smembers(self, key: str):
        return set(self.sets.get(key, set()))

    async def sadd(self, key: str, member: str) -> int:
        bucket = self.sets.setdefault(key, set())
        if member in bucket:
            return 0
        bucket.add(member)
        return 1

    async def sismember(self, key: str, member: str) -> bool:
        return member in self.sets.get(key, set())

    async def zadd(self, key: str, mapping: dict) -> int:
        bucket = self.zsets.setdefault(key, {})
        added = 0
        for member, score in mapping.items():
            if member not in bucket:
                added += 1
            bucket[member] = float(score)
        return added

    async def zrem(self, key: str, *members) -> int:
        bucket = self.zsets.setdefault(key, {})
        removed = 0
        for member in members:
            if member in bucket:
                del bucket[member]
                removed += 1
        return removed

    async def zrangebyscore(
        self, key: str, minimum, maximum, start: int = 0, num: int | None = None
    ):
        bucket = self.zsets.setdefault(key, {})
        lo = float("-inf") if minimum == "-inf" else float(minimum)
        hi = float("inf") if maximum == "+inf" else float(maximum)
        rows = sorted(
            (member for member, score in bucket.items() if lo <= score <= hi),
            key=lambda member: (bucket[member], member),
        )
        rows = rows[start:]
        return rows[:num] if num is not None else rows

    async def xadd(self, key: str, fields: dict, maxlen=None, approximate=True) -> str:
        self.stream_seq += 1
        message_id = f"{self.stream_seq}-0"
        self.streams.setdefault(key, []).append((message_id, dict(fields)))
        return message_id

    async def xgroup_create(self, key: str, group: str, id: str = "0", mkstream=False) -> bool:
        self.sets.setdefault(f"group:{key}:{group}", set())
        return True

    async def xreadgroup(self, group, consumer, streams: dict, count=None, block=None):
        key = next(iter(streams))
        pending = self.streams.setdefault(key, [])
        rows = pending[:count] if count else list(pending)
        if not rows:
            return []
        del pending[: len(rows)]
        return [(key, rows)]

    async def xack(self, key: str, group: str, *message_ids) -> int:
        return len(message_ids)

    async def scan_iter(self, match: str | None = None):
        import fnmatch

        for key in list(self.data):
            if match is None or fnmatch.fnmatch(key, match):
                yield key


_fake_redis_instance = FakeRedis()


@pytest_asyncio.fixture
async def fake_redis():
    return _fake_redis_instance


async def override_get_db():
    async with TestingSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


async def override_get_redis():
    return _fake_redis_instance


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_redis] = override_get_redis


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    shutil.rmtree(_TEST_DIR, ignore_errors=True)


@pytest_asyncio.fixture(autouse=True)
async def _clean_state(db_engine):
    """Give every test a clean database and a clean fake Redis."""
    async with engine.begin() as connection:
        for table in (
            "notification_deliveries",
            "notifications",
            "device_tokens",
            "scheduled_jobs",
            "quote_dispatch_runs",
            "quote_deliveries",
            "search_logs",
            "offers",
            "quote_requests",
            "reviews",
            "bookmarks",
            "business_images",
            "ads",
        ):
            await connection.execute(sa.text(f"DELETE FROM {table}"))
        await connection.execute(sa.text("DELETE FROM sms_logs"))
        await connection.execute(sa.text("DELETE FROM admin_audit_logs"))
        await connection.execute(sa.text("DELETE FROM app_settings"))
        await connection.execute(sa.text("DELETE FROM businesses"))
        await connection.execute(sa.text("DELETE FROM users"))
        await connection.execute(sa.text("DELETE FROM subcategories"))
        await connection.execute(sa.text("DELETE FROM categories"))
        # Legacy tests assume requests dispatch immediately. The explicit night
        # tests override this row; production defaults remain 06:00–21:00 Tehran.
        dispatch_settings = {
            "enabled": True,
            "day_start_hour": 0,
            "day_end_hour": 24,
        }
        await connection.execute(
            sa.text(
                "INSERT INTO app_settings (key, value, created_at, updated_at) "
                "VALUES ('quote_dispatch', :value, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"value": json.dumps(dispatch_settings)},
        )
    _fake_redis_instance.data.clear()
    _fake_redis_instance.sets.clear()
    _fake_redis_instance.ttls.clear()
    _fake_redis_instance.zsets.clear()
    _fake_redis_instance.streams.clear()
    _fake_redis_instance.stream_seq = 0
    yield


@pytest_asyncio.fixture
async def set_dispatch_settings(db_session):
    """Update the quote strategy row for a test and return the saved value."""

    async def _set(**overrides):
        from app.models.setting import AppSetting
        from app.services.quote_dispatch_settings import DEFAULT_QUOTE_DISPATCH

        row = await db_session.get(AppSetting, "quote_dispatch")
        value = {
            **DEFAULT_QUOTE_DISPATCH,
            "day_start_hour": 0,
            "day_end_hour": 24,
            **overrides,
        }
        if row is None:
            db_session.add(AppSetting(key="quote_dispatch", value=value))
        else:
            row.value = value
        await db_session.commit()
        return value

    return _set


@pytest_asyncio.fixture
async def db_session():
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def otp_service():
    return OtpService(_fake_redis_instance, ConsoleSmsProvider())


@pytest_asyncio.fixture
async def create_user():
    async def _create(
        phone: str,
        role: UserRole = UserRole.CUSTOMER,
        permissions: list[str] | None = None,
        full_name: str | None = None,
        deleted: bool = False,
    ) -> User:
        from datetime import datetime, timezone

        async with TestingSessionLocal() as session:
            user = User(
                phone=phone,
                role=role,
                permissions=permissions or [],
                full_name=full_name,
                is_phone_verified=True,
                deleted_at=datetime.now(timezone.utc) if deleted else None,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    return _create


@pytest_asyncio.fixture
async def client(db_engine):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
