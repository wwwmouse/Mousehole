from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Response, status

from app.api.deps import DbSession
from app.modules.task import service
from app.modules.task.schemas import TaskCreate, TaskRead, TaskUpdate

router = APIRouter()


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, db: DbSession) -> TaskRead:
    return service.create_task(db, payload)


@router.get("", response_model=list[TaskRead])
def list_tasks(
    db: DbSession,
    workspace_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[TaskRead]:
    return service.list_tasks(
        db,
        workspace_id=workspace_id,
        project_id=project_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: uuid.UUID, db: DbSession) -> Response:
    service.delete_task(db, task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: uuid.UUID, db: DbSession) -> TaskRead:
    return service.get_task_read(db, task_id)


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(task_id: uuid.UUID, payload: TaskUpdate, db: DbSession) -> TaskRead:
    return service.update_task(db, task_id, payload)
