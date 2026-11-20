from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.modules.execution import repository
from app.modules.execution.models import (
    Execution,
    ExecutionFileSnapshot,
    ExecutionStep,
)
from app.modules.file.models import File
from app.modules.task.models import Task
from app.shared.enums import (
    SNAPSHOT_SOURCE_TYPES,
    SNAPSHOT_USAGE_MODES,
    ExecutionStatus,
    ExecutionStepStatus,
)
from app.shared.exceptions import UnprocessableError


def _now() -> datetime:
    return datetime.now(timezone.utc)


# Explicit state machine: cancellation is never a failure.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    ExecutionStatus.PENDING.value: {
        ExecutionStatus.RUNNING.value,
        ExecutionStatus.CANCELLED.value,
    },
    ExecutionStatus.RUNNING.value: {
        ExecutionStatus.COMPLETED.value,
        ExecutionStatus.FAILED.value,
        ExecutionStatus.CANCELLED.value,
    },
    ExecutionStatus.COMPLETED.value: set(),
    ExecutionStatus.FAILED.value: set(),
    ExecutionStatus.CANCELLED.value: set(),
}


def create_execution(
    session: Session,
    *,
    task: Task,
    model_provider: str | None,
    model_name: str | None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    input_summary: str | None = None,
) -> Execution:
    execution = repository.create(
        session,
        task_id=task.id,
        sequence=repository.next_sequence(session, task.id),
        status=ExecutionStatus.PENDING.value,
        model_provider=model_provider,
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        input_summary=input_summary,
    )
    return execution


def transition(
    session: Session,
    execution: Execution,
    new_status: str,
    *,
    error_message: str | None = None,
    error_code: str | None = None,
    usage: dict | None = None,
) -> Execution:
    allowed = ALLOWED_TRANSITIONS.get(execution.status, set())
    if new_status not in allowed:
        raise UnprocessableError(
            f"非法的执行状态流转：{execution.status} → {new_status}"
        )
    execution.status = new_status
    if new_status == ExecutionStatus.RUNNING.value and execution.started_at is None:
        execution.started_at = _now()
    if new_status in {
        ExecutionStatus.COMPLETED.value,
        ExecutionStatus.FAILED.value,
        ExecutionStatus.CANCELLED.value,
    }:
        execution.completed_at = _now()
    if error_message is not None:
        execution.error_message = error_message
    if error_code is not None:
        execution.error_code = error_code
    if usage is not None:
        execution.usage = usage
    session.flush()
    return execution


def mark_running(session: Session, execution: Execution) -> Execution:
    return transition(session, execution, ExecutionStatus.RUNNING.value)


def complete(
    session: Session, execution: Execution, *, usage: dict | None = None
) -> Execution:
    return transition(
        session, execution, ExecutionStatus.COMPLETED.value, usage=usage
    )


def fail(
    session: Session,
    execution: Execution,
    *,
    message: str,
    code: str = "execution_failed",
) -> Execution:
    return transition(
        session,
        execution,
        ExecutionStatus.FAILED.value,
        error_message=message,
        error_code=code,
    )


def cancel(session: Session, execution: Execution) -> Execution:
    """User-initiated cancellation is not a failure; no error is recorded."""
    return transition(session, execution, ExecutionStatus.CANCELLED.value)


# --- key execution steps -------------------------------------------------


def open_step(
    session: Session,
    execution: Execution,
    *,
    step_type: str,
    name: str,
    input_summary: str | None = None,
) -> ExecutionStep:
    return repository.create_step(
        session,
        execution_id=execution.id,
        sequence=repository.next_step_sequence(session, execution.id),
        step_type=step_type,
        name=name,
        status=ExecutionStepStatus.RUNNING.value,
        input_summary=input_summary,
        started_at=_now(),
    )


def finish_step(
    session: Session,
    step: ExecutionStep,
    *,
    status: str = ExecutionStepStatus.COMPLETED.value,
    output_summary: str | None = None,
    error_message: str | None = None,
) -> ExecutionStep:
    if status not in {
        ExecutionStepStatus.COMPLETED.value,
        ExecutionStepStatus.FAILED.value,
        ExecutionStepStatus.SKIPPED.value,
    }:
        raise UnprocessableError(f"非法的步骤状态：{status}")
    step.status = status
    step.completed_at = _now()
    if output_summary is not None:
        step.output_summary = output_summary
    if error_message is not None:
        step.error_message = error_message
    session.flush()
    return step


# --- file snapshots ------------------------------------------------------


def record_file_usage(
    session: Session,
    execution: Execution,
    *,
    file: File,
    source_type: str,
    usage_mode: str,
) -> ExecutionFileSnapshot:
    """Record that a file was actually read and used (directly or summarized)."""
    if source_type not in SNAPSHOT_SOURCE_TYPES:
        raise UnprocessableError(f"非法的文件来源类型：{source_type}")
    if usage_mode not in SNAPSHOT_USAGE_MODES:
        raise UnprocessableError(f"非法的文件使用方式：{usage_mode}")
    existing = repository.get_snapshot(session, execution.id, file.id)
    if existing is not None:
        return existing
    return repository.create_snapshot(
        session,
        execution_id=execution.id,
        file_id=file.id,
        filename_snapshot=file.filename,
        content_hash_snapshot=file.content_hash,
        source_type=source_type,
        usage_mode=usage_mode,
    )


def recover_interrupted(session: Session) -> int:
    """Mark executions left Running by a previous process as failed (not 'running')."""
    recovered = repository.list_running(session)
    for execution in recovered:
        fail(
            session,
            execution,
            message="应用重启，执行被中断",
            code="interrupted",
        )
    if recovered:
        session.commit()
    return len(recovered)


def list_executions(session: Session, task_id: uuid.UUID) -> list[Execution]:
    return repository.list_for_task(session, task_id)


def get_execution(session: Session, execution_id: uuid.UUID) -> Execution:
    execution = repository.get(session, execution_id)
    if execution is None:
        from app.shared.exceptions import NotFoundError

        raise NotFoundError(
            "执行记录不存在", details={"execution_id": str(execution_id)}
        )
    return execution
