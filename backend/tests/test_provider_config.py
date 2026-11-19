from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.modules.model import config as provider_config


@pytest.fixture()
def isolated_provider_config(test_data_root, monkeypatch):
    monkeypatch.setattr(
        provider_config, "config_path", lambda: test_data_root / "provider_config.json"
    )
    return test_data_root / "provider_config.json"


def test_providers_default_not_configured(
    client: TestClient, isolated_provider_config
) -> None:
    response = client.get("/api/v1/providers")
    assert response.status_code == 200
    providers = {item["name"]: item for item in response.json()}
    assert set(providers) == {"deepseek", "openai", "ollama"}
    assert all(item["configured"] is False for item in providers.values())
    assert all(item["masked_key"] == "" for item in providers.values())


def test_update_provider_masks_key_and_writes_file(
    client: TestClient, isolated_provider_config
) -> None:
    secret = "sk-test-1234567890abcd"
    updated = client.put(
        "/api/v1/providers/deepseek", json={"api_key": secret}
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["configured"] is True
    assert body["masked_key"].endswith("abcd")
    assert secret not in updated.text

    listed = client.get("/api/v1/providers").json()
    deepseek = next(item for item in listed if item["name"] == "deepseek")
    assert deepseek["configured"] is True
    assert secret not in json.dumps(listed)

    stored = json.loads(isolated_provider_config.read_text(encoding="utf-8"))
    assert stored["providers"]["deepseek"]["api_key"] == secret

    models = client.get("/api/v1/models").json()
    assert any(
        item["provider"] == "deepseek" and item["model"] == "deepseek-flash"
        for item in models
    )


def test_ollama_requires_explicit_save(
    client: TestClient, isolated_provider_config
) -> None:
    providers = {item["name"]: item for item in client.get("/api/v1/providers").json()}
    assert providers["ollama"]["configured"] is False

    saved = client.put(
        "/api/v1/providers/ollama", json={"base_url": "http://127.0.0.1:11434"}
    )
    assert saved.status_code == 200
    assert saved.json()["configured"] is True


def test_unknown_provider_returns_404(
    client: TestClient, isolated_provider_config
) -> None:
    response = client.put("/api/v1/providers/unknown", json={"api_key": "x"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
