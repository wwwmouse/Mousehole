from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.file.models import File, ProjectFile, TaskFileOverride


def get(session: Session, file_id: uuid.UUID) -> File | None:
    return session.get(File, file_id)


def list_files(
    session: Session,
    *,
    search: str | None = None,
    file_type: str | None = None,
    status: str = "active",
    limit: int = 50,
    offset: int = 0,
) -> list[File]:
    stmt = select(File).order_by(File.created_at.desc())
    if status:
        stmt = stmt.where(File.status == status)
    if file_type:
        stmt = stmt.where(File.file_type == file_type)
    if search:
        stmt = stmt.where(func.lower(File.filename).contains(search.lower()))
    return list(session.scalars(stmt.limit(limit).offset(offset)))


def count_references(session: Session, file_id: uuid.UUID) -> tuple[int, int]:
    project_refs = int(
        session.scalar(
            select(func.count())
            .select_from(ProjectFile)
            .where(ProjectFile.file_id == file_id)
        )
        or 0
    )
    task_refs = int(
        session.scalar(
            select(func.count())
            .select_from(TaskFileOverride)
            .where(TaskFileOverride.file_id == file_id)
        )
        or 0
    )
    return project_refs, task_refs


# --- Phase 1: file domain additions (append-only) ---

from app.modules.project.models import Project  # noqa: E402
from app.modules.task.models import Task  # noqa: E402


def get_by_storage_key(session: Session, storage_key: str) -> File | None:
    return session.scalars(
        select(File).where(File.storage_key == storage_key)
    ).first()


def create(
    session: Session,
    *,
    filename: str,
    storage_key: str,
    file_type: str,
    mime_type: str,
    size: int,
    content_hash: str,
) -> File:
    file = File(
        filename=filename,
        storage_key=storage_key,
        file_type=file_type,
        mime_type=mime_type,
        size=size,
        content_hash=content_hash,
    )
    session.add(file)
    session.flush()
    return file


def list_project_references(session: Session, file_id: uuid.UUID) -> list[Project]:
    stmt = (
        select(Project)
        .join(ProjectFile, ProjectFile.project_id == Project.id)
        .where(ProjectFile.file_id == file_id)
        .order_by(Project.created_at, Project.id)
    )
    return list(session.scalars(stmt))


def list_task_references(session: Session, file_id: uuid.UUID) -> list[Task]:
    stmt = (
        select(Task)
        .join(TaskFileOverride, TaskFileOverride.task_id == Task.id)
        .where(TaskFileOverride.file_id == file_id)
        .order_by(Task.created_at, Task.id)
    )
    return list(session.scalars(stmt))


def get_project_file(
    session: Session, project_id: uuid.UUID, file_id: uuid.UUID
) -> ProjectFile | None:
    return session.scalars(
        select(ProjectFile).where(
            ProjectFile.project_id == project_id, ProjectFile.file_id == file_id
        )
    ).first()


def list_overrides_with_files(
    session: Session, task_id: uuid.UUID
) -> list[tuple[TaskFileOverride, File]]:
    stmt = (
        select(TaskFileOverride, File)
        .join(File, File.id == TaskFileOverride.file_id)
        .where(TaskFileOverride.task_id == task_id)
        .order_by(TaskFileOverride.created_at, TaskFileOverride.id)
    )
    return [(row[0], row[1]) for row in session.execute(stmt).all()]


def get_override(
    session: Session, task_id: uuid.UUID, file_id: uuid.UUID
) -> TaskFileOverride | None:
    return session.scalars(
        select(TaskFileOverride).where(
            TaskFileOverride.task_id == task_id, TaskFileOverride.file_id == file_id
        )
    ).first()


def add_override(
    session: Session, task_id: uuid.UUID, file_id: uuid.UUID, action: str
) -> TaskFileOverride:
    override = TaskFileOverride(task_id=task_id, file_id=file_id, action=action)
    session.add(override)
    session.flush()
    return override
