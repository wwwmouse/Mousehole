from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.file.schemas import FileRead


class ProjectCreate(BaseModel):
    workspace_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    status: str | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    task_count: int = 0
    file_count: int = 0


class ProjectFileCreate(BaseModel):
    file_id: uuid.UUID


class ProjectFileRead(BaseModel):
    file: FileRead
    added_at: datetime
    source: str = "project"
