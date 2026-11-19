from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.task.models import Task
from app.modules.workspace.models import Workspace


def list_tasks(
    session: Session,
    *,
    workspace_id: uuid.UUID | None,
    project_id: uuid.UUID | None,
    status: str | None,
    limit: int,
    offset: int,
) -> list[Task]:
    stmt = select(Task).order_by(Task.created_at.desc())
    if workspace_id is not None:
        stmt = stmt.where(Task.workspace_id == workspace_id)
    if project_id is not None:
        stmt = stmt.where(Task.project_id == project_id)
    if status is not None:
        stmt = stmt.where(Task.status == status)
    return list(session.scalars(stmt.limit(limit).offset(offset)))


def get(session: Session, task_id: uuid.UUID) -> Task | None:
    return session.get(Task, task_id)


def create(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None,
    title: str,
    description: str | None,
    model_provider: str | None,
    model_name: str | None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> Task:
    task = Task(
        workspace_id=workspace_id,
        project_id=project_id,
        title=title,
        description=description,
        model_provider=model_provider,
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    session.add(task)
    session.flush()
    return task


def get_workspace(session: Session, workspace_id: uuid.UUID) -> Workspace | None:
    return session.get(Workspace, workspace_id)


def delete_overrides(session: Session, task_id: uuid.UUID) -> None:
    from app.modules.file.models import TaskFileOverride

    session.execute(
        TaskFileOverride.__table__.delete().where(
            TaskFileOverride.task_id == task_id
        )
    )


def delete(session: Session, task: Task) -> None:
    delete_overrides(session, task.id)
    session.delete(task)
