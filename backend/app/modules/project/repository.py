from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.file.models import File, ProjectFile
from app.modules.project.models import Project
from app.modules.task.models import Task


def list_projects(
    session: Session,
    *,
    workspace_id: uuid.UUID | None,
    status: str | None,
    limit: int,
    offset: int,
) -> list[Project]:
    stmt = select(Project).order_by(Project.created_at.desc())
    if workspace_id is not None:
        stmt = stmt.where(Project.workspace_id == workspace_id)
    if status is not None:
        stmt = stmt.where(Project.status == status)
    return list(session.scalars(stmt.limit(limit).offset(offset)))


def get(session: Session, project_id: uuid.UUID) -> Project | None:
    return session.get(Project, project_id)


def create(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    name: str,
    description: str | None,
) -> Project:
    project = Project(
        workspace_id=workspace_id, name=name, description=description
    )
    session.add(project)
    session.flush()
    return project


def count_tasks(session: Session, project_id: uuid.UUID) -> int:
    return int(
        session.scalar(
            select(func.count()).select_from(Task).where(Task.project_id == project_id)
        )
        or 0
    )


def count_files(session: Session, project_id: uuid.UUID) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(ProjectFile)
            .join(File, File.id == ProjectFile.file_id)
            .where(ProjectFile.project_id == project_id, File.status == "active")
        )
        or 0
    )


def list_files(session: Session, project_id: uuid.UUID) -> list[tuple[ProjectFile, File]]:
    stmt = (
        select(ProjectFile, File)
        .join(File, File.id == ProjectFile.file_id)
        .where(ProjectFile.project_id == project_id, File.status == "active")
        .order_by(ProjectFile.added_at)
    )
    return [(row[0], row[1]) for row in session.execute(stmt).all()]


def get_project_file(
    session: Session, project_id: uuid.UUID, file_id: uuid.UUID
) -> ProjectFile | None:
    return session.scalars(
        select(ProjectFile).where(
            ProjectFile.project_id == project_id, ProjectFile.file_id == file_id
        )
    ).first()


def add_file(session: Session, project_id: uuid.UUID, file_id: uuid.UUID) -> ProjectFile:
    link = ProjectFile(project_id=project_id, file_id=file_id)
    session.add(link)
    session.flush()
    return link


def remove_file(session: Session, link: ProjectFile) -> None:
    session.delete(link)


def delete_files(session: Session, project_id: uuid.UUID) -> None:
    session.execute(
        ProjectFile.__table__.delete().where(ProjectFile.project_id == project_id)
    )


def delete(session: Session, project: Project) -> None:
    delete_files(session, project.id)
    session.delete(project)


def count_projects_for_file(session: Session, file_id: uuid.UUID) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(ProjectFile)
            .where(ProjectFile.file_id == file_id)
        )
        or 0
    )
