from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "nomax"
    APP_ENV: str = "local"
    DEBUG: bool = False

    DATABASE_URL: str = "postgresql+asyncpg://nomax:secret@localhost:5432/nomax"
    DATABASE_ECHO: bool = False

    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET: str = "nomax-local-dev-secret-change-me-please-0123456789abcdef"
    JWT_ACCESS_TTL_MINUTES: int = 15
    JWT_REFRESH_TTL_DAYS: int = 30

    OTP_TTL_SECONDS: int = 120
    OTP_RATE_LIMIT_PER_HOUR: int = 3
    OTP_MAX_ATTEMPTS: int = 5

    SMS_PROVIDER: str = "console"
    # Mellipayamak shared-service (pattern) endpoint. The message body is a
    # pre-approved template identified by SMS_OTP_BODY_ID.
    SMS_API_URL: str = "https://rest.payamak-panel.com/api/SendSMS/BaseServiceNumber"
    SMS_USERNAME: str = ""
    SMS_PASSWORD: str = ""
    SMS_OTP_BODY_ID: int = 0
    SMS_TIMEOUT_SECONDS: float = 8.0
    SMS_MAX_ATTEMPTS: int = 2

    DEV_OTP_ENABLED: bool = True

    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
    ]


settings = Settings()
