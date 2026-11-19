"""Task file-context API (inherited / included / excluded files).

Contract:
  GET    /api/v1/tasks/{task_id}/files           available + excluded files
  POST   /api/v1/tasks/{task_id}/files           include / exclude override
  DELETE /api/v1/tasks/{task_id}/files/{file_id} remove override
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Response, status

from app.api.deps import DbSession
from app.modules.context import service as context_service
from app.modules.file.schemas import (
    TaskFileOverrideRequest,
    TaskFilesResponse,
)

router = APIRouter()


@router.get("/{task_id}/files", response_model=TaskFilesResponse)
def list_task_files(task_id: uuid.UUID, db: DbSession) -> TaskFilesResponse:
    return context_service.get_task_files(db, task_id)


@router.post(
    "/{task_id}/files",
    response_model=TaskFilesResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_task_file(
    task_id: uuid.UUID,
    payload: TaskFileOverrideRequest,
    db: DbSession,
    response: Response,
) -> TaskFilesResponse:
    result = context_service.add_task_file(db, task_id, payload)
    if not result.created:
        # Idempotent re-request or an opposite-action update.
        response.status_code = status.HTTP_200_OK
    return result.files


@router.delete(
    "/{task_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_task_file(
    task_id: uuid.UUID, file_id: uuid.UUID, db: DbSession
) -> Response:
    context_service.remove_task_file(db, task_id, file_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
