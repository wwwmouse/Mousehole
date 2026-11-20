from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SkillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str | None
    name: str
    description: str | None
    system_prompt: str
    instruction: str
    output_type: str
    is_builtin: bool
    created_at: datetime
    updated_at: datetime


class SkillCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    instruction: str = Field(min_length=1)
    system_prompt: str | None = None


class SkillUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    instruction: str | None = None
    system_prompt: str | None = None


class TaskSkillAdd(BaseModel):
    skill_id: uuid.UUID


class SkillFileRead(BaseModel):
    file_id: uuid.UUID
    filename: str
    file_type: str
    size: int
    path: str | None
    created_at: datetime


class SkillFileAdd(BaseModel):
    file_id: uuid.UUID
    path: str | None = Field(default=None, max_length=1024)
