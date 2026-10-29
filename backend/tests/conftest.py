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
            "offers",
            "quote_requests",
            "reviews",
            "bookmarks",
            "ads",
        ):
            await connection.execute(sa.text(f"DELETE FROM {table}"))
        await connection.execute(sa.text("DELETE FROM sms_logs"))
        await connection.execute(sa.text("DELETE FROM admin_audit_logs"))
        await connection.execute(sa.text("DELETE FROM businesses"))
        await connection.execute(sa.text("DELETE FROM users"))
        await connection.execute(sa.text("DELETE FROM subcategories"))
        await connection.execute(sa.text("DELETE FROM categories"))
    _fake_redis_instance.data.clear()
    _fake_redis_instance.sets.clear()
    _fake_redis_instance.ttls.clear()
    yield


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
