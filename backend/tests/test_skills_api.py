from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _create_task(client: TestClient) -> str:
    response = client.post("/api/v1/tasks", json={"title": "skill test task"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_builtin_skills_are_seeded(client: TestClient) -> None:
    skills = client.get("/api/v1/skills")
    assert skills.status_code == 200
    names = {item["name"] for item in skills.json()}
    assert {"多文档分析", "内容摘要"} <= names
    assert all(item["is_builtin"] for item in skills.json() if item["name"] in names)


def test_create_update_and_delete_skill(client: TestClient) -> None:
    created = client.post(
        "/api/v1/skills",
        json={
            "name": "会议纪要",
            "description": "整理会议内容",
            "instruction": "输出会议纪要，包含结论与待办。",
        },
    )
    assert created.status_code == 201, created.text
    skill = created.json()
    assert skill["name"] == "会议纪要"
    assert skill["is_builtin"] is False

    duplicate = client.post(
        "/api/v1/skills",
        json={"name": "会议纪要", "instruction": "x"},
    )
    assert duplicate.status_code == 409

    updated = client.patch(
        f"/api/v1/skills/{skill['id']}",
        json={"name": "会议纪要 v2", "instruction": "输出精炼纪要。"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "会议纪要 v2"

    deleted = client.delete(f"/api/v1/skills/{skill['id']}")
    assert deleted.status_code == 204
    remaining = {item["id"] for item in client.get("/api/v1/skills").json()}
    assert skill["id"] not in remaining


def test_task_skill_reference_flow(client: TestClient) -> None:
    task_id = _create_task(client)
    skills = client.get("/api/v1/skills").json()
    summary = next(item for item in skills if item["name"] == "内容摘要")

    added = client.post(
        f"/api/v1/tasks/{task_id}/skills", json={"skill_id": summary["id"]}
    )
    assert added.status_code == 201, added.text
    assert [item["id"] for item in client.get(f"/api/v1/tasks/{task_id}/skills").json()] == [
        summary["id"]
    ]

    # idempotent
    again = client.post(
        f"/api/v1/tasks/{task_id}/skills", json={"skill_id": summary["id"]}
    )
    assert again.status_code == 201

    removed = client.delete(f"/api/v1/tasks/{task_id}/skills/{summary['id']}")
    assert removed.status_code == 204
    assert client.get(f"/api/v1/tasks/{task_id}/skills").json() == []

    # deleting a skill also removes task references
    client.post(f"/api/v1/tasks/{task_id}/skills", json={"skill_id": summary["id"]})
    assert client.delete(f"/api/v1/skills/{summary['id']}").status_code == 204
    assert client.get(f"/api/v1/tasks/{task_id}/skills").json() == []


def test_skill_file_attachment_flow(client: TestClient) -> None:
    skill = next(
        item
        for item in client.get("/api/v1/skills").json()
        if item["name"] == "多文档分析"
    )
    uploaded = client.post(
        "/api/v1/files",
        files={"file": ("skill-ref.md", b"# Reference\n\ntemplate", "text/markdown")},
    )
    assert uploaded.status_code == 201, uploaded.text
    file_id = uploaded.json()["id"]

    attached = client.post(
        f"/api/v1/skills/{skill['id']}/files",
        json={"file_id": file_id, "path": "templates/skill-ref.md"},
    )
    assert attached.status_code == 201, attached.text
    assert attached.json()["path"] == "templates/skill-ref.md"

    listed = client.get(f"/api/v1/skills/{skill['id']}/files")
    assert listed.status_code == 200
    assert listed.json()[0]["filename"] == "skill-ref.md"

    removed = client.delete(f"/api/v1/skills/{skill['id']}/files/{file_id}")
    assert removed.status_code == 204
    assert client.get(f"/api/v1/skills/{skill['id']}/files").json() == []


def test_execution_can_use_library_skill(client: TestClient, monkeypatch) -> None:
    from app.modules.model import service as model_service

    monkeypatch.setattr(
        model_service,
        "resolve_model",
        lambda *args, **kwargs: ("deepseek", "deepseek-flash", {}),
    )
    task_id = _create_task(client)
    skill = next(
        item
        for item in client.get("/api/v1/skills").json()
        if item["name"] == "内容摘要"
    )
    created = client.post(
        f"/api/v1/tasks/{task_id}/executions",
        json={"skill_id": skill["id"]},
    )
    assert created.status_code == 202, created.text
    assert created.json()["skill_id"] == skill["id"]
    assert created.json()["skill_name"] == "内容摘要"

    unknown = client.post(
        f"/api/v1/tasks/{task_id}/executions",
        json={"skill_id": "00000000-0000-4000-8000-000000000000"},
    )
    assert unknown.status_code == 404
