from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.shared.exceptions import NotFoundError, UnprocessableError

# Built-in provider definitions. Users only fill in api_key / base_url / models.
PROVIDER_DEFINITIONS: dict[str, dict[str, Any]] = {
    "deepseek": {
        "kind": "openai",
        "base_url": "https://api.deepseek.com",
        # Official model IDs (DeepSeek API Docs, 2026-11):
        # deepseek-flash = DeepSeek-V4.1-Flash, deepseek-v4-pro = DeepSeek-V4-Pro
        "default_model": "deepseek-flash",
        "models": ["deepseek-flash", "deepseek-v4-pro"],
    },
    "openai": {
        "kind": "openai",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "models": ["gpt-4o-mini", "gpt-4o"],
    },
    "ollama": {
        "kind": "ollama",
        "base_url": get_settings().ollama_base_url,
        "default_model": "llama3.2",
        "models": ["llama3.2"],
    },
}

CONFIG_FILENAME = "provider_config.json"


def config_path() -> Path:
    return get_settings().data_dir / CONFIG_FILENAME


def _load() -> dict[str, dict[str, Any]]:
    path = config_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    providers = raw.get("providers")
    return providers if isinstance(providers, dict) else {}


def _save(providers: dict[str, dict[str, Any]]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps({"providers": providers}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temp, path)


def _merged(name: str, stored: dict[str, Any]) -> dict[str, Any]:
    definition = PROVIDER_DEFINITIONS[name]
    merged = {
        "name": name,
        "kind": definition["kind"],
        "base_url": stored.get("base_url") or definition["base_url"],
        "api_key": stored.get("api_key") or "",
        "models": stored.get("models") or list(definition["models"]),
        "default_model": stored.get("default_model") or definition["default_model"],
        "stored": bool(stored),
    }
    return merged


def list_providers() -> list[dict[str, Any]]:
    stored = _load()
    return [
        _public(_merged(name, stored.get(name, {})))
        for name in PROVIDER_DEFINITIONS
    ]


def _public(config: dict[str, Any]) -> dict[str, Any]:
    key = config.get("api_key") or ""
    if config.get("kind") == "ollama":
        configured = bool(config.get("stored"))
    else:
        configured = bool(key)
    return {
        "name": config["name"],
        "kind": config["kind"],
        "base_url": config["base_url"],
        "configured": configured,
        "masked_key": mask_key(key),
        "models": config.get("models") or [],
        "default_model": config.get("default_model"),
    }


def mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "••••••••"
    return f"••••••••{key[-4:]}"


def get_provider(name: str) -> dict[str, Any]:
    if name not in PROVIDER_DEFINITIONS:
        raise NotFoundError("未知的模型 Provider", details={"provider": name})
    stored = _load()
    return _merged(name, stored.get(name, {}))


def update_provider(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if name not in PROVIDER_DEFINITIONS:
        raise NotFoundError("未知的模型 Provider", details={"provider": name})
    stored = _load()
    current = stored.get(name, {})
    if payload.get("api_key") is not None:
        current["api_key"] = payload["api_key"].strip()
    if payload.get("base_url") is not None:
        base_url = payload["base_url"].strip()
        if not base_url:
            raise UnprocessableError("base_url 不能为空")
        current["base_url"] = base_url
    if payload.get("models") is not None:
        models = [str(item).strip() for item in payload["models"] if str(item).strip()]
        current["models"] = models
    if payload.get("default_model") is not None:
        current["default_model"] = payload["default_model"].strip() or None
    stored[name] = current
    _save(stored)
    return _public(_merged(name, current))


def is_configured(name: str) -> bool:
    config = get_provider(name)
    if config.get("kind") == "ollama":
        return bool(config.get("stored"))
    return bool(config.get("api_key"))


def available_models() -> list[dict[str, str]]:
    models: list[dict[str, str]] = []
    for provider in list_providers():
        if not provider["configured"]:
            continue
        for model in provider["models"]:
            models.append(
                {
                    "provider": provider["name"],
                    "model": model,
                    "label": f"{provider['name']} / {model}",
                }
            )
    return models


def default_selection() -> tuple[str, str] | None:
    """Pick a sensible provider/model when the Task has none configured yet."""
    for provider in list_providers():
        if provider["configured"]:
            model = provider["default_model"] or (provider["models"][0] if provider["models"] else None)
            if model:
                return provider["name"], model
    return None


def new_id() -> str:
    return uuid.uuid4().hex
