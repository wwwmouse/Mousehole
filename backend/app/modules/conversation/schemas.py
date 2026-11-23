from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    sequence: int
    usage: dict[str, Any] | None
    metadata: dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices("message_metadata", "metadata"),
    )
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
    skill_id: str | None = Field(default=None, max_length=100)
    # Task-scoped temporary files used ONLY for this message.
    file_ids: list[str] = Field(default_factory=list, max_length=20)
    # Phase 5 H4: chat = no tool calls at all; work = all controlled tools are
    # offered to the model (which decides whether to use them).
    mode: Literal["chat", "work"] = "work"
