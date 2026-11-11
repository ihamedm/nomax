import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.db.seed import seed_categories
from app.models.business import Business, BusinessStatus
from app.models.category import Category
from app.models.user import User


def _national_id(base9: str) -> str:
    weights = [10, 9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(int(d) * w for d, w in zip(base9, weights))
    remainder = total % 11
    return base9 + str(remainder if remainder < 2 else 11 - remainder)


def _auth(user) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


async def _make_business(db_session, create_user, *, owner_phone="9120000001"):
    await seed_categories(db_session)
    await db_session.commit()
    category = (
        await db_session.execute(select(Category).where(Category.slug == "automotive"))
    ).scalars().first()
    owner = await create_user(owner_phone, full_name="مالک پنل")
    business = Business(
        owner_id=owner.id,
        category_id=category.id,
        name="تعمیرگاه نمونه",
        slug=f"claim-{owner_phone}",
        short_description="",
        address="بهبهان، خیابان امام",
        status=BusinessStatus.APPROVED,
    )
    db_session.add(business)
    await db_session.commit()
    await db_session.refresh(business)
    return business, owner


async def _issue_otp(client, business, user) -> str:
    response = await client.post(
        f"/api/v1/businesses/{business.id}/claim/otp", headers=_auth(user)
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["dev_otp"]


@pytest.mark.asyncio
async def test_owner_claim_sets_profile_and_signs_owner_in(
    client, db_session, create_user
):
    business, owner = await _make_business(db_session, create_user)
    claimant = await create_user("09120000002")
    code = await _issue_otp(client, business, claimant)

    verified = await client.post(
        f"/api/v1/businesses/{business.id}/claim/otp/verify",
        json={"code": code},
        headers=_auth(claimant),
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["data"]["full_name"] == "مالک پنل"

    nid = _national_id("541111111")
    profile = await client.post(
        f"/api/v1/businesses/{business.id}/claim/profile",
        json={"full_name": "مالک واقعی", "national_id": nid, "password": "secret-password-1"},
        headers=_auth(claimant),
    )
    assert profile.status_code == 200, profile.text
    data = profile.json()["data"]
    assert data["user"]["id"] == str(owner.id)
    assert data["user"]["full_name"] == "مالک واقعی"
    assert data["user"]["role"] == "owner"
    assert data["user"]["is_verified"] is True
    assert data["user"]["is_national_id_verified"] is True

    # The OTP marker is single-use.
    again = await client.post(
        f"/api/v1/businesses/{business.id}/claim/profile",
        json={"full_name": "مالک واقعی", "national_id": nid, "password": "secret-password-1"},
        headers=_auth(claimant),
    )
    assert again.status_code == 409

    # The new password belongs to the owner account, which also carries the profile.
    login = await client.post(
        "/api/v1/auth/login", json={"phone": owner.phone, "password": "secret-password-1"}
    )
    assert login.status_code == 200, login.text
    assert login.json()["data"]["user"]["id"] == str(owner.id)


@pytest.mark.asyncio
async def test_owner_claim_requires_verified_otp(client, db_session, create_user):
    business, _ = await _make_business(db_session, create_user)
    claimant = await create_user("09120000002")
    await _issue_otp(client, business, claimant)

    wrong = await client.post(
        f"/api/v1/businesses/{business.id}/claim/otp/verify",
        json={"code": "000000"},
        headers=_auth(claimant),
    )
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "otp_invalid"

    profile = await client.post(
        f"/api/v1/businesses/{business.id}/claim/profile",
        json={
            "full_name": "مالک واقعی",
            "national_id": _national_id("541111111"),
            "password": "secret-password-1",
        },
        headers=_auth(claimant),
    )
    assert profile.status_code == 403
    assert profile.json()["error"]["code"] == "owner_claim_not_verified"


@pytest.mark.asyncio
async def test_owner_claim_rejects_verified_owner(client, db_session, create_user):
    business, owner = await _make_business(db_session, create_user)
    stored = await db_session.get(User, owner.id)
    stored.is_verified = True
    await db_session.commit()
    claimant = await create_user("09120000002")

    response = await client.post(
        f"/api/v1/businesses/{business.id}/claim/otp", headers=_auth(claimant)
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "owner_already_verified"


@pytest.mark.asyncio
async def test_owner_claim_rejects_shared_national_id(client, db_session, create_user):
    business, _ = await _make_business(db_session, create_user)
    claimant = await create_user("09120000002")
    nid = _national_id("541111111")
    taken = await create_user("09120000003")
    stored = await db_session.get(User, taken.id)
    stored.national_id = nid
    await db_session.commit()
    code = await _issue_otp(client, business, claimant)

    verified = await client.post(
        f"/api/v1/businesses/{business.id}/claim/otp/verify",
        json={"code": code},
        headers=_auth(claimant),
    )
    assert verified.status_code == 200

    profile = await client.post(
        f"/api/v1/businesses/{business.id}/claim/profile",
        json={"full_name": "مالک واقعی", "national_id": nid, "password": "secret-password-1"},
        headers=_auth(claimant),
    )
    assert profile.status_code == 409
    assert profile.json()["error"]["code"] == "national_id_in_use"
