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
    max_upload_mb: int = 50
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # 每个 Chat 请求最多携带多少条历史消息（user/assistant 各算一条）。
    chat_history_limit: int = 80
    # Ollama 地址：Docker 模式应指向宿主机（host.docker.internal），
    # 本机直接运行 backend 时用 127.0.0.1。
    ollama_base_url: str = "http://127.0.0.1:11434"
    # --- Phase 5 (H1/H5) runtime knobs -------------------------------------
    # Logging: stdlib level name; sensitive values are filtered by core.logging.
    log_level: str = "INFO"
    # Scheduler worker count (was hardcoded to 2 in main.py).
    max_concurrency: int = 2
    # Upper bound for a single file's read+parse job (seconds).
    parse_timeout_seconds: float = 120.0
    # Fallback context budget when Workspace/Task does not override it.
    default_context_budget_tokens: int = 32_768
    # Known model windows, keyed "provider/model"; unknown models use
    # builder.DEFAULT_WINDOW. Override with MODEL_CONTEXT_WINDOWS='{"p/m": 8192}'.
    model_context_windows: dict[str, int] = {
        "deepseek/deepseek-flash": 1_000_000,
        "deepseek/deepseek-v4-pro": 1_000_000,
        "openai/gpt-4o": 128_000,
        "openai/gpt-4o-mini": 128_000,
    }

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
