from __future__ import annotations

import json

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
    assert captured_params[-1] == {"temperature": 0.7, "max_tokens": 4096}

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


def test_chat_message_lists_only_temporary_files(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(model_service, "resolve_model", fake_resolve)

    async def capture_stream(provider, model, messages, **kwargs):
        yield {"type": "delta", "text": "ok"}

    monkeypatch.setattr(model_service, "stream_chat", capture_stream)

    task_id = _create_task(client)
    uploaded = client.post(
        "/api/v1/files",
        files={"file": ("temp.md", b"# temp", "text/markdown")},
    ).json()
    linked = client.post(
        f"/api/v1/tasks/{task_id}/files",
        json={"file_id": uploaded["id"], "action": "include"},
    )
    assert linked.status_code in (200, 201), linked.text

    with client.stream(
        "POST", f"/api/v1/tasks/{task_id}/messages", json={"content": "hi"}
    ) as response:
        "".join(response.iter_text())

    stored = client.get(f"/api/v1/tasks/{task_id}/messages").json()["messages"]
    files_meta = stored[0]["metadata"]["files"]
    assert [item["filename"] for item in files_meta] == ["temp.md"]
    assert files_meta[0]["source"] == "task_added"


def test_chat_uses_selected_skill(client: TestClient, monkeypatch) -> None:
    captured: list[list[dict]] = []

    async def capture_stream(provider, model, messages, **kwargs):
        captured.append(messages)
        yield {"type": "delta", "text": "ok"}

    monkeypatch.setattr(model_service, "resolve_model", fake_resolve)
    monkeypatch.setattr(model_service, "stream_chat", capture_stream)

    task_id = _create_task(client)
    skill = next(
        item
        for item in client.get("/api/v1/skills").json()
        if item["name"] == "内容摘要"
    )
    with client.stream(
        "POST",
        f"/api/v1/tasks/{task_id}/messages",
        json={"content": "总结一下", "skill_id": skill["id"]},
    ) as response:
        "".join(response.iter_text())

    system = captured[-1][0]["content"]
    assert "内容摘要" in system
    assert "总结" in system

    stored = client.get(f"/api/v1/tasks/{task_id}/messages").json()["messages"]
    assert stored[0]["metadata"]["skill"]["name"] == "内容摘要"
    assert stored[0]["metadata"]["files"] == []
    assert stored[1]["metadata"]["tools"] == []
    assert stored[1]["metadata"]["duration_ms"] >= 0

    unknown = client.post(
        f"/api/v1/tasks/{task_id}/messages",
        json={"content": "hi", "skill_id": "00000000-0000-4000-8000-000000000000"},
    )
    assert unknown.status_code == 404


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


def test_chat_includes_available_files_in_context(
    client: TestClient, monkeypatch
) -> None:
    captured: list[list[dict]] = []

    async def capture_stream(provider, model, messages, **kwargs):
        captured.append(messages)
        yield {"type": "delta", "text": "看到了"}

    monkeypatch.setattr(model_service, "resolve_model", fake_resolve)
    monkeypatch.setattr(model_service, "stream_chat", capture_stream)

    project = client.post("/api/v1/projects", json={"name": "ctx"}).json()
    upload = client.post(
        "/api/v1/files",
        files={
            "file": (
                "notes.md",
                "# 资料\n\n项目继承的独特内容XYZ。".encode(),
                "text/markdown",
            )
        },
    ).json()
    linked = client.post(
        f"/api/v1/projects/{project['id']}/files",
        json={"file_id": upload["id"]},
    )
    assert linked.status_code in (200, 201), linked.text
    task = client.post(
        "/api/v1/tasks",
        json={"title": "ctx task", "project_id": project["id"]},
    ).json()

    with client.stream(
        "POST", f"/api/v1/tasks/{task['id']}/messages", json={"content": "文件里写了什么"}
    ) as response:
        "".join(response.iter_text())

    system = captured[-1][0]["content"]
    assert "notes.md" in system
    assert "项目继承" in system
    assert "独特内容XYZ" in system

    stored = client.get(f"/api/v1/tasks/{task['id']}/messages").json()["messages"]
    # Project-inherited files are context, not per-message attachments.
    assert stored[0]["metadata"]["files"] == []


def test_stream_heartbeat_emits_thinking() -> None:
    import asyncio

    from app.api.v1.chat import _stream_with_heartbeat

    async def slow_stream():
        await asyncio.sleep(2.2)
        yield {"type": "delta", "text": "x"}

    async def collect() -> list[dict]:
        return [event async for event in _stream_with_heartbeat(slow_stream())]

    events = asyncio.run(collect())
    assert any(event["type"] == "thinking" for event in events)
    assert events[-1] == {"type": "delta", "text": "x"}


def _tool_call_complete(tool_name: str, arguments: dict):
    state = {"called": 0}

    async def fake_complete(provider, model, messages, *, tools=None, **kwargs):
        state["called"] += 1
        if state["called"] == 1:
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "name": tool_name,
                        "arguments": json.dumps(arguments, ensure_ascii=False),
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
            }
        return {
            "content": "已完成。",
            "tool_calls": [],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
        }

    return fake_complete


