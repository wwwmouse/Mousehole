from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.workspace.models import Workspace


def list_all(session: Session) -> list[Workspace]:
    return list(session.scalars(select(Workspace).order_by(Workspace.created_at)))


def get(session: Session, workspace_id: uuid.UUID) -> Workspace | None:
    return session.get(Workspace, workspace_id)


def first(session: Session) -> Workspace | None:
    return session.scalars(select(Workspace).order_by(Workspace.created_at).limit(1)).first()


def create(
    session: Session, *, name: str, description: str | None = None
) -> Workspace:
    workspace = Workspace(name=name, description=description)
    session.add(workspace)
    session.flush()
    return workspace
