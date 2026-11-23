"""Phase 5 H4: chat/work modes; the model decides tool usage in work mode."""
from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.v1.chat import _build_messages
from app.modules.conversation.schemas import ChatRequest
from app.modules.model import service as model_service


def _fake_task() -> SimpleNamespace:
    return SimpleNamespace(title="mode task", description="mode test")


def test_chat_mode_system_prompt_explains_no_tools() -> None:
    messages = _build_messages(_fake_task(), [], mode="chat")
    system = messages[0]["content"]
    assert "对话模式" in system
    assert "save_artifact" not in system
    assert "工作模式" in system  # tells the user how to switch


def test_work_mode_system_prompt_lists_all_tools() -> None:
    messages = _build_messages(_fake_task(), [], include_tools=True, mode="work")
    system = messages[0]["content"]
    assert "工作模式" in system
    for name in ("read_task_files", "read_task_file", "save_artifact", "create_execution"):
        assert name in system
    # A trailer after history is what actually overrides old "no tools" answers.
    assert messages[-1]["role"] == "system"
    assert "save_artifact" in messages[-1]["content"]


def test_chat_mode_has_no_work_mode_tool_reminder() -> None:
    messages = _build_messages(_fake_task(), [], mode="chat")
    assert all("工作模式工具提醒" not in message["content"] for message in messages)


def test_tool_history_includes_reasoning_content_when_available() -> None:
    history = [
        SimpleNamespace(
            role="assistant",
            content="previous answer",
            message_metadata={"reasoning_content": "previous chain of thought"},
        ),
        SimpleNamespace(role="user", content="next", message_metadata=None),
    ]
    with_reasoning = _build_messages(
        _fake_task(),
        history,
        include_tools=True,
        mode="work",
        include_reasoning=True,
    )
    assert with_reasoning[1]["reasoning_content"] == "previous chain of thought"

    without_reasoning = _build_messages(
        _fake_task(),
        history,
        include_tools=True,
        mode="work",
    )
    assert "reasoning_content" not in without_reasoning[1]


def _fake_resolve(task_provider, task_model, request_provider=None, request_model=None):
    return "deepseek", "deepseek-chat", {}


def _create_task(client: TestClient) -> str:
    created = client.post("/api/v1/tasks", json={"title": "mode test"})
    assert created.status_code == 201, created.text
    return created.json()["id"]


def test_chat_request_mode_defaults_to_work() -> None:
    assert ChatRequest(content="hi").mode == "work"
    assert ChatRequest(content="hi", mode="chat").mode == "chat"
    assert ChatRequest(content="hi", mode="work").mode == "work"


def test_chat_request_rejects_unknown_mode() -> None:
    try:
        ChatRequest(content="hi", mode="bogus")
    except ValueError:
        return
    raise AssertionError("unknown mode should be rejected")


