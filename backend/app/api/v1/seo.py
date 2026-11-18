"""Crawl helpers: robots.txt and the public sitemap.

Both are served by nginx next to the SPA, because social/SEO crawlers request
them at the site root rather than under `/api/v1`.
"""
from __future__ import annotations

from urllib.parse import quote
from xml.sax.saxutils import escape

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.business import Business, BusinessStatus
from app.models.category import Category

router = APIRouter(tags=["seo"])

STATIC_PAGES = ["/", "/categories", "/pages/about", "/pages/contact"]


def _site_url() -> str:
    return settings.SITE_URL.rstrip("/")


@router.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
async def robots() -> str:
    return "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /admin",
            "Disallow: /api/",
            "Disallow: /me",
            "Disallow: /quote",
            "Disallow: /login",
            "Disallow: /businesses/new",
            "",
            f"Sitemap: {_site_url()}/sitemap.xml",
            "",
        ]
    )


@router.get("/sitemap.xml", include_in_schema=False)
async def sitemap(session: AsyncSession = Depends(get_db)) -> Response:
    site = _site_url()
    businesses = (
        await session.execute(
            sa.select(Business.slug, Business.updated_at)
            .join(Category, Business.category_id == Category.id)
            .where(
                Business.status == BusinessStatus.APPROVED,
                Business.deleted_at.is_(None),
                Category.deleted_at.is_(None),
            )
            .order_by(Business.updated_at.desc())
        )
    ).all()
    categories = (
        (
            await session.execute(
                sa.select(Category.slug).where(
                    Category.deleted_at.is_(None), Category.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )

    urls = [(path, None) for path in STATIC_PAGES]
    urls += [(f"/search?cat={quote(slug)}", None) for slug in categories]
    urls += [
        (f"/businesses/{quote(slug, safe='')}", updated_at) for slug, updated_at in businesses
    ]

    entries = []
    for path, updated_at in urls:
        lastmod = f"<lastmod>{updated_at.date().isoformat()}</lastmod>" if updated_at else ""
        entries.append(f"<url><loc>{escape(f'{site}{path}')}</loc>{lastmod}</url>")

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(entries)
        + "</urlset>"
    )
    return Response(content=body, media_type="application/xml")
