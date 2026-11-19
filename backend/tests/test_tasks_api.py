from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_task_in_project_and_workspace_consistency(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "P"}).json()

    created = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project["id"],
            "title": "分析 Agent 架构",
            "description": "整理核心概念",
        },
    )
    assert created.status_code == 201, created.text
    task = created.json()
    assert task["workspace_id"] == project["workspace_id"]
    assert task["project_id"] == project["id"]

    listed = client.get("/api/v1/tasks", params={"project_id": project["id"]})
    assert listed.status_code == 200
    assert [t["id"] for t in listed.json()] == [task["id"]]


def test_global_task_and_status_update(client: TestClient) -> None:
    task = client.post("/api/v1/tasks", json={"title": "临时任务"}).json()
    assert task["project_id"] is None

    updated = client.patch(
        f"/api/v1/tasks/{task['id']}", json={"status": "completed"}
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "completed"

    invalid = client.patch(f"/api/v1/tasks/{task['id']}", json={"status": "done"})
    assert invalid.status_code == 422


def test_task_model_fields_and_project_change_rejected(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "P"}).json()
    task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project["id"],
            "title": "T",
            "model_provider": "deepseek",
            "model_name": "deepseek-chat",
        },
    ).json()
    assert task["model_provider"] == "deepseek"

    changed = client.patch(
        f"/api/v1/tasks/{task['id']}", json={"project_id": str(project["id"])}
    )
    assert changed.status_code == 200  # unchanged value is accepted

    other = client.post("/api/v1/projects", json={"name": "Other"}).json()
    rejected = client.patch(
        f"/api/v1/tasks/{task['id']}", json={"project_id": other["id"]}
    )
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "unprocessable"
