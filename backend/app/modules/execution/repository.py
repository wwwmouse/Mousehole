from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.execution.models import (
    Execution,
    ExecutionFileSnapshot,
    ExecutionStep,
)


def next_sequence(session: Session, task_id: uuid.UUID) -> int:
    current = session.scalar(
        select(func.max(Execution.sequence)).where(Execution.task_id == task_id)
    )
    return int(current or 0) + 1


def next_step_sequence(session: Session, execution_id: uuid.UUID) -> int:
    current = session.scalar(
        select(func.max(ExecutionStep.sequence)).where(
            ExecutionStep.execution_id == execution_id
        )
    )
    return int(current or 0) + 1


def create(session: Session, *, task_id: uuid.UUID, sequence: int, **fields) -> Execution:
    execution = Execution(task_id=task_id, sequence=sequence, **fields)
    session.add(execution)
    session.flush()
    return execution


def get(session: Session, execution_id: uuid.UUID) -> Execution | None:
    return session.get(Execution, execution_id)


def list_for_task(
    session: Session, task_id: uuid.UUID, *, limit: int = 50
) -> list[Execution]:
    stmt = (
        select(Execution)
        .where(Execution.task_id == task_id)
        .order_by(Execution.sequence.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt))


def list_running(session: Session) -> list[Execution]:
    return list(session.scalars(select(Execution).where(Execution.status == "running")))


def list_pending_ids(session: Session) -> list[uuid.UUID]:
    return list(
        session.scalars(
            select(Execution.id)
            .where(Execution.status == "pending")
            .order_by(Execution.created_at)
        )
    )


def create_step(
    session: Session,
    *,
    execution_id: uuid.UUID,
    sequence: int,
    step_type: str,
    name: str,
    status: str,
    input_summary: str | None = None,
    started_at=None,
) -> ExecutionStep:
    step = ExecutionStep(
        execution_id=execution_id,
        sequence=sequence,
        step_type=step_type,
        name=name,
        status=status,
        input_summary=input_summary,
        started_at=started_at,
    )
    session.add(step)
    session.flush()
    return step


def list_steps(session: Session, execution_id: uuid.UUID) -> list[ExecutionStep]:
    stmt = (
        select(ExecutionStep)
        .where(ExecutionStep.execution_id == execution_id)
        .order_by(ExecutionStep.sequence)
    )
    return list(session.scalars(stmt))


def get_snapshot(
    session: Session, execution_id: uuid.UUID, file_id: uuid.UUID
) -> ExecutionFileSnapshot | None:
    return session.scalars(
        select(ExecutionFileSnapshot).where(
            ExecutionFileSnapshot.execution_id == execution_id,
            ExecutionFileSnapshot.file_id == file_id,
        )
    ).first()


def create_snapshot(
    session: Session,
    *,
    execution_id: uuid.UUID,
    file_id: uuid.UUID,
    filename_snapshot: str,
    content_hash_snapshot: str,
    source_type: str,
    usage_mode: str,
) -> ExecutionFileSnapshot:
    snapshot = ExecutionFileSnapshot(
        execution_id=execution_id,
        file_id=file_id,
        filename_snapshot=filename_snapshot,
        content_hash_snapshot=content_hash_snapshot,
        source_type=source_type,
        usage_mode=usage_mode,
    )
    session.add(snapshot)
    session.flush()
    return snapshot


def list_snapshots(
    session: Session, execution_id: uuid.UUID
) -> list[ExecutionFileSnapshot]:
    stmt = (
        select(ExecutionFileSnapshot)
        .where(ExecutionFileSnapshot.execution_id == execution_id)
        .order_by(ExecutionFileSnapshot.filename_snapshot)
    )
    return list(session.scalars(stmt))
