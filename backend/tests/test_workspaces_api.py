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
