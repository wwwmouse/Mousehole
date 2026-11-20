from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.modules.artifact import service as artifact_service
from app.modules.execution import service as execution_service
from app.modules.model import service as model_service
from app.modules.task.models import Task


@pytest.fixture()
def configured_model(monkeypatch):
    monkeypatch.setattr(
        model_service,
        "resolve_model",
        lambda task_provider, task_model, request_provider=None, request_model=None: (
            task_provider or "deepseek",
            task_model or "deepseek-flash",
            {},
        ),
    )


def _create_task(client: TestClient) -> str:
    response = client.post("/api/v1/tasks", json={"title": "执行任务"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_create_list_cancel_execution(client: TestClient, configured_model) -> None:
    task_id = _create_task(client)
    created = client.post(f"/api/v1/tasks/{task_id}/executions")
    assert created.status_code == 202, created.text
    body = created.json()
    assert body["status"] == "pending"
    assert body["sequence"] == 1
    assert body["model_name"] == "deepseek-flash"
    assert body["skill_id"] == "multi_doc_analysis"
    assert body["skill_name"] == "多文档分析"

    listed = client.get(f"/api/v1/tasks/{task_id}/executions")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [body["id"]]

    detail = client.get(f"/api/v1/executions/{body['id']}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["steps"] == []
    assert payload["snapshots"] == []
    assert payload["artifact_ids"] == []

    cancelled = client.post(f"/api/v1/executions/{body['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    again = client.post(f"/api/v1/executions/{body['id']}/cancel")
    assert again.status_code == 409


def test_skills_endpoint_and_selected_skill(
    client: TestClient, configured_model
) -> None:
    skills = client.get("/api/v1/skills")
    assert skills.status_code == 200
    ids = {item["id"] for item in skills.json()}
    assert {"multi_doc_analysis", "content_summary"} <= ids

    task_id = _create_task(client)
    created = client.post(
        f"/api/v1/tasks/{task_id}/executions",
        json={"skill_id": "content_summary"},
    )
    assert created.status_code == 202
    assert created.json()["skill_id"] == "content_summary"
    assert created.json()["skill_name"] == "内容摘要"

    unknown = client.post(
        f"/api/v1/tasks/{task_id}/executions",
        json={"skill_id": "nope"},
    )
    assert unknown.status_code == 404


def test_execution_events_stream_for_terminal_execution(
    client: TestClient, configured_model, db_session
) -> None:
    task_id = _create_task(client)
    created = client.post(f"/api/v1/tasks/{task_id}/executions").json()

    task = db_session.get(Task, uuid.UUID(task_id))
    execution = execution_service.get_execution(db_session, uuid.UUID(created["id"]))
    execution_service.mark_running(db_session, execution)
    execution_service.complete(db_session, execution, usage={"total_tokens": 9})
    db_session.commit()

    with client.stream(
        "GET", f"/api/v1/executions/{created['id']}/events"
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    assert "event: snapshot" in body
    assert "event: execution.completed" in body


def test_artifact_endpoints(client: TestClient, configured_model, db_session) -> None:
    task_id = _create_task(client)
    task = db_session.get(Task, uuid.UUID(task_id))
    series = artifact_service.get_or_create_series(db_session, task, "分析报告")
    artifact = artifact_service.append_artifact(
        db_session, series, title="报告 v1", content="# hello"
    )
    db_session.commit()

    series_list = client.get(f"/api/v1/tasks/{task_id}/artifact-series")
    assert series_list.status_code == 200
    assert series_list.json()[0]["title"] == "分析报告"

    detail = client.get(f"/api/v1/artifact-series/{series.id}")
    assert detail.status_code == 200
    assert detail.json()["artifacts"][0]["content"] == "# hello"

    renamed = client.patch(
        f"/api/v1/artifact-series/{series.id}", json={"title": "新报告"}
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "新报告"

    artifact_read = client.get(f"/api/v1/artifacts/{artifact.id}")
    assert artifact_read.status_code == 200
    assert artifact_read.json()["version"] == 1
