from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.modules.workspace import repository
from app.modules.workspace.models import Workspace
from app.modules.workspace.schemas import WorkspaceUpdate
from app.shared.exceptions import NotFoundError


def ensure_default_workspace(session: Session, default_name: str) -> Workspace:
    workspace = repository.first(session)
    if workspace is not None:
        return workspace
    workspace = repository.create(session, name=default_name)
    session.commit()
    session.refresh(workspace)
    return workspace


def list_workspaces(session: Session) -> list[Workspace]:
    return repository.list_all(session)


def get_workspace(session: Session, workspace_id: uuid.UUID) -> Workspace:
    workspace = repository.get(session, workspace_id)
    if workspace is None:
        raise NotFoundError("工作空间不存在", details={"workspace_id": str(workspace_id)})
    return workspace


def get_default_workspace(session: Session, default_name: str) -> Workspace:
    return repository.first(session) or ensure_default_workspace(session, default_name)


def update_workspace(
    session: Session, workspace_id: uuid.UUID, payload: WorkspaceUpdate
) -> Workspace:
    workspace = get_workspace(session, workspace_id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        workspace.name = data["name"]
    if "description" in data:
        workspace.description = data["description"]
    if "default_temperature" in data:
        workspace.default_temperature = data["default_temperature"]
    if "default_max_tokens" in data:
        workspace.default_max_tokens = data["default_max_tokens"]
    if "context_budget_tokens" in data:
        workspace.context_budget_tokens = data["context_budget_tokens"]
    session.commit()
    session.refresh(workspace)
    return workspace
