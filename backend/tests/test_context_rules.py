from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.context.service import compute_task_files
from app.modules.file.models import File, ProjectFile, TaskFileOverride
from app.modules.project.models import Project
from app.modules.task.models import Task


def _upload(
    client: TestClient,
    filename: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> dict:
    response = client.post(
        "/api/v1/files", files={"file": (filename, data, content_type)}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_project(client: TestClient, name: str = "Docs") -> dict:
    response = client.post("/api/v1/projects", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def _attach(client: TestClient, project_id: str, file_id: str) -> dict:
    response = client.post(
        f"/api/v1/projects/{project_id}/files", json={"file_id": file_id}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_task(client: TestClient, **payload) -> dict:
    response = client.post("/api/v1/tasks", json={"title": "Task", **payload})
    assert response.status_code == 201, response.text
    return response.json()


def _task_files(client: TestClient, task_id: str) -> dict:
    response = client.get(f"/api/v1/tasks/{task_id}/files")
    assert response.status_code == 200, response.text
    return response.json()


def _set_task_file(
    client: TestClient, task_id: str, file_id: str, action: str
):
    return client.post(
        f"/api/v1/tasks/{task_id}/files",
        json={"file_id": file_id, "action": action},
    )


def _make_file(name: str, status: str = "active") -> File:
    extension = name.rsplit(".", 1)[-1]
    return File(
        filename=name,
        storage_key=f"objects/test/{uuid.uuid4().hex}.{extension}",
        file_type=extension,
        mime_type="text/plain",
        size=1,
        content_hash=uuid.uuid4().hex * 2,
        status=status,
    )


def test_project_task_inheritance_include_and_exclude(client: TestClient) -> None:
    project = _create_project(client)
    zeta = _upload(client, "zeta.md", b"zeta")
    alpha = _upload(client, "alpha.md", b"alpha")
    extra = _upload(client, "extra.md", b"extra")
    _attach(client, project["id"], zeta["id"])
    _attach(client, project["id"], alpha["id"])
    task = _create_task(client, project_id=project["id"], title="分析")

    state = _task_files(client, task["id"])
    assert [
        (entry["file"]["filename"], entry["source"])
        for entry in state["available"]
    ] == [("alpha.md", "project_inherited"), ("zeta.md", "project_inherited")]
    assert state["excluded"] == []
    assert state["project_file_count"] == 2
    assert state["task_include_count"] == 0
    assert state["task_exclude_count"] == 0

    excluded = _set_task_file(client, task["id"], zeta["id"], "exclude")
    assert excluded.status_code == 201, excluded.text
    state = excluded.json()
    assert [entry["file"]["filename"] for entry in state["available"]] == [
        "alpha.md"
    ]
    assert [file["filename"] for file in state["excluded"]] == ["zeta.md"]
    assert state["task_exclude_count"] == 1

    repeated = _set_task_file(client, task["id"], zeta["id"], "exclude")
    assert repeated.status_code == 200
    assert repeated.json()["task_exclude_count"] == 1
    assert state["excluded"] == repeated.json()["excluded"]

    included = _set_task_file(client, task["id"], extra["id"], "include")
    assert included.status_code == 201, included.text
    state = included.json()
    assert [
        (entry["file"]["filename"], entry["source"])
        for entry in state["available"]
    ] == [
        ("alpha.md", "project_inherited"),
        ("extra.md", "task_added"),
    ]
    assert state["task_include_count"] == 1
    assert [file["filename"] for file in state["excluded"]] == ["zeta.md"]

    repeated_include = _set_task_file(client, task["id"], extra["id"], "include")
    assert repeated_include.status_code == 200
    assert repeated_include.json()["task_include_count"] == 1

    # DATA_MODEL rule 7: project files are already inherited.
    rule7 = _set_task_file(client, task["id"], alpha["id"], "include")
    assert rule7.status_code == 422
    assert rule7.json()["error"]["code"] == "unprocessable"

    # Only files of the task's project can be excluded.
    not_member = _set_task_file(client, task["id"], extra["id"], "exclude")
    assert not_member.status_code == 422
    assert not_member.json()["error"]["code"] == "unprocessable"

    removed = client.delete(f"/api/v1/tasks/{task['id']}/files/{extra['id']}")
    assert removed.status_code == 204
    state = _task_files(client, task["id"])
    assert state["task_include_count"] == 0
    assert [entry["file"]["filename"] for entry in state["available"]] == [
        "alpha.md"
    ]

    missing = client.delete(f"/api/v1/tasks/{task['id']}/files/{extra['id']}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


def test_global_task_context_only_has_included_files(client: TestClient) -> None:
    task = _create_task(client, title="Global")
    file = _upload(client, "global.txt", b"global")

    state = _task_files(client, task["id"])
    assert state == {
        "available": [],
        "excluded": [],
        "project_file_count": 0,
        "task_include_count": 0,
        "task_exclude_count": 0,
    }

    excluded = _set_task_file(client, task["id"], file["id"], "exclude")
    assert excluded.status_code == 422
    assert excluded.json()["error"]["code"] == "unprocessable"

    included = _set_task_file(client, task["id"], file["id"], "include")
    assert included.status_code == 201, included.text
    state = included.json()
    assert [
        (entry["file"]["filename"], entry["source"])
        for entry in state["available"]
    ] == [("global.txt", "task_added")]
    assert state["project_file_count"] == 0
    assert state["task_include_count"] == 1


def test_opposite_action_updates_the_single_override(client: TestClient) -> None:
    project = _create_project(client, "P")
    file = _upload(client, "switch.md", b"switch")
    task = _create_task(client, project_id=project["id"], title="T")

    included = _set_task_file(client, task["id"], file["id"], "include")
    assert included.status_code == 201, included.text
    assert included.json()["task_include_count"] == 1

    # The file later becomes part of the project; the stale include override
    # must not duplicate the inherited entry.
    _attach(client, project["id"], file["id"])
    state = _task_files(client, task["id"])
    assert [
        (entry["file"]["filename"], entry["source"])
        for entry in state["available"]
    ] == [("switch.md", "project_inherited")]
    assert state["task_include_count"] == 0

    switched = _set_task_file(client, task["id"], file["id"], "exclude")
    assert switched.status_code == 200, switched.text
    state = switched.json()
    assert state["available"] == []
    assert [item["filename"] for item in state["excluded"]] == ["switch.md"]
    assert state["task_exclude_count"] == 1


def test_task_file_errors(client: TestClient) -> None:
    missing_task = client.get(f"/api/v1/tasks/{uuid.uuid4()}/files")
    assert missing_task.status_code == 404

    task = _create_task(client, title="T")
    missing_file = _set_task_file(
        client, task["id"], str(uuid.uuid4()), "include"
    )
    assert missing_file.status_code == 404
    assert missing_file.json()["error"]["code"] == "not_found"

    invalid_action = client.post(
        f"/api/v1/tasks/{task['id']}/files",
        json={"file_id": str(uuid.uuid4()), "action": "delete"},
    )
    assert invalid_action.status_code == 422
    assert invalid_action.json()["error"]["code"] == "validation_error"


def test_compute_handles_soft_deleted_files_and_dangling_overrides(
    db_session: Session, workspace
) -> None:
    project = Project(workspace_id=workspace.id, name="P")
    db_session.add(project)
    db_session.flush()
    task = Task(workspace_id=workspace.id, project_id=project.id, title="T")
    active = _make_file("active.md")
    deleted = _make_file("deleted.md", status="deleted")
    dangling = _make_file("dangling.md", status="deleted")
    db_session.add_all([task, active, deleted, dangling])
    db_session.flush()
    db_session.add_all(
        [
            ProjectFile(project_id=project.id, file_id=active.id),
            ProjectFile(project_id=project.id, file_id=deleted.id),
            TaskFileOverride(task_id=task.id, file_id=active.id, action="exclude"),
            TaskFileOverride(
                task_id=task.id, file_id=dangling.id, action="include"
            ),
        ]
    )
    db_session.commit()

    result = compute_task_files(db_session, task)
    assert result.project_file_count == 1
    assert result.available == []
    assert [file.filename for file in result.excluded] == ["active.md"]
    assert result.task_include_count == 0
    assert result.task_exclude_count == 1


def test_compute_global_task_without_project(db_session: Session, workspace) -> None:
    task = Task(workspace_id=workspace.id, project_id=None, title="Global")
    file = _make_file("global.md")
    db_session.add_all([task, file])
    db_session.flush()
    db_session.add(
        TaskFileOverride(task_id=task.id, file_id=file.id, action="include")
    )
    db_session.commit()

    result = compute_task_files(db_session, task)
    assert [
        (entry.file.filename, entry.source) for entry in result.available
    ] == [("global.md", "task_added")]
    assert result.project_file_count == 0
    assert result.task_include_count == 1
    assert result.excluded == []
