import pytest


@pytest.mark.asyncio
async def test_ready_reports_database_and_redis(client):
    response = await client.get("/ready")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "ok"
    assert body["checks"] == {"database": "ok", "redis": "ok", "storage": "not_configured"}


@pytest.mark.asyncio
async def test_ready_is_503_when_redis_is_down(client, fake_redis, monkeypatch):
    async def broken_ping():
        raise ConnectionError("redis down")

    monkeypatch.setattr(fake_redis, "ping", broken_ping)

    response = await client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "not_ready"
    assert body["data"]["checks"]["database"] == "ok"
    assert body["data"]["checks"]["redis"] == "error"


@pytest.mark.asyncio
async def test_ready_is_503_when_storage_is_down(client, monkeypatch):
    async def broken_storage():
        return "error"

    monkeypatch.setattr("app.api.v1.health.storage_health", broken_storage)

    response = await client.get("/ready")
    assert response.status_code == 503
    assert response.json()["data"]["checks"]["storage"] == "error"
