from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.api.deps import DbSession
from app.modules.workspace import service
from app.modules.workspace.schemas import WorkspaceRead, WorkspaceUpdate

router = APIRouter()


@router.get("", response_model=list[WorkspaceRead])
def list_workspaces(db: DbSession) -> list[WorkspaceRead]:
    return [WorkspaceRead.model_validate(item) for item in service.list_workspaces(db)]


@router.get("/{workspace_id}", response_model=WorkspaceRead)
def get_workspace(workspace_id: uuid.UUID, db: DbSession) -> WorkspaceRead:
    return WorkspaceRead.model_validate(service.get_workspace(db, workspace_id))


@router.patch("/{workspace_id}", response_model=WorkspaceRead)
def update_workspace(
    workspace_id: uuid.UUID, payload: WorkspaceUpdate, db: DbSession
) -> WorkspaceRead:
    return WorkspaceRead.model_validate(
        service.update_workspace(db, workspace_id, payload)
    )
