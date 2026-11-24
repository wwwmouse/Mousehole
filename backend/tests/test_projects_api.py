from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_create_and_list_project(client: TestClient) -> None:
    created = client.post(
        "/api/v1/projects",
        json={"name": "Agent Learning", "description": "multi-doc analysis"},
    )
    assert created.status_code == 201, created.text
    project = created.json()
    assert project["name"] == "Agent Learning"
    assert project["status"] == "active"
    assert project["task_count"] == 0
    assert project["file_count"] == 0

    listed = client.get("/api/v1/projects")
    assert listed.status_code == 200
    assert [p["id"] for p in listed.json()] == [project["id"]]


def test_update_project_archive_and_invalid_status(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "P"}).json()

    archived = client.patch(
        f"/api/v1/projects/{project['id']}", json={"status": "archived"}
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

    invalid = client.patch(
        f"/api/v1/projects/{project['id']}", json={"status": "deleted"}
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "unprocessable"

    missing = client.get(f"/api/v1/projects/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


def test_project_files_attach_and_remove(
    client: TestClient, db_session: Session, sample_file
) -> None:
    project = client.post("/api/v1/projects", json={"name": "P"}).json()
    project_id = project["id"]

    attached = client.post(
        f"/api/v1/projects/{project_id}/files", json={"file_id": str(sample_file.id)}
    )
    assert attached.status_code == 201, attached.text
    assert attached.json()["file"]["id"] == str(sample_file.id)
    assert attached.json()["source"] == "project"

    duplicated = client.post(
        f"/api/v1/projects/{project_id}/files", json={"file_id": str(sample_file.id)}
    )
    assert duplicated.status_code == 409

    listed = client.get(f"/api/v1/projects/{project_id}/files")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert client.get(f"/api/v1/projects/{project_id}").json()["file_count"] == 1

    removed = client.delete(f"/api/v1/projects/{project_id}/files/{sample_file.id}")
    assert removed.status_code == 204
    assert client.get(f"/api/v1/projects/{project_id}/files").json() == []


def test_project_private_upload_is_hidden_from_library_and_cleaned(
    client: TestClient,
) -> None:
    project = client.post("/api/v1/projects", json={"name": "Private P"}).json()
    project_id = project["id"]

    uploaded = client.post(
        f"/api/v1/projects/{project_id}/files/upload",
        files={"file": ("private.md", b"# private\n\nonly this project", "text/markdown")},
    )
    assert uploaded.status_code == 201, uploaded.text
    payload = uploaded.json()
    file_id = payload["file"]["id"]
    assert payload["file"]["is_temporary"] is True
    assert payload["file"]["owner_project_id"] == project_id

    # 不出现在 Global Library，但属于项目文件。
    library_ids = [item["id"] for item in client.get("/api/v1/files").json()]
    assert file_id not in library_ids
    assert [
        item["file"]["id"]
        for item in client.get(f"/api/v1/projects/{project_id}/files").json()
    ] == [file_id]

    # 项目内 Task 可以继承该文件。
    task = client.post(
        "/api/v1/tasks", json={"title": "private task", "project_id": project_id}
    ).json()
    task_files = client.get(f"/api/v1/tasks/{task['id']}/files").json()
    assert file_id in [item["file"]["id"] for item in task_files["available"]]

    # 移除项目引用后，无引用的私有文件被清理。
    removed = client.delete(f"/api/v1/projects/{project_id}/files/{file_id}")
    assert removed.status_code == 204
    assert client.get(f"/api/v1/files/{file_id}").status_code == 404


def test_delete_project_cleans_private_files(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "Cleanup P"}).json()
    project_id = project["id"]
    uploaded = client.post(
        f"/api/v1/projects/{project_id}/files/upload",
        files={"file": ("cleanup.md", b"# cleanup", "text/markdown")},
    )
    assert uploaded.status_code == 201, uploaded.text
    file_id = uploaded.json()["file"]["id"]

    deleted = client.delete(f"/api/v1/projects/{project_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/files/{file_id}").status_code == 404
