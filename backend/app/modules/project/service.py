from __future__ import annotations

import uuid

from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from app.core.config import get_settings
from app.modules.file import repository as file_repository
from app.modules.file import service as file_service
from app.modules.file.schemas import FileRead
from app.modules.project import repository
from app.modules.project.models import Project
from app.modules.project.schemas import (
    ProjectCreate,
    ProjectFileRead,
    ProjectRead,
    ProjectUpdate,
)
from app.modules.workspace import service as workspace_service
from app.shared.enums import PROJECT_STATUSES
from app.shared.exceptions import ConflictError, NotFoundError, UnprocessableError


def _to_read(session: Session, project: Project) -> ProjectRead:
    data = ProjectRead.model_validate(project)
    return data.model_copy(
        update={
            "task_count": repository.count_tasks(session, project.id),
            "file_count": repository.count_files(session, project.id),
        }
    )


def list_projects(
    session: Session,
    *,
    workspace_id: uuid.UUID | None,
    status: str | None,
    limit: int = 50,
    offset: int = 0,
) -> list[ProjectRead]:
    projects = repository.list_projects(
        session,
        workspace_id=workspace_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return [_to_read(session, project) for project in projects]


def get_project(session: Session, project_id: uuid.UUID) -> Project:
    project = repository.get(session, project_id)
    if project is None:
        raise NotFoundError("项目不存在", details={"project_id": str(project_id)})
    return project


def get_project_read(session: Session, project_id: uuid.UUID) -> ProjectRead:
    return _to_read(session, get_project(session, project_id))


def create_project(session: Session, payload: ProjectCreate) -> ProjectRead:
    settings = get_settings()
    if payload.workspace_id is None:
        workspace = workspace_service.get_default_workspace(
            session, settings.default_workspace_name
        )
    else:
        workspace = workspace_service.get_workspace(session, payload.workspace_id)
    project = repository.create(
        session,
        workspace_id=workspace.id,
        name=payload.name.strip(),
        description=payload.description,
    )
    session.commit()
    session.refresh(project)
    return _to_read(session, project)


def update_project(
    session: Session, project_id: uuid.UUID, payload: ProjectUpdate
) -> ProjectRead:
    project = get_project(session, project_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("status") is not None:
        if data["status"] not in PROJECT_STATUSES:
            raise UnprocessableError(
                "非法的项目状态",
                details={"allowed": list(PROJECT_STATUSES)},
            )
        project.status = data["status"]
    if data.get("name") is not None:
        project.name = data["name"].strip()
    if "description" in data:
        project.description = data["description"]
    session.commit()
    session.refresh(project)
    return _to_read(session, project)


def delete_project(session: Session, project_id: uuid.UUID) -> None:
    project = get_project(session, project_id)
    task_count = repository.count_tasks(session, project_id)
    if task_count > 0:
        raise ConflictError(
            "项目下存在任务，无法删除；请先删除或归档这些任务",
            details={"task_count": task_count},
        )
    repository.delete(session, project)
    session.commit()
    file_service.cleanup_project_private_files(session, project_id)


def list_project_files(session: Session, project_id: uuid.UUID) -> list[ProjectFileRead]:
    get_project(session, project_id)
    rows = repository.list_files(session, project_id)
    return [
        ProjectFileRead(
            file=FileRead.model_validate(file),
            added_at=link.added_at,
            source="project",
        )
        for link, file in rows
    ]


def add_project_file(
    session: Session, project_id: uuid.UUID, file_id: uuid.UUID
) -> ProjectFileRead:
    get_project(session, project_id)
    file = file_repository.get(session, file_id)
    if file is None or file.status != "active":
        raise NotFoundError("文件不存在或已删除", details={"file_id": str(file_id)})
    if repository.get_project_file(session, project_id, file_id) is not None:
        raise ConflictError("文件已在项目上下文中", details={"file_id": str(file_id)})
    link = repository.add_file(session, project_id, file_id)
    session.commit()
    session.refresh(link)
    return ProjectFileRead(
        file=FileRead.model_validate(file),
        added_at=link.added_at,
        source="project",
    )


def upload_project_file(
    session: Session, project_id: uuid.UUID, upload: UploadFile
) -> ProjectFileRead:
    """上传项目私有文件：不进入 Global Library，默认给项目内 Task 使用。"""
    project = get_project(session, project_id)
    file = file_service.upload_file(
        session,
        upload,
        is_temporary=True,
        owner_project_id=project.id,
    )
    link = repository.get_project_file(session, project.id, file.id)
    if link is None:
        link = repository.add_file(session, project.id, file.id)
        session.commit()
        session.refresh(link)
    return ProjectFileRead(
        file=file,
        added_at=link.added_at,
        source="project",
    )


def remove_project_file(
    session: Session, project_id: uuid.UUID, file_id: uuid.UUID
) -> None:
    get_project(session, project_id)
    link = repository.get_project_file(session, project_id, file_id)
    if link is None:
        raise NotFoundError(
            "文件不在该项目的上下文中",
            details={"project_id": str(project_id), "file_id": str(file_id)},
        )
    repository.remove_file(session, link)
    session.commit()
    file_service.cleanup_project_private_file(session, project_id, file_id)
