from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Response, UploadFile, status

from app.api.deps import DbSession
from app.modules.project import service
from app.modules.project.schemas import (
    ProjectCreate,
    ProjectFileCreate,
    ProjectFileRead,
    ProjectRead,
    ProjectUpdate,
)

router = APIRouter()


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: DbSession) -> ProjectRead:
    return service.create_project(db, payload)


@router.get("", response_model=list[ProjectRead])
def list_projects(
    db: DbSession,
    workspace_id: uuid.UUID | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ProjectRead]:
    return service.list_projects(
        db,
        workspace_id=workspace_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: uuid.UUID, db: DbSession) -> ProjectRead:
    return service.get_project_read(db, project_id)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: uuid.UUID, payload: ProjectUpdate, db: DbSession
) -> ProjectRead:
    return service.update_project(db, project_id, payload)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: uuid.UUID, db: DbSession) -> Response:
    service.delete_project(db, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{project_id}/files", response_model=list[ProjectFileRead])
def list_project_files(
    project_id: uuid.UUID, db: DbSession
) -> list[ProjectFileRead]:
    return service.list_project_files(db, project_id)


@router.post(
    "/{project_id}/files/upload",
    response_model=ProjectFileRead,
    status_code=status.HTTP_201_CREATED,
)
def upload_project_file(
    project_id: uuid.UUID, db: DbSession, file: UploadFile
) -> ProjectFileRead:
    """上传项目私有文件：只在项目内可见，不进入 Global Library。"""
    return service.upload_project_file(db, project_id, file)


@router.post(
    "/{project_id}/files",
    response_model=ProjectFileRead,
    status_code=status.HTTP_201_CREATED,
)
def add_project_file(
    project_id: uuid.UUID, payload: ProjectFileCreate, db: DbSession
) -> ProjectFileRead:
    return service.add_project_file(db, project_id, payload.file_id)


@router.delete("/{project_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project_file(
    project_id: uuid.UUID, file_id: uuid.UUID, db: DbSession
) -> Response:
    service.remove_project_file(db, project_id, file_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
