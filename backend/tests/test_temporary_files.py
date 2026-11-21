from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.modules.task.models import Task


def _create_task(client: TestClient) -> str:
    response = client.post("/api/v1/tasks", json={"title": "temp file task"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_temporary_file_is_only_used_for_one_turn(
    client: TestClient, monkeypatch
) -> None:
    from app.modules.model import service as model_service

    captured: list[list[dict]] = []

    async def capture_stream(provider, model, messages, **kwargs):
        captured.append(messages)
        yield {"type": "delta", "text": "好的"}

    monkeypatch.setattr(model_service, "resolve_model", lambda *a, **k: ("fake", "fake", None))
    monkeypatch.setattr(model_service, "stream_chat", capture_stream)

    task_id = _create_task(client)
    uploaded = client.post(
        f"/api/v1/tasks/{task_id}/files/upload",
        files={"file": ("temp-note.md", b"# TEMP-UNIQUE-CONTENT", "text/markdown")},
    )
    assert uploaded.status_code == 201, uploaded.text
    file_id = uploaded.json()["id"]

    # Not in the Library and not part of the Task's persistent context.
    library = client.get("/api/v1/files").json()
    assert all(item["id"] != file_id for item in library)
    context = client.get(f"/api/v1/tasks/{task_id}/files").json()
    assert all(item["file"]["id"] != file_id for item in context["available"])

    # First turn explicitly attaches the temporary file.
    with client.stream(
        "POST",
        f"/api/v1/tasks/{task_id}/messages",
        json={"content": "总结一下", "file_ids": [file_id]},
    ) as response:
        "".join(response.iter_text())
    assert "TEMP-UNIQUE-CONTENT" in captured[-1][0]["content"]
    messages = client.get(f"/api/v1/tasks/{task_id}/messages").json()["messages"]
    assert messages[0]["metadata"]["files"][0]["filename"] == "temp-note.md"
    assert messages[0]["metadata"]["files"][0]["source"] == "temporary"

    # Second turn must NOT carry the file.
    with client.stream(
        "POST", f"/api/v1/tasks/{task_id}/messages", json={"content": "继续"}
    ) as response:
        "".join(response.iter_text())
    assert "TEMP-UNIQUE-CONTENT" not in captured[-1][0]["content"]
    assert all(
        "temp-note.md" not in str(message.get("content", ""))
        for message in captured[-1]
    )

    # Removing the attachment discards the hidden file.
    assert client.delete(f"/api/v1/tasks/{task_id}/files/{file_id}").status_code == 204
    assert client.get(f"/api/v1/files/{file_id}").status_code == 404


def test_normal_upload_still_appears_in_library(client: TestClient) -> None:
    uploaded = client.post(
        "/api/v1/files",
        files={"file": ("library-note.md", b"# library", "text/markdown")},
    )
    assert uploaded.status_code == 201
    library = client.get("/api/v1/files").json()
    assert any(item["id"] == uploaded.json()["id"] for item in library)


def test_deleting_task_discards_temporary_files(client: TestClient) -> None:
    task_id = _create_task(client)
    uploaded = client.post(
        f"/api/v1/tasks/{task_id}/files/upload",
        files={"file": ("task-only.md", b"# only", "text/markdown")},
    ).json()

    assert client.delete(f"/api/v1/tasks/{task_id}").status_code == 204
    assert client.get(f"/api/v1/files/{uploaded['id']}").status_code == 404
