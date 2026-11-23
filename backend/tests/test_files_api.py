from __future__ import annotations

import uuid
from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.modules.file import service as file_service
from app.modules.file.models import File


def upload(
    client: TestClient,
    filename: str,
    data: bytes = b"content",
    content_type: str = "application/octet-stream",
) -> object:
    return client.post(
        "/api/v1/files", files={"file": (filename, data, content_type)}
    )


def test_upload_query_and_content(client: TestClient) -> None:
    data = b"# Hello\r\n\r\n\r\nWorld  \r\n"
    created = upload(client, "Notes.MD", data, "text/markdown")
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["filename"] == "Notes.MD"
    assert body["file_type"] == "md"
    assert body["mime_type"] == "text/markdown"
    assert body["size"] == len(data)
    assert body["status"] == "active"
    assert len(body["content_hash"]) == 64
    file_id = body["id"]

    listed = client.get("/api/v1/files")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [file_id]

    searched = client.get("/api/v1/files", params={"search": "notes"})
    assert [item["id"] for item in searched.json()] == [file_id]
    assert client.get("/api/v1/files", params={"search": "missing"}).json() == []
    assert client.get("/api/v1/files", params={"file_type": "pdf"}).json() == []
    assert client.get("/api/v1/files", params={"file_type": "md"}).json()[0][
        "id"
    ] == file_id
    assert client.get("/api/v1/files", params={"file_type": "markdown"}).json()[0][
        "id"
    ] == file_id

    detail = client.get(f"/api/v1/files/{file_id}")
    assert detail.status_code == 200
    assert detail.json()["references"] == []

    content = client.get(f"/api/v1/files/{file_id}/content")
    assert content.status_code == 200, content.text
    payload = content.json()
    assert payload["file"]["id"] == file_id
    assert payload["text"] == "# Hello\n\nWorld"
    assert payload["truncated"] is False

    truncated = client.get(
        f"/api/v1/files/{file_id}/content", params={"max_chars": 5}
    )
    assert truncated.status_code == 200
    assert truncated.json()["truncated"] is True
    assert truncated.json()["text"] == "# Hel"

    missing = client.get(f"/api/v1/files/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


def test_upload_structured_and_design_text_formats(client: TestClient) -> None:
    cases = [
        ("metadata.json", b'{"name":"skill","version":1}', "json", "application/json"),
        ("config.yaml", b"name: skill\nversion: 1\n", "yaml", "application/yaml"),
        ("config.yml", b"name: skill\n", "yaml", "application/yaml"),
        ("table.csv", b"name,value\na,1\n", "csv", "text/csv"),
        ("page.html", b"<h1>Hello</h1>", "html", "text/html"),
        ("style.css", b"h1 { color: red; }", "css", "text/css"),
    ]
    for filename, data, file_type, mime_type in cases:
        created = upload(client, filename, data)
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["file_type"] == file_type
        assert body["mime_type"] == mime_type
        content = client.get(f"/api/v1/files/{body['id']}/content")
        assert content.status_code == 200, content.text
        assert content.json()["text"]


def test_upload_rejects_unsupported_empty_and_oversized(
    client: TestClient, monkeypatch
) -> None:
    unsupported = upload(client, "report.docx", b"docx bytes")
    assert unsupported.status_code == 415
    assert unsupported.json()["error"]["code"] == "unsupported_file_type"

    no_extension = upload(client, "README", b"hello")
    assert no_extension.status_code == 415

    empty = upload(client, "empty.txt", b"")
    assert empty.status_code == 422
    assert empty.json()["error"]["code"] == "unprocessable"

    monkeypatch.setattr(
        file_service,
        "get_settings",
        lambda: SimpleNamespace(max_upload_bytes=10),
    )
    too_large = upload(client, "big.txt", b"x" * 11)
    assert too_large.status_code == 413
    assert too_large.json()["error"]["code"] == "payload_too_large"


def test_upload_uses_basename_and_markdown_extension(client: TestClient) -> None:
    created = upload(client, "C:/fake/dir/report.txt", b"hello")
    assert created.status_code == 201, created.text
    assert created.json()["filename"] == "report.txt"

    markdown = upload(client, "readme.markdown", b"# readme")
    assert markdown.status_code == 201, markdown.text
    assert markdown.json()["file_type"] == "md"
    assert markdown.json()["mime_type"] == "text/markdown"


def test_reupload_same_content_reuses_existing_file(client: TestClient) -> None:
    first = upload(client, "same.txt", b"duplicate content").json()
    second = upload(client, "same.txt", b"duplicate content")
    assert second.status_code == 201
    assert second.json()["id"] == first["id"]
    assert len(client.get("/api/v1/files").json()) == 1

    assert client.delete(f"/api/v1/files/{first['id']}").status_code == 204
    restored = upload(client, "same.txt", b"duplicate content")
    assert restored.status_code == 201
    assert restored.json()["id"] == first["id"]
    assert restored.json()["status"] == "active"
    assert len(client.get("/api/v1/files").json()) == 1


def test_delete_blocked_by_project_and_task_references(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "Docs"}).json()
    uploaded = upload(client, "spec.md", b"# Spec").json()
    file_id = uploaded["id"]
    attached = client.post(
        f"/api/v1/projects/{project['id']}/files", json={"file_id": file_id}
    )
    assert attached.status_code == 201, attached.text

    blocked = client.delete(f"/api/v1/files/{file_id}")
    assert blocked.status_code == 409
    details = blocked.json()["error"]["details"]
    assert details["projects"] == [{"id": project["id"], "name": "Docs"}]
    assert details["tasks"] == []

    detail = client.get(f"/api/v1/files/{file_id}").json()
    assert detail["references"] == [
        {"kind": "project", "id": project["id"], "name": "Docs"}
    ]

    removed = client.delete(f"/api/v1/projects/{project['id']}/files/{file_id}")
    assert removed.status_code == 204

    task = client.post("/api/v1/tasks", json={"title": "临时分析"}).json()
    included = client.post(
        f"/api/v1/tasks/{task['id']}/files",
        json={"file_id": file_id, "action": "include"},
    )
    assert included.status_code == 201, included.text

    blocked_by_task = client.delete(f"/api/v1/files/{file_id}")
    assert blocked_by_task.status_code == 409
    task_details = blocked_by_task.json()["error"]["details"]
    assert task_details["projects"] == []
    assert task_details["tasks"] == [{"id": task["id"], "title": "临时分析"}]

    detail = client.get(f"/api/v1/files/{file_id}").json()
    assert detail["references"] == [
        {"kind": "task", "id": task["id"], "name": "临时分析"}
    ]

    removed_override = client.delete(
        f"/api/v1/tasks/{task['id']}/files/{file_id}"
    )
    assert removed_override.status_code == 204

    assert client.delete(f"/api/v1/files/{file_id}").status_code == 204
    assert client.get(f"/api/v1/files/{file_id}").status_code == 404
    assert client.get(f"/api/v1/files/{file_id}/content").status_code == 404
    assert client.delete(f"/api/v1/files/{file_id}").status_code == 404
    assert client.get("/api/v1/files").json() == []


