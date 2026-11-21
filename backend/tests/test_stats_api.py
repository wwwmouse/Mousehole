from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.modules.artifact import service as artifact_service
from app.modules.conversation import service as conversation_service
from app.modules.conversation.models import Conversation
from app.modules.execution import service as execution_service
from app.modules.project.models import Project
from app.modules.task.models import Task


def _seed(db_session, workspace):
    project = Project(workspace_id=workspace.id, name="Stats Project")
    db_session.add(project)
    db_session.flush()
    task = Task(
        workspace_id=workspace.id, project_id=project.id, title="Stats Task"
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    conversation = Conversation(task_id=task.id)
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)
    return task, conversation


def test_stats_overview_counts_and_tokens(client: TestClient, db_session, workspace) -> None:
    task, conversation = _seed(db_session, workspace)
    conversation_service.append_message(
        db_session, conversation, role="user", content="问题一"
    )
    conversation_service.append_message(
        db_session,
        conversation,
        role="assistant",
        content="回答一",
        usage={"prompt_tokens": 6, "completion_tokens": 4, "total_tokens": 10},
    )
    db_session.commit()

    execution = execution_service.create_execution(
        db_session, task=task, model_provider="deepseek", model_name="deepseek-flash"
    )
    execution_service.mark_running(db_session, execution)
    execution_service.complete(
        db_session,
        execution,
        usage={"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
    )
    db_session.commit()

    series = artifact_service.get_or_create_series(db_session, task, "统计系列")
    artifact_service.append_artifact(
        db_session, series, title="统计成果", content="# stats"
    )
    db_session.commit()

    response = client.get("/api/v1/stats/overview?days=7")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["conversation_turns"] == 1
    assert body["execution_count"] == 1
    assert body["tokens"]["total_tokens"] == 15  # chat 10 + execution 5
    assert body["tokens_complete"] is True
    assert len(body["daily"]) == 7
    assert sum(item["conversation_turns"] for item in body["daily"]) == 1
    assert sum(item["total_tokens"] for item in body["daily"]) == 15
    assert body["recent_artifacts"][0]["title"] == "统计成果"
    assert body["recent_artifacts"][0]["task_title"] == "Stats Task"


def test_stats_marks_missing_usage_incomplete(client: TestClient, db_session, workspace) -> None:
    _, conversation = _seed(db_session, workspace)
    conversation_service.append_message(
        db_session, conversation, role="assistant", content="无 usage", usage=None
    )
    db_session.commit()

    body = client.get("/api/v1/stats/overview").json()
    assert body["tokens_complete"] is False
