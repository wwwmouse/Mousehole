from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_and_update_workspace(client: TestClient, workspace) -> None:
    listed = client.get("/api/v1/workspaces")
    assert listed.status_code == 200
    assert [w["id"] for w in listed.json()] == [str(workspace.id)]

    updated = client.patch(
        f"/api/v1/workspaces/{workspace.id}", json={"name": "Renamed"}
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed"


def test_update_workspace_model_defaults(client: TestClient, workspace) -> None:
    response = client.patch(
        f"/api/v1/workspaces/{workspace.id}",
        json={"default_temperature": 0.3, "default_max_tokens": 256},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["default_temperature"] == 0.3
    assert body["default_max_tokens"] == 256

    invalid = client.patch(
        f"/api/v1/workspaces/{workspace.id}", json={"default_temperature": 3}
    )
    assert invalid.status_code == 422
