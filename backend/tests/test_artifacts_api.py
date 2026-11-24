from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.modules.artifact import service as artifact_service
from app.modules.task.models import Task


def test_download_and_delete_artifact(client: TestClient, db_session) -> None:
    task = client.post("/api/v1/tasks", json={"title": "artifact"}).json()
    task_row = db_session.get(Task, uuid.UUID(task["id"]))
    series = artifact_service.get_or_create_series(db_session, task_row, "系列")
    first = artifact_service.append_artifact(
        db_session, series, title="文档 v1", content="# hello\n\nworld"
    )
    db_session.commit()

    download = client.get(f"/api/v1/artifacts/{first.id}/download")
    assert download.status_code == 200
    assert download.text == "# hello\n\nworld"
    assert "attachment" in download.headers["content-disposition"]

    deleted = client.delete(f"/api/v1/artifacts/{first.id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/artifact-series/{series.id}").status_code == 404


def _make_artifact(client: TestClient, db_session, content: str = "# report"):
    task = client.post("/api/v1/tasks", json={"title": "export"}).json()
    task_row = db_session.get(Task, uuid.UUID(task["id"]))
    series = artifact_service.get_or_create_series(db_session, task_row, "导出系列")
    artifact = artifact_service.append_artifact(
        db_session, series, title="导出报告", content=content
    )
    db_session.commit()
    return task, artifact


def test_export_artifact_to_library(client: TestClient, db_session) -> None:
    _task, artifact = _make_artifact(client, db_session, "# report\n\nbody")

    response = client.post(f"/api/v1/artifacts/{artifact.id}/to-library")
    assert response.status_code == 201, response.text
    exported = response.json()
    assert exported["filename"] == "导出报告.md"
    assert exported["file_type"] == "md"
    assert exported["size"] > 0

    content = client.get(f"/api/v1/files/{exported['id']}/content").json()
    assert content["text"] == "# report\n\nbody"

    files = client.get("/api/v1/files").json()
    assert any(item["id"] == exported["id"] for item in files)

    # Identical content is content-addressed and reuses the existing File row.
    again = client.post(f"/api/v1/artifacts/{artifact.id}/to-library")
    assert again.status_code == 201
    assert again.json()["id"] == exported["id"]


def test_export_artifact_with_empty_content_fails(
    client: TestClient, db_session
) -> None:
    _task, artifact = _make_artifact(client, db_session, "   ")
    response = client.post(f"/api/v1/artifacts/{artifact.id}/to-library")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unprocessable"


def test_export_unknown_artifact_returns_404(client: TestClient) -> None:
    response = client.post(f"/api/v1/artifacts/{uuid.uuid4()}/to-library")
    assert response.status_code == 404
