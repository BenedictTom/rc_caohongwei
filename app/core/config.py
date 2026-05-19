from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./notifications.db"
    providers_file: Path = Path("./providers.yaml")

    log_level: str = "INFO"
    log_format: str = "json"

    worker_interval_seconds: float = 1.0
    worker_batch_size: int = 100
    worker_max_concurrency: int = 32

    max_retry_attempts: int = 4
    payload_max_bytes: int = 64 * 1024

    breaker_fail_threshold: int = 5
    breaker_open_duration_seconds: int = 300

    http_default_timeout_ms: int = 5000

    cors_allow_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
