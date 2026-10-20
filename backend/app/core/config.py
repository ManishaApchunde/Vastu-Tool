from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration. Every field can be overridden with an env var of the same name."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Vastu Plan Analyzer"
    report_brand: str = "Vastu Plan Analyzer"  # name printed on PDF reports
    environment: str = "development"  # development | production | test

    # Database: SQLite works out of the box for local dev; use PostgreSQL in any shared environment.
    database_url: str = "sqlite:///./vastu_dev.db"
    auto_create_tables: bool = True  # dev convenience; production uses Alembic migrations
    auto_seed: bool = True  # seed rule set, remedies, scoring config and demo user if empty

    # Auth
    secret_key: str = "dev-insecure-secret-change-me"
    access_token_minutes: int = 60 * 12
    cors_origins: str = "http://localhost:3000"

    # Storage
    storage_backend: str = "local"  # local | s3
    local_storage_dir: str = "./storage"
    public_api_url: str = "http://localhost:8000"
    s3_endpoint_url: str | None = None
    s3_public_endpoint_url: str | None = None  # host the browser uses for presigned URLs, if different
    s3_bucket: str = "vastu-private"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_region: str = "us-east-1"
    signed_url_ttl_seconds: int = 600

    # Uploads
    max_upload_mb: int = 15
    max_image_pixels: int = 40_000_000
    min_image_side: int = 300
    blur_threshold: float = 40.0

    # Background jobs
    job_mode: str = "inline"  # inline (FastAPI background tasks) | celery
    redis_url: str = "redis://localhost:6379/0"
    job_max_attempts: int = 3

    # AI
    ai_provider: str = "mock"  # mock | anthropic
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"
    ai_timeout_seconds: int = 90

    # Video report (narrated walkthrough of the PDF)
    video_tts: str = "auto"  # auto | edge | gtts | silent
    video_voice_en: str = "en-IN-NeerjaNeural"
    video_voice_mr: str = "mr-IN-AarohiNeural"
    video_voice_rate: str = "-4%"
    video_burn_captions: bool = True  # subtitles drawn on the video too, so it works muted

    # Rate limiting (per client IP, per minute)
    rate_limit_per_minute: int = 240
    upload_rate_limit_per_minute: int = 12

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
