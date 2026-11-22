from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class TokenStats(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class DailyStats(BaseModel):
    date: str  # local date, YYYY-MM-DD
    conversation_turns: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class RecentArtifact(BaseModel):
    artifact_id: uuid.UUID
    title: str
    version: int
    source_type: str | None = None
    task_id: uuid.UUID
    task_title: str
    project_id: uuid.UUID | None
    project_name: str | None
    created_at: datetime


class StatsOverview(BaseModel):
    period_days: int
    conversation_turns: int
    execution_count: int
    tokens: TokenStats
    tokens_complete: bool
    daily: list[DailyStats]
    recent_artifacts: list[RecentArtifact]
