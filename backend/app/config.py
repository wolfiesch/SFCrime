"""Application configuration using Pydantic settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://localhost:5432/sfcrime"

    # DataSF SODA API
    soda_app_token: str | None = None  # Optional but recommended for higher rate limits
    soda_base_url: str = "https://data.sfgov.org/resource"
    dispatch_calls_dataset_id: str = "gnap-fj3t"
    incident_reports_dataset_id: str = "wg3w-h783"

    # Ingestion settings
    dispatch_poll_interval_minutes: int = 5
    incidents_poll_interval_minutes: int = 60
    dispatch_retention_hours: int = 48
    backfill_chunk_days: int = 7

    # API settings
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["*"]  # Restrict in production
    rate_limit_per_minute: int = 60

    # Environment
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
