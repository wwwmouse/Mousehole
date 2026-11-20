from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    series_id: uuid.UUID
    source_execution_id: uuid.UUID | None
    version: int
    title: str
    content_type: str
    content: str | None
    storage_key: str | None
    created_at: datetime


class ArtifactSeriesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    title: str
    description: str | None
    current_artifact_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class ArtifactSeriesDetail(ArtifactSeriesRead):
    artifacts: list[ArtifactRead] = []


class SeriesUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
