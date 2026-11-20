from __future__ import annotations

import pytest

from app.modules.artifact import service as artifact_service
from app.modules.project.models import Project
from app.modules.task.models import Task
from app.shared.exceptions import ConflictError, UnprocessableError


@pytest.fixture()
def task(db_session, workspace) -> Task:
    project = Project(workspace_id=workspace.id, name="Artifact Project")
    db_session.add(project)
    db_session.flush()
    task = Task(workspace_id=workspace.id, project_id=project.id, title="Artifact Task")
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


def test_series_is_reused_by_title(db_session, task) -> None:
    first = artifact_service.get_or_create_series(db_session, task, "分析报告")
    second = artifact_service.get_or_create_series(db_session, task, "分析报告")
    other = artifact_service.get_or_create_series(db_session, task, "对比报告")
    db_session.commit()

    assert first.id == second.id
    assert first.id != other.id
    assert len(artifact_service.list_task_series(db_session, task.id)) == 2


def test_artifact_versions_increment_and_keep_history(db_session, task) -> None:
    series = artifact_service.get_or_create_series(db_session, task, "分析报告")
    v1 = artifact_service.append_artifact(
        db_session, series, title="分析报告 v1", content="# v1"
    )
    db_session.commit()
    v2 = artifact_service.append_artifact(
        db_session, series, title="分析报告 v2", content="# v2"
    )
    db_session.commit()

    assert v1.version == 1
    assert v2.version == 2
    assert series.current_artifact_id == v2.id

    artifacts = artifact_service.list_series_artifacts(db_session, series.id)
    assert [item.version for item in artifacts] == [2, 1]
    assert artifacts[1].content == "# v1"  # history not overwritten


def test_rename_series_rejects_duplicate_title(db_session, task) -> None:
    first = artifact_service.get_or_create_series(db_session, task, "报告 A")
    artifact_service.get_or_create_series(db_session, task, "报告 B")
    db_session.commit()

    renamed = artifact_service.rename_series(db_session, first, "报告 C")
    assert renamed.title == "报告 C"

    with pytest.raises(ConflictError):
        artifact_service.rename_series(db_session, first, "报告 B")
    with pytest.raises(UnprocessableError):
        artifact_service.rename_series(db_session, first, "   ")


def test_current_artifact_must_belong_to_series(db_session, task) -> None:
    series_a = artifact_service.get_or_create_series(db_session, task, "A")
    series_b = artifact_service.get_or_create_series(db_session, task, "B")
    artifact_a = artifact_service.append_artifact(
        db_session, series_a, title="a", content="a"
    )
    artifact_b = artifact_service.append_artifact(
        db_session, series_b, title="b", content="b"
    )
    db_session.commit()

    artifact_service.set_current_artifact(db_session, series_a, artifact_a.id)
    assert series_a.current_artifact_id == artifact_a.id

    with pytest.raises(UnprocessableError):
        artifact_service.set_current_artifact(db_session, series_a, artifact_b.id)
