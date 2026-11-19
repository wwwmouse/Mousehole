from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    default_temperature: float | None = Field(default=None, ge=0, le=2)
    default_max_tokens: int | None = Field(default=None, ge=1, le=32000)


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    default_temperature: float | None = None
    default_max_tokens: int | None = None
    created_at: datetime
    updated_at: datetime
