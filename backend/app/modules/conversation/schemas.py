from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    sequence: int
    usage: dict[str, Any] | None
    created_at: datetime


class TaskMessagesRead(BaseModel):
    task_id: uuid.UUID
    conversation_id: uuid.UUID | None
    messages: list[MessageRead]
    task_usage: dict[str, Any] | None


class ChatRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20000)
    provider: str | None = Field(default=None, max_length=50)
    model: str | None = Field(default=None, max_length=100)
