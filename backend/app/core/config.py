from pydantic import field_validator
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

    # Each owner may register this many active businesses. The profile hides
    # the "new business" action once the limit is reached.
    MAX_BUSINESSES_PER_OWNER: int = 1

    # Gallery photos allowed per business. The wizard reads this value from
    # `/me/businesses` so the UI and API stay in sync.
    MAX_BUSINESS_IMAGES: int = 6

    DATABASE_URL: str = "postgresql+asyncpg://nomax:secret@localhost:5432/nomax"
    DATABASE_ECHO: bool = False

    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET: str = "nomax-local-dev-secret-change-me-please-0123456789abcdef"
    JWT_ACCESS_TTL_MINUTES: int = 15
    JWT_REFRESH_TTL_DAYS: int = 30

    OTP_TTL_SECONDS: int = 120
    # 0 disables request throttling; development overrides set this to 0.
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

    # ArvanCloud S3 (S3-compatible). When the credentials are empty, local
    # development falls back to UPLOAD_DIR; production compose requires them.
    S3_ENDPOINT_URL: str = "https://s3.ir-thr-at1.arvanstorage.ir"
    S3_REGION: str = "ir-thr-at1"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET_PUBLIC: str = "nomax-public"
    S3_BUCKET_PRIVATE: str = "nomax-private"
    S3_PUBLIC_URL: str = ""
    S3_ADDRESSING_STYLE: str = "path"
    S3_HEALTHCHECK_TTL_SECONDS: int = 30
    S3_PRESIGN_TTL_SECONDS: int = 900
    S3_PUBLIC_READ_ACL: bool = True
    UPLOAD_DIR: str = "/tmp/nomax/uploads"

    # Database backup/restore from the superadmin dashboard. Compose mounts a
    # persistent volume at /data/backups; local development uses /tmp.
    BACKUP_DIR: str = "/tmp/nomax/backups"
    BACKUP_MAX_UPLOAD_MB: int = 512
    BACKUP_TIMEOUT_SECONDS: int = 600
    # Manual and automatic dumps are gzipped and copied to the private Arvan
    # bucket. An empty BACKUP_S3_BUCKET reuses S3_BUCKET_PRIVATE.
    BACKUP_S3_BUCKET: str = ""
    BACKUP_S3_PREFIX: str = "database-backups"
    BACKUP_KEEP_REMOTE: int = 30
    BACKUP_DAILY_ENABLED: bool = True
    BACKUP_DAILY_HOUR: int = 3
    BACKUP_DAILY_MINUTE: int = 0
    BACKUP_TIMEZONE: str = "Asia/Tehran"

    # Address geocoding used by the map picker. Nominatim is the default
    # because it needs no key; set GEOCODER_URL to switch providers.
    GEOCODER_URL: str = "https://nominatim.openstreetmap.org"
    GEOCODER_USER_AGENT: str = "NOMAX/1.0 (+https://nomax.ir)"
    GEOCODER_TIMEOUT_SECONDS: float = 8.0
    GEOCODER_COUNTRY_CODES: str = "ir"
    # Restrict searches to Behbahan (left,top,right,bottom in WGS84).
    GEOCODER_VIEWBOX: str = "50.18,30.65,50.30,30.54"
    GEOCODER_BOUNDED: bool = True

    @field_validator("S3_ENDPOINT_URL", "S3_PUBLIC_URL")
    @classmethod
    def _normalize_s3_url(cls, value: str) -> str:
        value = (value or "").strip().rstrip("/")
        if value and not value.startswith(("http://", "https://")):
            value = f"https://{value}"
        return value

    @field_validator("MAX_BUSINESS_IMAGES")
    @classmethod
    def _validate_max_business_images(cls, value: int) -> int:
        if value < 1:
            raise ValueError("MAX_BUSINESS_IMAGES must be at least 1")
        return value

    @field_validator("BACKUP_MAX_UPLOAD_MB", "BACKUP_TIMEOUT_SECONDS", "BACKUP_KEEP_REMOTE")
    @classmethod
    def _validate_backup_limits(cls, value: int) -> int:
        if value < 1:
            raise ValueError("BACKUP values must be at least 1")
        return value

    @field_validator("BACKUP_DAILY_HOUR")
    @classmethod
    def _validate_backup_hour(cls, value: int) -> int:
        if not 0 <= value <= 23:
            raise ValueError("BACKUP_DAILY_HOUR must be between 0 and 23")
        return value

    @field_validator("BACKUP_DAILY_MINUTE")
    @classmethod
    def _validate_backup_minute(cls, value: int) -> int:
        if not 0 <= value <= 59:
            raise ValueError("BACKUP_DAILY_MINUTE must be between 0 and 59")
        return value

    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
    ]


settings = Settings()
