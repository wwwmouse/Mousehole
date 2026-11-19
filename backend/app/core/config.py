from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Application settings, loaded from environment variables and .env files."""

    model_config = SettingsConfigDict(
        env_file=(str(REPO_ROOT / ".env"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "mousehole"
    api_prefix: str = "/api/v1"
    database_url: str = (
        "postgresql+pg8000://mousehole:mousehole@localhost:5433/mousehole"
    )
    storage_dir: Path = REPO_ROOT / "storage"
    data_dir: Path = REPO_ROOT / "data"
    default_workspace_name: str = "My Workspace"
    max_upload_mb: int = 25
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def ensure_directories(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings


def clear_settings_cache() -> None:
    """Tests use this after overriding environment variables."""
    get_settings.cache_clear()
