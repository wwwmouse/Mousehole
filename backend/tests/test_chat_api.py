from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.modules.model import config as provider_config
from app.modules.model import service as model_service


def fake_resolve(task_provider, task_model, request_provider=None, request_model=None):
    return "deepseek", "deepseek-chat", {}


captured_params: list[dict] = []


async def fake_stream(provider, model, messages, *, temperature=None, max_tokens=None):
    captured_params.append({"temperature": temperature, "max_tokens": max_tokens})
    yield {"type": "delta", "text": "你好"}
    yield {"type": "delta", "text": "，世界"}
    yield {
        "type": "usage",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


async def failing_stream(provider, model, messages, *, temperature=None, max_tokens=None):
    yield {"type": "delta", "text": "部分"}
    raise RuntimeError("boom")


def _create_task(client: TestClient) -> str:
    response = client.post("/api/v1/tasks", json={"title": "chat test"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_chat_stream_persists_messages_and_usage(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(model_service, "resolve_model", fake_resolve)
    monkeypatch.setattr(model_service, "stream_chat", fake_stream)
    task_id = _create_task(client)

    with client.stream(
        "POST", f"/api/v1/tasks/{task_id}/messages", json={"content": "你好"}
    ) as response:
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())

    assert "event: start" in body
    assert "event: delta" in body
    assert "event: done" in body
    assert "你好" in body

    messages = client.get(f"/api/v1/tasks/{task_id}/messages").json()
    assert [item["role"] for item in messages["messages"]] == ["user", "assistant"]
    assert messages["messages"][0]["content"] == "你好"
    assert messages["messages"][1]["content"] == "你好，世界"
    assert messages["messages"][1]["usage"]["total_tokens"] == 15
    assert messages["task_usage"]["total_tokens"] == 15
    assert messages["messages"][1]["sequence"] == 2

    task = client.get(f"/api/v1/tasks/{task_id}").json()
    assert task["usage"]["total_tokens"] == 15

    # 第二轮对话：sequence 递增、usage 累加
    with client.stream(
        "POST", f"/api/v1/tasks/{task_id}/messages", json={"content": "继续"}
    ) as response:
        "".join(response.iter_text())
    messages = client.get(f"/api/v1/tasks/{task_id}/messages").json()
    assert len(messages["messages"]) == 4
    assert [item["sequence"] for item in messages["messages"]] == [1, 2, 3, 4]
    assert messages["task_usage"]["total_tokens"] == 30


def test_chat_uses_task_model_parameters(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(model_service, "resolve_model", fake_resolve)
    monkeypatch.setattr(model_service, "stream_chat", fake_stream)
    captured_params.clear()

    task_id = _create_task(client)
    with client.stream(
        "POST", f"/api/v1/tasks/{task_id}/messages", json={"content": "hi"}
    ) as response:
        "".join(response.iter_text())
    assert captured_params[-1] == {"temperature": None, "max_tokens": None}

    patched = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"temperature": 0.7, "max_tokens": 512},
    )
    assert patched.status_code == 200
    assert patched.json()["temperature"] == 0.7
    assert patched.json()["max_tokens"] == 512

    with client.stream(
        "POST", f"/api/v1/tasks/{task_id}/messages", json={"content": "again"}
    ) as response:
        "".join(response.iter_text())
    assert captured_params[-1] == {"temperature": 0.7, "max_tokens": 512}


def test_task_model_parameter_validation(client: TestClient) -> None:
    task = client.post("/api/v1/tasks", json={"title": "params"}).json()
    too_hot = client.patch(
        f"/api/v1/tasks/{task['id']}", json={"temperature": 3.0}
    )
    assert too_hot.status_code == 422
    bad_tokens = client.patch(
        f"/api/v1/tasks/{task['id']}", json={"max_tokens": 0}
    )
    assert bad_tokens.status_code == 422


def test_chat_falls_back_to_workspace_model_defaults(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(model_service, "resolve_model", fake_resolve)
    monkeypatch.setattr(model_service, "stream_chat", fake_stream)
    captured_params.clear()

    workspace_id = client.get("/api/v1/workspaces").json()[0]["id"]
    patched = client.patch(
        f"/api/v1/workspaces/{workspace_id}",
        json={"default_temperature": 0.3, "default_max_tokens": 256},
    )
    assert patched.status_code == 200

    task_id = _create_task(client)
    with client.stream(
        "POST", f"/api/v1/tasks/{task_id}/messages", json={"content": "hi"}
    ) as response:
        "".join(response.iter_text())
    assert captured_params[-1] == {"temperature": 0.3, "max_tokens": 256}

    # Task-level value overrides the workspace default
    client.patch(f"/api/v1/tasks/{task_id}", json={"temperature": 0.9})
    with client.stream(
        "POST", f"/api/v1/tasks/{task_id}/messages", json={"content": "again"}
    ) as response:
        "".join(response.iter_text())
    assert captured_params[-1] == {"temperature": 0.9, "max_tokens": 256}


def test_chat_error_does_not_fake_assistant_message(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(model_service, "resolve_model", fake_resolve)
    monkeypatch.setattr(model_service, "stream_chat", failing_stream)
    task_id = _create_task(client)

    with client.stream(
        "POST", f"/api/v1/tasks/{task_id}/messages", json={"content": "hi"}
    ) as response:
        body = "".join(response.iter_text())

    assert "event: error" in body
    messages = client.get(f"/api/v1/tasks/{task_id}/messages").json()
    assert [item["role"] for item in messages["messages"]] == ["user"]
    assert messages["task_usage"] is None


def test_chat_without_configured_provider_returns_422(
    client: TestClient, test_data_root, monkeypatch
) -> None:
    monkeypatch.setattr(
        provider_config, "config_path", lambda: test_data_root / "provider_config.json"
    )
    task_id = _create_task(client)
    response = client.post(
        f"/api/v1/tasks/{task_id}/messages", json={"content": "hi"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "model_required"
