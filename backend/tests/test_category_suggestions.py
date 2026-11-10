import pytest
import sqlalchemy as sa

from app.core.config import settings
from app.core.security import create_access_token
from app.db.seed import seed_categories
from app.models.category import Category, Subcategory
from app.models.user import UserRole
from app.services import category_suggestions


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


async def _catalog(db_session):
    await seed_categories(db_session)
    await db_session.commit()
    categories = {
        row.slug: row
        for row in (await db_session.execute(sa.select(Category))).scalars().all()
    }
    subcategories = {
        row.slug: row
        for row in (await db_session.execute(sa.select(Subcategory))).scalars().all()
    }
    return categories, subcategories


@pytest.mark.asyncio
async def test_suggestion_requires_login(client):
    response = await client.post(
        "/api/v1/categories/suggest",
        json={"title": "کافه تست", "description": "قهوه و کیک و صبحانه"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth_unauthorized"


@pytest.mark.asyncio
async def test_suggestion_is_disabled_without_a_sidecar(client, create_user, monkeypatch):
    user = await create_user("09150000031")
    monkeypatch.setattr(settings, "LAYA_ENABLED", False)

    response = await client.post(
        "/api/v1/categories/suggest",
        json={"title": "کافه تست", "description": "قهوه و کیک و صبحانه"},
        headers=auth(user),
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "disabled"
    assert body["suggestions"] == []


@pytest.mark.asyncio
async def test_rule_layer_picks_clear_persian_business_without_laya(
    client, db_session, create_user, monkeypatch
):
    await _catalog(db_session)
    user = await create_user("09150000032")
    monkeypatch.setattr(settings, "LAYA_ENABLED", True)
    calls = []

    async def fake_choice(state, question):
        del state, question
        calls.append(True)
        raise AssertionError("clear alias should not call Laya")

    monkeypatch.setattr(category_suggestions, "_laya_choice", fake_choice)

    response = await client.post(
        "/api/v1/categories/suggest",
        json={
            "title": "رستوران سنتی نومکس",
            "description": "غذای ایرانی و کباب در بهبهان واقع شده است.",
        },
        headers=auth(user),
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "ok"
    suggestion = body["suggestions"][0]
    assert suggestion["category"]["slug"] == "food"
    assert suggestion["subcategory"]["slug"] == "restaurant"
    assert suggestion["category_source"] == "rules"
    assert suggestion["subcategory_source"] == "rules"
    assert suggestion["quality"] == "high"
    assert calls == []


@pytest.mark.asyncio
async def test_laya_fallback_handles_two_stage_choice(
    client, db_session, create_user, monkeypatch
):
    categories, subcategories = await _catalog(db_session)
    food = categories["food"]
    restaurant = subcategories["restaurant"]
    user = await create_user("09150000035")
    monkeypatch.setattr(settings, "LAYA_ENABLED", True)
    monkeypatch.setattr(settings, "LAYA_BASE_URL", "http://laya.test")
    calls = []

    async def fake_choice(state, question):
        del state
        calls.append(question["instructions"])
        if "دسته اصلی" in question["instructions"]:
            return {
                "type": "choice",
                "choice": str(food.id),
                "probabilities": {str(food.id): 0.91, str(categories["retail"].id): 0.09},
            }
        return {
            "type": "choice",
            "choice": str(restaurant.id),
            "probabilities": {
                str(restaurant.id): 0.84,
                str(subcategories["cafe"].id): 0.16,
            },
        }

    monkeypatch.setattr(category_suggestions, "_laya_choice", fake_choice)

    response = await client.post(
        "/api/v1/categories/suggest",
        json={
            "title": "امداد نومکس",
            "description": "پشتیبانی و رسیدگی به درخواست‌های ویژه",
        },
        headers=auth(user),
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "ok"
    assert body["enabled"] is True
    assert len(calls) == 2
    suggestion = body["suggestions"][0]
    assert suggestion["category"]["slug"] == "food"
    assert suggestion["subcategory"]["slug"] == "restaurant"
    assert suggestion["subcategory"]["standard_tags"]
    assert suggestion["category_source"] == "laya"
    assert suggestion["subcategory_source"] == "laya"
    assert suggestion["quality"] in {"high", "medium"}
    assert 0 < suggestion["confidence"] <= 1


@pytest.mark.asyncio
async def test_ambiguous_category_abstains(
    client, db_session, create_user, monkeypatch
):
    categories, _ = await _catalog(db_session)
    user = await create_user("09150000033")
    monkeypatch.setattr(settings, "LAYA_ENABLED", True)

    async def fake_choice(state, question):
        del state, question
        return {
            "type": "choice",
            "choice": str(categories["food"].id),
            "probabilities": {
                str(categories["food"].id): 0.31,
                str(categories["retail"].id): 0.30,
            },
        }

    monkeypatch.setattr(category_suggestions, "_laya_choice", fake_choice)

    response = await client.post(
        "/api/v1/categories/suggest",
        json={"title": "امداد نومکس", "description": "پشتیبانی و رسیدگی ویژه"},
        headers=auth(user),
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "no_match"
    assert body["suggestions"] == []


@pytest.mark.asyncio
async def test_sidecar_failure_degrades_to_manual_picker(
    client, db_session, create_user, monkeypatch
):
    await _catalog(db_session)
    user = await create_user("09150000034")
    monkeypatch.setattr(settings, "LAYA_ENABLED", True)

    async def fake_choice(state, question):
        del state, question
        raise category_suggestions.LayaUnavailable("connection refused")

    monkeypatch.setattr(category_suggestions, "_laya_choice", fake_choice)

    response = await client.post(
        "/api/v1/categories/suggest",
        json={"title": "امداد نومکس", "description": "پشتیبانی و رسیدگی ویژه"},
        headers=auth(user),
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "unavailable"
    assert body["suggestions"] == []


@pytest.mark.asyncio
async def test_rule_layer_disambiguates_veterinary_from_medical_clinic(
    client, db_session, create_user, monkeypatch
):
    await _catalog(db_session)
    user = await create_user("09150000036")
    monkeypatch.setattr(settings, "LAYA_ENABLED", True)

    async def fake_choice(state, question):
        del state, question
        raise AssertionError("veterinary aliases should win without Laya")

    monkeypatch.setattr(category_suggestions, "_laya_choice", fake_choice)

    response = await client.post(
        "/api/v1/categories/suggest",
        json={
            "title": "کلینیک دامپزشکی دکتر روانبخش",
            "description": "معاینه و درمان حیوانات خانگی و دام",
        },
        headers=auth(user),
    )
    assert response.status_code == 200
    suggestion = response.json()["data"]["suggestions"][0]
    assert suggestion["category"]["slug"] == "agriculture"
    assert suggestion["subcategory"]["slug"] == "vet"


@pytest.mark.asyncio
async def test_rule_layer_handles_automotive_service_phrases(
    client, db_session, create_user, monkeypatch
):
    await _catalog(db_session)
    user = await create_user("09150000037")
    monkeypatch.setattr(settings, "LAYA_ENABLED", True)

    async def fake_choice(state, question):
        del state, question
        raise AssertionError("automotive aliases should win without Laya")

    monkeypatch.setattr(category_suggestions, "_laya_choice", fake_choice)

    for title, expected_subcategory in (
        ("برق خودرو بهبهان", "electric"),
        ("آژانس تاکسی بهبهان", "taxi"),
    ):
        response = await client.post(
            "/api/v1/categories/suggest",
            json={"title": title, "description": "خدمات تخصصی در بهبهان"},
            headers=auth(user),
        )
        assert response.status_code == 200
        suggestion = response.json()["data"]["suggestions"][0]
        assert suggestion["category"]["slug"] == "automotive"
        assert suggestion["subcategory"]["slug"] == expected_subcategory


@pytest.mark.asyncio
async def test_rules_can_be_disabled_for_raw_laya_benchmark(
    client, db_session, create_user, monkeypatch
):
    categories, subcategories = await _catalog(db_session)
    user = await create_user("09150000038")
    monkeypatch.setattr(settings, "LAYA_ENABLED", True)
    monkeypatch.setattr(settings, "LAYA_RULES_ENABLED", False)
    calls = []

    async def fake_choice(state, question):
        del state
        calls.append(question["instructions"])
        if "دسته اصلی" in question["instructions"]:
            return {
                "type": "choice",
                "choice": str(categories["food"].id),
                "probabilities": {
                    str(categories["food"].id): 0.91,
                    str(categories["retail"].id): 0.09,
                },
            }
        return {
            "type": "choice",
            "choice": str(subcategories["restaurant"].id),
            "probabilities": {
                str(subcategories["restaurant"].id): 0.84,
                str(subcategories["cafe"].id): 0.16,
            },
        }

    monkeypatch.setattr(category_suggestions, "_laya_choice", fake_choice)

    response = await client.post(
        "/api/v1/categories/suggest",
        json={"title": "برق خودرو بهبهان", "description": "تعمیر برق خودرو"},
        headers=auth(user),
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert len(calls) == 2
    suggestion = body["suggestions"][0]
    assert suggestion["category_source"] == "laya"
    assert suggestion["subcategory_source"] == "laya"


@pytest.mark.asyncio
async def test_diagnostics_requires_category_permission(client, create_user, monkeypatch):
    user = await create_user("09150000039")
    monkeypatch.setattr(settings, "LAYA_ENABLED", False)

    response = await client.post(
        "/api/v1/admin/categories/suggest/diagnose",
        json={"title": "رستوران تست", "description": "غذای ایرانی"},
        headers=auth(user),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_diagnostics_reports_disabled_configuration(
    client, create_user, monkeypatch
):
    admin = await create_user(
        "09150000040", role=UserRole.ADMIN, permissions=["category.read"]
    )
    monkeypatch.setattr(settings, "LAYA_ENABLED", False)

    response = await client.post(
        "/api/v1/admin/categories/suggest/diagnose",
        json={"title": "رستوران تست", "description": "غذای ایرانی"},
        headers=auth(admin),
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["verdict"] == "disabled"
    assert body["status"] == "disabled"
    assert body["health"]["status"] == "skipped"
    assert body["config"]["enabled"] is False
    assert body["suggestions"] == []
    assert body["tuning"][0]["severity"] == "critical"


@pytest.mark.asyncio
async def test_diagnostics_probes_laya_even_when_rules_decide(
    client, db_session, create_user, monkeypatch
):
    categories, subcategories = await _catalog(db_session)
    admin = await create_user(
        "09150000041", role=UserRole.ADMIN, permissions=["category.read"]
    )
    monkeypatch.setattr(settings, "LAYA_ENABLED", True)

    async def fake_health():
        return {
            "status": "ok",
            "latency_ms": 12,
            "http_status": 200,
            "detail": {"status": "ok"},
            "error": None,
        }

    async def fake_choice(state, question):
        del state
        if "دسته اصلی" in question["instructions"]:
            return {
                "type": "choice",
                "choice": str(categories["food"].id),
                "probabilities": {
                    str(categories["food"].id): 0.91,
                    str(categories["retail"].id): 0.09,
                },
            }
        return {
            "type": "choice",
            "choice": str(subcategories["restaurant"].id),
            "probabilities": {
                str(subcategories["restaurant"].id): 0.84,
                str(subcategories["cafe"].id): 0.16,
            },
        }

    monkeypatch.setattr(category_suggestions, "_laya_health", fake_health)
    monkeypatch.setattr(category_suggestions, "_laya_choice", fake_choice)

    response = await client.post(
        "/api/v1/admin/categories/suggest/diagnose",
        json={
            "title": "رستوران سنتی نومکس",
            "description": "غذای ایرانی و کباب",
            "probe_laya": True,
        },
        headers=auth(admin),
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["verdict"] == "working"
    assert body["probe"]["status"] == "ok"
    assert body["probe"]["category"]["slug"] == "food"
    assert body["probe"]["subcategory"]["slug"] == "restaurant"
    stages = [event["stage"] for event in body["events"]]
    assert "rules_category" in stages
    assert "laya_probe_category" in stages
    assert "laya_probe_subcategory" in stages
    assert body["suggestions"][0]["category"]["slug"] == "food"
    assert body["config"]["rules_enabled"] is True


@pytest.mark.asyncio
async def test_diagnostics_raw_mode_skips_the_duplicate_probe(
    client, db_session, create_user, monkeypatch
):
    categories, subcategories = await _catalog(db_session)
    admin = await create_user(
        "09150000042", role=UserRole.ADMIN, permissions=["category.read"]
    )
    monkeypatch.setattr(settings, "LAYA_ENABLED", True)
    calls = []

    async def fake_health():
        return {
            "status": "ok",
            "latency_ms": 10,
            "http_status": 200,
            "detail": {"status": "ok"},
            "error": None,
        }

    async def fake_choice(state, question):
        del state
        calls.append(question["instructions"])
        if "دسته اصلی" in question["instructions"]:
            return {
                "type": "choice",
                "choice": str(categories["food"].id),
                "probabilities": {str(categories["food"].id): 0.9},
            }
        return {
            "type": "choice",
            "choice": str(subcategories["restaurant"].id),
            "probabilities": {str(subcategories["restaurant"].id): 0.85},
        }

    monkeypatch.setattr(category_suggestions, "_laya_health", fake_health)
    monkeypatch.setattr(category_suggestions, "_laya_choice", fake_choice)

    response = await client.post(
        "/api/v1/admin/categories/suggest/diagnose",
        json={
            "title": "امداد نومکس",
            "description": "خدمات و پشتیبانی ویژه",
            "rules_enabled": False,
            "probe_laya": True,
        },
        headers=auth(admin),
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["config"]["rules_enabled"] is False
    assert body["verdict"] == "working"
    assert body["probe"] is None
    assert len(calls) == 2
    stages = [event["stage"] for event in body["events"]]
    assert "laya_probe_category" not in stages
    assert "laya_probe" in stages


@pytest.mark.asyncio
async def test_diagnostics_reports_unreachable_model(
    client, db_session, create_user, monkeypatch
):
    await _catalog(db_session)
    admin = await create_user(
        "09150000043", role=UserRole.ADMIN, permissions=["category.read"]
    )
    monkeypatch.setattr(settings, "LAYA_ENABLED", True)

    async def fake_health():
        return {
            "status": "unreachable",
            "latency_ms": 4,
            "http_status": None,
            "detail": None,
            "error": "connection refused",
        }

    async def fake_choice(state, question):
        del state, question
        raise category_suggestions.LayaUnavailable("connection refused")

    monkeypatch.setattr(category_suggestions, "_laya_health", fake_health)
    monkeypatch.setattr(category_suggestions, "_laya_choice", fake_choice)

    response = await client.post(
        "/api/v1/admin/categories/suggest/diagnose",
        json={
            "title": "امداد نومکس",
            "description": "خدمات و پشتیبانی ویژه",
        },
        headers=auth(admin),
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["verdict"] == "unavailable"
    assert body["status"] == "unavailable"
    assert body["probe"] is None
    stages = [event["stage"] for event in body["events"]]
    assert "laya_category" in stages
    severities = {hint["severity"] for hint in body["tuning"]}
    assert "critical" in severities
