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
