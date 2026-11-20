from __future__ import annotations

import uuid

import pytest

from app.modules.execution import service as execution_service
from app.modules.file.models import File
from app.modules.project.models import Project
from app.modules.task.models import Task
from app.shared.exceptions import UnprocessableError


@pytest.fixture()
def task(db_session, workspace) -> Task:
    project = Project(workspace_id=workspace.id, name="Exec Project")
    db_session.add(project)
    db_session.flush()
    task = Task(
        workspace_id=workspace.id,
        project_id=project.id,
        title="Exec Task",
        model_provider="deepseek",
        model_name="deepseek-flash",
        temperature=0.3,
        max_tokens=1024,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


def test_create_execution_snapshots_model_config(db_session, task) -> None:
    first = execution_service.create_execution(
        db_session,
        task=task,
        model_provider=task.model_provider,
        model_name=task.model_name,
        temperature=task.temperature,
        max_tokens=task.max_tokens,
        input_summary="分析两份资料",
    )
    second = execution_service.create_execution(
        db_session,
        task=task,
        model_provider="ollama",
        model_name="qwen2.5:3b",
    )
    db_session.commit()

    assert first.sequence == 1
    assert second.sequence == 2
    assert first.status == "pending"
    assert first.model_name == "deepseek-flash"
    assert first.temperature == 0.3
    assert second.model_provider == "ollama"


def test_execution_state_machine_and_cancel_semantics(db_session, task) -> None:
    execution = execution_service.create_execution(
        db_session, task=task, model_provider="deepseek", model_name="deepseek-flash"
    )
    db_session.commit()

    # pending -> completed is not allowed
    with pytest.raises(UnprocessableError):
        execution_service.complete(db_session, execution)

    execution_service.mark_running(db_session, execution)
    assert execution.started_at is not None
    execution_service.complete(db_session, execution, usage={"total_tokens": 12})
    assert execution.status == "completed"
    assert execution.completed_at is not None
    assert execution.usage == {"total_tokens": 12}

    # terminal states are final
    with pytest.raises(UnprocessableError):
        execution_service.fail(db_session, execution, message="late failure")


def test_cancel_is_not_failure(db_session, task) -> None:
    pending = execution_service.create_execution(
        db_session, task=task, model_provider="deepseek", model_name="deepseek-flash"
    )
    execution_service.cancel(db_session, pending)
    assert pending.status == "cancelled"
    assert pending.error_message is None
    assert pending.error_code is None

    running = execution_service.create_execution(
        db_session, task=task, model_provider="deepseek", model_name="deepseek-flash"
    )
    execution_service.mark_running(db_session, running)
    execution_service.cancel(db_session, running)
    assert running.status == "cancelled"
    assert running.completed_at is not None


def test_failure_records_location(db_session, task) -> None:
    execution = execution_service.create_execution(
        db_session, task=task, model_provider="deepseek", model_name="deepseek-flash"
    )
    execution_service.mark_running(db_session, execution)
    execution_service.fail(
        db_session, execution, message="模型调用超时", code="model_timeout"
    )
    assert execution.status == "failed"
    assert execution.error_code == "model_timeout"
    assert execution.error_message == "模型调用超时"


def test_execution_steps_are_recorded_in_order(db_session, task) -> None:
    execution = execution_service.create_execution(
        db_session, task=task, model_provider="deepseek", model_name="deepseek-flash"
    )
    first = execution_service.open_step(
        db_session, execution, step_type="resolve_files", name="解析可用文件"
    )
    execution_service.finish_step(db_session, first, output_summary="2 files")
    second = execution_service.open_step(
        db_session, execution, step_type="model_call", name="调用模型"
    )
    execution_service.finish_step(
        db_session, second, status="failed", error_message="timeout"
    )
    db_session.commit()

    steps = execution_service.repository.list_steps(db_session, execution.id)
    assert [step.sequence for step in steps] == [1, 2]
    assert steps[0].status == "completed"
    assert steps[1].status == "failed"
    assert steps[1].error_message == "timeout"


def test_file_snapshots_record_usage_mode(db_session, task) -> None:
    execution = execution_service.create_execution(
        db_session, task=task, model_provider="deepseek", model_name="deepseek-flash"
    )
    file_a = File(
        filename="a.md",
        storage_key=f"objects/{uuid.uuid4().hex}.md",
        file_type="md",
        mime_type="text/markdown",
        size=10,
        content_hash=uuid.uuid4().hex * 2,
    )
    file_b = File(
        filename="b.txt",
        storage_key=f"objects/{uuid.uuid4().hex}.txt",
        file_type="txt",
        mime_type="text/plain",
        size=20,
        content_hash=uuid.uuid4().hex * 2,
    )
    db_session.add_all([file_a, file_b])
    db_session.flush()

    execution_service.record_file_usage(
        db_session,
        execution,
        file=file_a,
        source_type="project_inherited",
        usage_mode="direct",
    )
    execution_service.record_file_usage(
        db_session,
        execution,
        file=file_b,
        source_type="task_added",
        usage_mode="summarized",
    )
    # duplicate file is idempotent
    execution_service.record_file_usage(
        db_session,
        execution,
        file=file_a,
        source_type="project_inherited",
        usage_mode="direct",
    )
    db_session.commit()

    snapshots = execution_service.repository.list_snapshots(db_session, execution.id)
    assert len(snapshots) == 2
    by_name = {item.filename_snapshot: item for item in snapshots}
    assert by_name["a.md"].usage_mode == "direct"
    assert by_name["b.txt"].usage_mode == "summarized"
    assert by_name["a.md"].content_hash_snapshot == file_a.content_hash

    with pytest.raises(UnprocessableError):
        execution_service.record_file_usage(
            db_session,
            execution,
            file=file_a,
            source_type="project_inherited",
            usage_mode="unknown",
        )
