from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    file_type: str
    mime_type: str
    size: int
    content_hash: str
    status: str
    created_at: datetime
    updated_at: datetime


class FileDetail(FileRead):
    references: list["FileReference"] = Field(default_factory=list)


class FileReference(BaseModel):
    kind: str  # project | task
    id: uuid.UUID
    name: str


class FileContentRead(BaseModel):
    file: FileRead
    text: str
    truncated: bool


# --- Phase 1: Task file context schemas (append-only) ---

from typing import Literal  # noqa: E402


class TaskFileEntry(BaseModel):
    """One file available to a Task, with where it came from."""

    file: FileRead
    source: Literal["project_inherited", "task_added"]


class TaskFilesResponse(BaseModel):
    """Effective file context of a Task (available context, not execution input)."""

    available: list[TaskFileEntry] = Field(default_factory=list)
    excluded: list[FileRead] = Field(default_factory=list)
    project_file_count: int = 0
    task_include_count: int = 0
    task_exclude_count: int = 0


class TaskFileOverrideRequest(BaseModel):
    file_id: uuid.UUID
    action: Literal["include", "exclude"]


FileDetail.model_rebuild()
