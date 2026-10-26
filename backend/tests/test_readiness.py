import pytest


@pytest.mark.asyncio
async def test_ready_reports_database_and_redis(client):
    response = await client.get("/ready")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "ok"
    assert body["checks"] == {"database": "ok", "redis": "ok"}


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