def test_deleted_file_hidden_by_default_and_status_filter(client: TestClient) -> None:
    file = upload(client, "gone.txt", b"gone").json()
    assert client.delete(f"/api/v1/files/{file['id']}").status_code == 204

    assert client.get("/api/v1/files").json() == []
    deleted = client.get("/api/v1/files", params={"status": "deleted"})
    assert deleted.status_code == 200
    assert [item["id"] for item in deleted.json()] == [file["id"]]

    invalid = client.get("/api/v1/files", params={"status": "archived"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "unprocessable"


def test_list_is_ordered_by_created_at_desc(
    client: TestClient, db_session: Session
) -> None:
    first = upload(client, "first.txt", b"first").json()
    second = upload(client, "second.txt", b"second").json()

    db_session.execute(
        update(File)
        .where(File.id == uuid.UUID(first["id"]))
        .values(created_at=datetime(2025, 1, 1))
        .execution_options(synchronize_session=False)
    )
    db_session.execute(
        update(File)
        .where(File.id == uuid.UUID(second["id"]))
        .values(created_at=datetime(2025, 1, 2))
        .execution_options(synchronize_session=False)
    )
    db_session.commit()

    listed = client.get("/api/v1/files").json()
    assert [item["id"] for item in listed] == [second["id"], first["id"]]