async def _unexpected_stream(provider, model, messages, **kwargs):
    raise AssertionError("stream_chat should not be called when tools finish the turn")
    yield  # pragma: no cover


def test_chat_tool_saves_artifact_with_chat_source(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(model_service, "resolve_model", fake_resolve)
    monkeypatch.setattr(
        model_service,
        "complete_chat",
        _tool_call_complete(
            "save_artifact",
            {"title": "对话成果", "content": "# 来自对话的成果", "series_title": "对话系列"},
        ),
    )
    monkeypatch.setattr(model_service, "stream_chat", _unexpected_stream)
    task_id = _create_task(client)

    with client.stream(
        "POST", f"/api/v1/tasks/{task_id}/messages", json={"content": "帮我总结成成果"}
    ) as response:
        body = "".join(response.iter_text())

    assert "event: tool_call" in body
    assert "event: tool_result" in body
    assert "event: done" in body
    done_line = next(
        line for line in body.splitlines() if "artifacts" in line and "message_id" in line
    )
    payload = json.loads(done_line.split("data: ", 1)[1])
    assert len(payload["artifacts"]) == 1

    series_list = client.get(f"/api/v1/tasks/{task_id}/artifact-series").json()
    assert series_list[0]["title"] == "对话系列"
    detail = client.get(f"/api/v1/artifact-series/{series_list[0]['id']}").json()
    artifact = detail["artifacts"][0]
    assert artifact["content"] == "# 来自对话的成果"
    assert artifact["source_type"] == "chat"
    assert artifact["source_message_id"] == payload["message_id"]

    messages = client.get(f"/api/v1/tasks/{task_id}/messages").json()
    assert messages["messages"][-1]["content"] == "已完成。"
    assistant_meta = messages["messages"][-1]["metadata"]
    assert assistant_meta["tools"][0]["name"] == "save_artifact"
    assert assistant_meta["tools"][0]["ok"] is True


def test_chat_saves_artifact_when_model_omits_tool(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(model_service, "resolve_model", fake_resolve)

    async def doc_stream(provider, model, messages, **kwargs):
        yield {"type": "delta", "text": "这是文档内容。"}

    monkeypatch.setattr(model_service, "stream_chat", doc_stream)
    task_id = _create_task(client)

    with client.stream(
        "POST",
        f"/api/v1/tasks/{task_id}/messages",
        json={"content": "帮我写一份文档并保存为成果"},
    ) as response:
        body = "".join(response.iter_text())

    assert "event: tool_result" in body
    done_line = next(
        line for line in body.splitlines() if "artifacts" in line and "message_id" in line
    )
    payload = json.loads(done_line.split("data: ", 1)[1])
    assert len(payload["artifacts"]) == 1

    series = client.get(f"/api/v1/tasks/{task_id}/artifact-series").json()
    detail = client.get(f"/api/v1/artifact-series/{series[0]['id']}").json()
    assert detail["artifacts"][0]["content"] == "这是文档内容。"
    assert detail["artifacts"][0]["source_type"] == "chat"


def test_chat_tool_creates_execution(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(model_service, "resolve_model", fake_resolve)
    monkeypatch.setattr(
        model_service,
        "complete_chat",
        _tool_call_complete("create_execution", {}),
    )
    task_id = _create_task(client)

    with client.stream(
        "POST", f"/api/v1/tasks/{task_id}/messages", json={"content": "做多文档分析"}
    ) as response:
        body = "".join(response.iter_text())

    assert "event: tool_result" in body
    executions = client.get(f"/api/v1/tasks/{task_id}/executions").json()
    assert len(executions) == 1
    assert executions[0]["status"] == "pending"
    assert executions[0]["skill_name"] == "多文档分析"


def test_chat_tool_read_task_files(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(model_service, "resolve_model", fake_resolve)
    monkeypatch.setattr(
        model_service,
        "complete_chat",
        _tool_call_complete("read_task_files", {}),
    )
    task_id = _create_task(client)

    with client.stream(
        "POST", f"/api/v1/tasks/{task_id}/messages", json={"content": "有哪些文件"}
    ) as response:
        body = "".join(response.iter_text())

    assert "event: tool_call" in body
    assert "tool_result" in body
    assert "已完成。" in body


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
