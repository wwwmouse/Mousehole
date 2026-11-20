from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.api.deps import DbSession
from app.modules.artifact import service as artifact_service
from app.modules.artifact.schemas import (
    ArtifactRead,
    ArtifactSeriesDetail,
    ArtifactSeriesRead,
    SeriesUpdate,
)
from app.modules.task import service as task_service

router = APIRouter()


@router.get(
    "/tasks/{task_id}/artifact-series",
    response_model=list[ArtifactSeriesRead],
)
def list_series(task_id: uuid.UUID, db: DbSession) -> list[ArtifactSeriesRead]:
    task_service.get_task(db, task_id)
    return [
        ArtifactSeriesRead.model_validate(series)
        for series in artifact_service.list_task_series(db, task_id)
    ]


@router.get(
    "/projects/{project_id}/artifact-series",
    response_model=list[ArtifactSeriesRead],
)
def list_project_series(
    project_id: uuid.UUID, db: DbSession
) -> list[ArtifactSeriesRead]:
    from app.modules.project import service as project_service

    project_service.get_project(db, project_id)
    return [
        ArtifactSeriesRead.model_validate(series)
        for series in artifact_service.list_project_series(db, project_id)
    ]


@router.get(
    "/artifact-series/{series_id}", response_model=ArtifactSeriesDetail
)
def get_series(series_id: uuid.UUID, db: DbSession) -> ArtifactSeriesDetail:
    series = artifact_service.get_series(db, series_id)
    detail = ArtifactSeriesDetail.model_validate(series)
    detail.artifacts = [
        ArtifactRead.model_validate(artifact)
        for artifact in artifact_service.list_series_artifacts(db, series.id)
    ]
    return detail


@router.patch(
    "/artifact-series/{series_id}", response_model=ArtifactSeriesRead
)
def rename_series(
    series_id: uuid.UUID, payload: SeriesUpdate, db: DbSession
) -> ArtifactSeriesRead:
    series = artifact_service.get_series(db, series_id)
    updated = artifact_service.rename_series(db, series, payload.title)
    db.commit()
    db.refresh(updated)
    return ArtifactSeriesRead.model_validate(updated)


@router.get("/artifacts/{artifact_id}", response_model=ArtifactRead)
def get_artifact(artifact_id: uuid.UUID, db: DbSession) -> ArtifactRead:
    return ArtifactRead.model_validate(artifact_service.get_artifact(db, artifact_id))