def test_chat_mode_never_offers_tools(client: TestClient, monkeypatch) -> None:
    calls: list[int] = []

    async def recorder(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("tool pre-pass must not run in chat mode")

    async def fake_stream(provider, model, messages, *, temperature=None, max_tokens=None):
        yield {"type": "delta", "text": "这是对话模式的回答。"}

    monkeypatch.setattr(model_service, "resolve_model", _fake_resolve)
    monkeypatch.setattr(model_service, "complete_chat", recorder)
    monkeypatch.setattr(model_service, "stream_chat", fake_stream)
    task_id = _create_task(client)

    with client.stream(
        "POST",
        f"/api/v1/tasks/{task_id}/messages",
        json={"content": "把这段保存为成果", "mode": "chat"},
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    assert calls == []
    assert "event: tool_call" not in body
    assert "event: tool_result" not in body
    assert client.get(f"/api/v1/tasks/{task_id}/artifact-series").json() == []

    stored = client.get(f"/api/v1/tasks/{task_id}/messages").json()["messages"]
    assert stored[0]["metadata"]["mode"] == "chat"
    assert stored[1]["metadata"]["mode"] == "chat"


def test_work_mode_always_runs_tool_prepass(client: TestClient, monkeypatch) -> None:
    calls: list[dict] = []

    async def complete_chat(provider, model, messages, *, tools=None, temperature=None, max_tokens=None, thinking=None):
        calls.append({"tools": tools, "messages": messages, "thinking": thinking})
        return {"content": "", "tool_calls": []}

    async def fake_stream(provider, model, messages, *, temperature=None, max_tokens=None):
        yield {"type": "delta", "text": "工作模式回答。"}

    monkeypatch.setattr(model_service, "resolve_model", _fake_resolve)
    monkeypatch.setattr(model_service, "complete_chat", complete_chat)
    monkeypatch.setattr(model_service, "stream_chat", fake_stream)
    task_id = _create_task(client)

    with client.stream(
        "POST",
        f"/api/v1/tasks/{task_id}/messages",
        json={"content": "你好", "mode": "work"},
    ) as response:
        assert response.status_code == 200
        "".join(response.iter_text())

    assert len(calls) == 1
    tool_names = {item["function"]["name"] for item in calls[0]["tools"]}
    assert tool_names == {
        "read_task_files",
        "read_task_file",
        "save_artifact",
        "create_execution",
    }
    stored = client.get(f"/api/v1/tasks/{task_id}/messages").json()["messages"]
    assert stored[0]["metadata"]["mode"] == "work"


def test_chat_mode_does_not_auto_save_artifact(client: TestClient, monkeypatch) -> None:
    """Regression: no deterministic artifact fallback exists anymore."""

    async def fake_stream(provider, model, messages, *, temperature=None, max_tokens=None):
        yield {"type": "delta", "text": "抱歉，对话模式不能保存成果。"}

    monkeypatch.setattr(model_service, "resolve_model", _fake_resolve)
    monkeypatch.setattr(model_service, "stream_chat", fake_stream)
    task_id = _create_task(client)

    with client.stream(
        "POST",
        f"/api/v1/tasks/{task_id}/messages",
        json={"content": "保存为成果", "mode": "chat"},
    ) as response:
        "".join(response.iter_text())

    assert client.get(f"/api/v1/tasks/{task_id}/artifact-series").json() == []


def test_tool_loop_passes_reasoning_content_back(
    client: TestClient, monkeypatch
) -> None:
    calls: list[list[dict]] = []

    async def complete_chat(provider, model, messages, *, tools=None, temperature=None, max_tokens=None, thinking=None):
        calls.append(messages)
        if len(calls) == 1:
            return {
                "content": "",
                "reasoning_content": "chain-of-thought-1",
                "tool_calls": [
                    {"id": "call_1", "name": "read_task_files", "arguments": "{}"}
                ],
            }
        return {"content": "", "reasoning_content": "chain-of-thought-2", "tool_calls": []}

    async def fake_stream(provider, model, messages, *, temperature=None, max_tokens=None):
        yield {"type": "delta", "text": "完成。"}

    monkeypatch.setattr(model_service, "resolve_model", _fake_resolve)
    monkeypatch.setattr(model_service, "complete_chat", complete_chat)
    monkeypatch.setattr(model_service, "stream_chat", fake_stream)
    task_id = _create_task(client)

    with client.stream(
        "POST",
        f"/api/v1/tasks/{task_id}/messages",
        json={"content": "看看文件", "mode": "work"},
    ) as response:
        "".join(response.iter_text())

    assert len(calls) == 2
    assistant = next(
        message for message in calls[1] if message.get("role") == "assistant"
    )
    assert assistant["reasoning_content"] == "chain-of-thought-1"


def test_legacy_history_without_reasoning_disables_thinking(
    client: TestClient, monkeypatch
) -> None:
    thinking_flags: list[bool | None] = []

    async def complete_chat(provider, model, messages, *, tools=None, temperature=None, max_tokens=None, thinking=None):
        thinking_flags.append(thinking)
        return {"content": "", "tool_calls": []}

    async def fake_stream(provider, model, messages, *, temperature=None, max_tokens=None):
        yield {"type": "delta", "text": "ok"}

    monkeypatch.setattr(model_service, "resolve_model", _fake_resolve)
    monkeypatch.setattr(model_service, "complete_chat", complete_chat)
    monkeypatch.setattr(model_service, "stream_chat", fake_stream)
    task_id = _create_task(client)

    for content in ("第一轮", "第二轮"):
        with client.stream(
            "POST",
            f"/api/v1/tasks/{task_id}/messages",
            json={"content": content, "mode": "work"},
        ) as response:
            "".join(response.iter_text())

    # The first assistant message has no stored reasoning_content, so the next
    # tool-carrying request must disable thinking to avoid DeepSeek V4 400s.
    assert thinking_flags[-1] is False
