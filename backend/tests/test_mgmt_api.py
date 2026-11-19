from __future__ import annotations

from fastapi.testclient import TestClient


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
