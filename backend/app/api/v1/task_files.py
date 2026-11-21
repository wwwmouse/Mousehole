"""Task file-context API (inherited / included / excluded files).

Contract:
  GET    /api/v1/tasks/{task_id}/files           available + excluded files
  POST   /api/v1/tasks/{task_id}/files           include / exclude override
  DELETE /api/v1/tasks/{task_id}/files/{file_id} remove override
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Response, UploadFile, status

from app.api.deps import DbSession
from app.modules.context import service as context_service
from app.modules.file import service as file_service
from app.modules.file.schemas import (
    FileRead,
    TaskFileOverrideRequest,
    TaskFilesResponse,
)
from app.modules.task import service as task_service
from app.shared.exceptions import NotFoundError

router = APIRouter()


@router.get("/{task_id}/files", response_model=TaskFilesResponse)
def list_task_files(task_id: uuid.UUID, db: DbSession) -> TaskFilesResponse:
    return context_service.get_task_files(db, task_id)


@router.post(
    "/{task_id}/files/upload",
    response_model=FileRead,
    status_code=status.HTTP_201_CREATED,
)
def upload_task_temporary_file(
    task_id: uuid.UUID, db: DbSession, file: UploadFile
) -> FileRead:
    """Upload a Task-scoped temporary file and include it in that Task.

    Temporary files never appear in the Global Library and are discarded when
    the Task reference is removed (unless a historical snapshot needs them).
    """
    task_service.get_task(db, task_id)
    # No Task include override: the file is sent as a per-message attachment
    # via ChatRequest.file_ids and disappears from the next turn.
    return file_service.upload_file(
        db, file, is_temporary=True, owner_task_id=task_id
    )


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
    try:
        context_service.remove_task_file(db, task_id, file_id)
    except NotFoundError:
        # Temporary files have no override; removing one discards the file.
        file_service.delete_temporary_file(db, task_id, file_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
