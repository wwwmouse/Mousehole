"""Phase 5 efficiency: clear/restore Chat context without deleting history."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.modules.model import service as model_service


def _fake_resolve(task_provider, task_model, request_provider=None, request_model=None):
    return "deepseek", "deepseek-chat", {}


def _create_task(client: TestClient) -> str:
    created = client.post("/api/v1/tasks", json={"title": "context test"})
    assert created.status_code == 201, created.text
    return created.json()["id"]


def _send(client: TestClient, task_id: str, content: str) -> None:
    with client.stream(
        "POST",
        f"/api/v1/tasks/{task_id}/messages",
        json={"content": content, "mode": "chat"},
    ) as response:
        assert response.status_code == 200
        "".join(response.iter_text())


def test_clear_and_restore_chat_context(client: TestClient, monkeypatch) -> None:
    captured: list[list[dict]] = []

    async def fake_stream(provider, model, messages, *, temperature=None, max_tokens=None):
        captured.append(messages)
        yield {"type": "delta", "text": "ok"}

    monkeypatch.setattr(model_service, "resolve_model", _fake_resolve)
    monkeypatch.setattr(model_service, "stream_chat", fake_stream)
    task_id = _create_task(client)

    _send(client, task_id, "first question")
    _send(client, task_id, "second question")

    # Clear: older messages stay in the database but are not sent to the model.
    cleared = client.patch(
        f"/api/v1/tasks/{task_id}/messages/context", json={"cleared": True}
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["context_cleared"] is True
    assert cleared.json()["context_start_sequence"] is not None

    stored = client.get(f"/api/v1/tasks/{task_id}/messages").json()
    assert stored["context_cleared"] is True
    assert stored["context_start_sequence"] == cleared.json()["context_start_sequence"]
    assert len(stored["messages"]) == 4  # nothing is deleted

    _send(client, task_id, "after clear")
    after_clear = captured[-1]
    assert "after clear" in str(after_clear)
    assert "first question" not in str(after_clear)
    assert "second question" not in str(after_clear)

    # Restore: old history is sent again.
    restored = client.patch(
        f"/api/v1/tasks/{task_id}/messages/context", json={"cleared": False}
    )
    assert restored.status_code == 200
    assert restored.json()["context_cleared"] is False
    assert restored.json()["context_start_sequence"] is None

    _send(client, task_id, "after restore")
    after_restore = captured[-1]
    assert "first question" in str(after_restore)
    assert "second question" in str(after_restore)
    assert "after clear" in str(after_restore)
