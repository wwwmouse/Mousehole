from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.modules.artifact import service as artifact_service
from app.modules.conversation.models import Conversation, Message
from app.modules.execution.models import Execution
from app.modules.task.models import Task


def test_delete_project_when_empty(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "P"}).json()
    assert client.delete(f"/api/v1/projects/{project['id']}").status_code == 204
    assert client.get(f"/api/v1/projects/{project['id']}").status_code == 404


def test_delete_project_with_tasks_conflicts(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "P"}).json()
    client.post(
        "/api/v1/tasks", json={"project_id": project["id"], "title": "T"}
    )
    res = client.delete(f"/api/v1/projects/{project['id']}")
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "conflict"


def test_delete_task(client: TestClient) -> None:
    task = client.post("/api/v1/tasks", json={"title": "T"}).json()
    assert client.delete(f"/api/v1/tasks/{task['id']}").status_code == 204
    assert client.get(f"/api/v1/tasks/{task['id']}").status_code == 404


def test_delete_task_cascades_conversation_execution_and_artifact(
    client: TestClient, db_session
) -> None:
    task = client.post("/api/v1/tasks", json={"title": "with dependents"}).json()
    task_id = uuid.UUID(task["id"])
    task_row = db_session.get(Task, task_id)
    assert task_row is not None

    series = artifact_service.get_or_create_series(db_session, task_row, "系列")
    artifact = artifact_service.append_artifact(
        db_session, series, title="报告", content="# hello"
    )
    execution = Execution(task_id=task_id, sequence=1, status="pending")
    conversation = Conversation(task_id=task_id)
    db_session.add_all([execution, conversation])
    db_session.flush()
    db_session.add(
        Message(
            conversation_id=conversation.id,
            role="user",
            content="hi",
            sequence=1,
        )
    )
    db_session.commit()
    execution_id = execution.id
    conversation_id = conversation.id
    artifact_id = artifact.id
    series_id = series.id

    response = client.delete(f"/api/v1/tasks/{task['id']}")
    assert response.status_code == 204, response.text

    db_session.expire_all()
    assert db_session.get(Task, task_id) is None
    assert db_session.get(Execution, execution_id) is None
    assert db_session.get(Conversation, conversation_id) is None
    assert db_session.get(type(artifact), artifact_id) is None
    assert db_session.get(type(series), series_id) is None


def test_task_bind_project_once(client: TestClient) -> None:
    task = client.post("/api/v1/tasks", json={"title": "T"}).json()
    assert task["project_id"] is None

    project_a = client.post("/api/v1/projects", json={"name": "A"}).json()
    project_b = client.post("/api/v1/projects", json={"name": "B"}).json()

    # 绑定一次
    bound = client.patch(
        f"/api/v1/tasks/{task['id']}", json={"project_id": project_a["id"]}
    )
    assert bound.status_code == 200
    assert bound.json()["project_id"] == project_a["id"]

    # 幂等：再次传相同值
    same = client.patch(
        f"/api/v1/tasks/{task['id']}", json={"project_id": project_a["id"]}
    )
    assert same.status_code == 200

    # 变更 -> 422
    changed = client.patch(
        f"/api/v1/tasks/{task['id']}", json={"project_id": project_b["id"]}
    )
    assert changed.status_code == 422

    # 解除 -> 422
    unbound = client.patch(
        f"/api/v1/tasks/{task['id']}", json={"project_id": None}
    )
    assert unbound.status_code == 422
