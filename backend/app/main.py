from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.admin import admin_router, dev_router
from app.api.v1.auth import router as auth_router
from app.api.v1.businesses import router as businesses_router
from app.api.v1.quotes import router as quotes_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.ads import router as ads_router
from app.api.v1.reviews import router as reviews_router
from app.api.v1.utility import router as utility_router
from app.api.v1.categories import router as categories_router
from app.api.v1.health import router as health_router
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
    application.include_router(businesses_router, prefix="/api/v1")
    application.include_router(quotes_router, prefix="/api/v1")
    application.include_router(notifications_router, prefix="/api/v1")
    application.include_router(ads_router, prefix="/api/v1")
    application.include_router(reviews_router, prefix="/api/v1")
    application.include_router(utility_router, prefix="/api/v1")
    application.include_router(admin_router, prefix="/api/v1")
    if settings.APP_ENV != "production" and settings.DEV_OTP_ENABLED:
        application.include_router(dev_router, prefix="/api/v1")
    application.include_router(health_router)

    return application


app = create_app()
