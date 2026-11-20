from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.artifact.models import Artifact, ArtifactSeries


def get_series_by_title(
    session: Session, task_id: uuid.UUID, title: str
) -> ArtifactSeries | None:
    return session.scalars(
        select(ArtifactSeries).where(
            ArtifactSeries.task_id == task_id, ArtifactSeries.title == title
        )
    ).first()


def get_series(session: Session, series_id: uuid.UUID) -> ArtifactSeries | None:
    return session.get(ArtifactSeries, series_id)


def list_series(session: Session, task_id: uuid.UUID) -> list[ArtifactSeries]:
    stmt = (
        select(ArtifactSeries)
        .where(ArtifactSeries.task_id == task_id)
        .order_by(ArtifactSeries.created_at)
    )
    return list(session.scalars(stmt))


def create_series(
    session: Session, *, task_id: uuid.UUID, title: str, description: str | None = None
) -> ArtifactSeries:
    series = ArtifactSeries(task_id=task_id, title=title, description=description)
    session.add(series)
    session.flush()
    return series


def next_version(session: Session, series_id: uuid.UUID) -> int:
    current = session.scalar(
        select(func.max(Artifact.version)).where(Artifact.series_id == series_id)
    )
    return int(current or 0) + 1


def create_artifact(
    session: Session,
    *,
    series_id: uuid.UUID,
    version: int,
    title: str,
    content: str | None,
    content_type: str,
    source_execution_id: uuid.UUID | None,
    storage_key: str | None = None,
) -> Artifact:
    artifact = Artifact(
        series_id=series_id,
        version=version,
        title=title,
        content=content,
        content_type=content_type,
        source_execution_id=source_execution_id,
        storage_key=storage_key,
    )
    session.add(artifact)
    session.flush()
    return artifact


def list_by_project(session: Session, project_id: uuid.UUID):
    from app.modules.task.models import Task

    stmt = (
        select(ArtifactSeries)
        .join(Task, Task.id == ArtifactSeries.task_id)
        .where(Task.project_id == project_id)
        .order_by(ArtifactSeries.created_at.desc())
    )
    return list(session.scalars(stmt))


def list_by_execution(
    session: Session, execution_id: uuid.UUID
) -> list[Artifact]:
    stmt = (
        select(Artifact)
        .where(Artifact.source_execution_id == execution_id)
        .order_by(Artifact.created_at)
    )
    return list(session.scalars(stmt))


def get_artifact(session: Session, artifact_id: uuid.UUID) -> Artifact | None:
    return session.get(Artifact, artifact_id)


def list_artifacts(session: Session, series_id: uuid.UUID) -> list[Artifact]:
    stmt = (
        select(Artifact)
        .where(Artifact.series_id == series_id)
        .order_by(Artifact.version.desc())
    )
    return list(session.scalars(stmt))
