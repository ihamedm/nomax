from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.admin import admin_router, dev_router
from app.api.v1.admin_quotes import router as admin_quotes_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.auth import router as auth_router
from app.api.v1.businesses import me_router, router as businesses_router, uploads_router
from app.api.v1.bookmarks import router as bookmarks_router
from app.api.v1.files import router as files_router
from app.api.v1.quotes import router as quotes_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.owner_reviews import router as owner_reviews_router
from app.api.v1.ads import router as ads_router
from app.api.v1.reviews import router as reviews_router
from app.api.v1.utility import router as utility_router
from app.api.v1.categories import router as categories_router
from app.api.v1.geo import router as geo_router
from app.api.v1.health import router as health_router
from app.api.v1.settings import router as settings_router
from app.api.v1.cms import router as cms_router
from app.api.v1.admin_data import router as admin_data_router
from app.core.api_response import build_error_response
from app.core.config import settings
from app.core.errors import AppError


def create_app() -> FastAPI:
    application = FastAPI(
        title="NOMAX API",
        version="0.1.0",
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return build_error_response(exc)

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "validation_failed",
                    "details": {"errors": exc.errors()},
                }
            },
        )

    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(categories_router, prefix="/api/v1")
    application.include_router(geo_router, prefix="/api/v1")
    application.include_router(businesses_router, prefix="/api/v1")
    application.include_router(me_router, prefix="/api/v1")
    application.include_router(bookmarks_router, prefix="/api/v1")
    application.include_router(files_router, prefix="/api/v1")
    application.include_router(uploads_router, prefix="/api/v1")
    application.include_router(quotes_router, prefix="/api/v1")
    application.include_router(notifications_router, prefix="/api/v1")
    application.include_router(owner_reviews_router, prefix="/api/v1")
    application.include_router(ads_router, prefix="/api/v1")
    application.include_router(reviews_router, prefix="/api/v1")
    application.include_router(utility_router, prefix="/api/v1")
    application.include_router(settings_router, prefix="/api/v1")
    application.include_router(cms_router, prefix="/api/v1")
    application.include_router(admin_data_router, prefix="/api/v1")
    application.include_router(admin_router, prefix="/api/v1")
    application.include_router(admin_quotes_router, prefix="/api/v1")
    application.include_router(analytics_router, prefix="/api/v1")
    if settings.APP_ENV != "production" and settings.DEV_OTP_ENABLED:
        application.include_router(dev_router, prefix="/api/v1")
    application.include_router(health_router)

    # Local development fallback: serve files written under UPLOAD_DIR. In
    # production with ArvanCloud S3 these URLs are not used.
    upload_root = Path(settings.UPLOAD_DIR)
    upload_root.mkdir(parents=True, exist_ok=True)
    application.mount("/uploads", StaticFiles(directory=upload_root), name="uploads")

    return application


app = create_app()
