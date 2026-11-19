from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskCreate(BaseModel):
    workspace_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    model_provider: str | None = Field(default=None, max_length=50)
    model_name: str | None = Field(default=None, max_length=100)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=32000)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    status: str | None = None
    model_provider: str | None = Field(default=None, max_length=50)
    model_name: str | None = Field(default=None, max_length=100)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=32000)
    # Only used to reject project changes explicitly (MVP forbids it).
    project_id: uuid.UUID | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID | None
    title: str
    description: str | None
    status: str
    model_provider: str | None
    model_name: str | None
    temperature: float | None = None
    max_tokens: int | None = None
    usage: dict | None = None
    created_at: datetime
    updated_at: datetime
