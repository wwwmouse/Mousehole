"""Phase 5 H5: runtime knobs are configurable instead of hardcoded."""
from __future__ import annotations

from types import SimpleNamespace

from app.core.config import clear_settings_cache, get_settings
from app.modules.context import builder


def test_h5_defaults() -> None:
    clear_settings_cache()
    try:
        settings = get_settings()
        assert settings.max_concurrency == 2
        assert settings.parse_timeout_seconds == 120.0
        assert settings.default_context_budget_tokens == 32_768
        assert settings.model_context_windows["deepseek/deepseek-flash"] == 1_000_000
        assert settings.model_context_windows["openai/gpt-4o"] == 128_000
        assert settings.log_level == "INFO"
    finally:
        clear_settings_cache()


def test_h5_environment_overrides(monkeypatch) -> None:
    monkeypatch.setenv("MAX_CONCURRENCY", "5")
    monkeypatch.setenv("PARSE_TIMEOUT_SECONDS", "3.5")
    monkeypatch.setenv("DEFAULT_CONTEXT_BUDGET_TOKENS", "8192")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv(
        "MODEL_CONTEXT_WINDOWS", '{"custom/model": 4096, "openai/gpt-4o": 64000}'
    )
    clear_settings_cache()
    try:
        settings = get_settings()
        assert settings.max_concurrency == 5
        assert settings.parse_timeout_seconds == 3.5
        assert settings.default_context_budget_tokens == 8192
        assert settings.log_level == "DEBUG"
        assert settings.model_context_windows == {
            "custom/model": 4096,
            "openai/gpt-4o": 64000,
        }
    finally:
        clear_settings_cache()


def test_configured_model_window_drives_context_budget(monkeypatch) -> None:
    monkeypatch.setenv("MODEL_CONTEXT_WINDOWS", '{"custom/model": 8192}')
    clear_settings_cache()
    try:
        budget = builder.compute_budget(
            SimpleNamespace(context_budget_tokens=None),
            "custom",
            "model",
            max_tokens=1024,
        )
        assert budget == 8192 - 1024 - builder.OVERHEAD_RESERVE
    finally:
        clear_settings_cache()
