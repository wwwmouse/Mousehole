from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ExecutionStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sequence: int
    step_type: str
    name: str
    status: str
    input_summary: str | None = None
    output_summary: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None


class ExecutionSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    file_id: uuid.UUID
    filename_snapshot: str
    content_hash_snapshot: str
    source_type: str
    usage_mode: str
    used_at: datetime


class ExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    sequence: int
    status: str
    skill_id: str | None = None
    skill_name: str | None = None
    model_provider: str | None
    model_name: str | None
    temperature: float | None
    max_tokens: int | None
    input_summary: str | None
    error_message: str | None
    error_code: str | None
    usage: dict[str, Any] | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class ExecutionCreate(BaseModel):
    skill_id: str | None = None


class ExecutionDetail(ExecutionRead):
    steps: list[ExecutionStepRead] = []
    snapshots: list[ExecutionSnapshotRead] = []
    artifact_ids: list[uuid.UUID] = []
