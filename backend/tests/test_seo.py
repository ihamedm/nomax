import sqlalchemy as sa

from app.core.config import settings
from app.db.seed import seed_categories
from app.models.business import Business, BusinessStatus
from app.models.category import Category
from app.models.user import UserRole


async def _business(db_session, owner, category, slug, status):
    business = Business(
        owner_id=owner.id,
        category_id=category.id,
        name=slug,
        slug=slug,
        short_description="",
        address="بهبهان",
        status=status,
    )
    db_session.add(business)
    await db_session.commit()
    return business


async def test_robots_points_to_the_sitemap(client):
    response = await client.get("/robots.txt")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "Disallow: /admin" in response.text
    assert f"Sitemap: {settings.SITE_URL}/sitemap.xml" in response.text


async def test_sitemap_lists_only_public_urls(client, db_session, create_user):
    owner = await create_user("09160000041", UserRole.OWNER)
    await seed_categories(db_session)
    await db_session.commit()
    category = (await db_session.execute(sa.select(Category))).scalars().first()

    approved = await _business(db_session, owner, category, "kafe-stare", BusinessStatus.APPROVED)
    await _business(db_session, owner, category, "hidden-shop", BusinessStatus.PENDING)

    response = await client.get("/sitemap.xml")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert f"{settings.SITE_URL}/businesses/{approved.slug}" in response.text
    assert "hidden-shop" not in response.text
    assert f"{settings.SITE_URL}/search?cat={category.slug}" in response.text
