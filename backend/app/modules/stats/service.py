from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.artifact.models import Artifact, ArtifactSeries
from app.modules.conversation.models import Message
from app.modules.execution.models import Execution
from app.modules.project.models import Project
from app.modules.stats.schemas import (
    DailyStats,
    RecentArtifact,
    StatsOverview,
    TokenStats,
)
from app.modules.task.models import Task

TERMINAL_EXECUTION_STATUSES = {"completed", "failed", "cancelled"}


def _local_date(value: datetime, tz) -> date:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(tz).date()


def _add_usage(bucket: DailyStats, usage: dict | None) -> bool:
    if not usage:
        return False
    bucket.prompt_tokens += int(usage.get("prompt_tokens") or 0)
    bucket.completion_tokens += int(usage.get("completion_tokens") or 0)
    bucket.total_tokens += int(usage.get("total_tokens") or 0)
    return True


def overview(session: Session, *, days: int = 7) -> StatsOverview:
    days = max(1, min(days, 90))
    tz = datetime.now().astimezone().tzinfo or timezone.utc
    today = datetime.now(tz).date()
    first_day = today - timedelta(days=days - 1)
    since = datetime.combine(first_day, time.min, tzinfo=tz).astimezone(timezone.utc)

    daily: dict[str, DailyStats] = {
        (first_day + timedelta(days=offset)).isoformat(): DailyStats(
            date=(first_day + timedelta(days=offset)).isoformat()
        )
        for offset in range(days)
    }

    tokens_complete = True

    user_messages = session.scalars(
        select(Message).where(Message.role == "user", Message.created_at >= since)
    )
    for message in user_messages:
        key = _local_date(message.created_at, tz).isoformat()
        if key in daily:
            daily[key].conversation_turns += 1

    assistant_messages = session.scalars(
        select(Message).where(
            Message.role == "assistant", Message.created_at >= since
        )
    )
    for message in assistant_messages:
        key = _local_date(message.created_at, tz).isoformat()
        bucket = daily.get(key)
        if bucket is None:
            continue
        if not _add_usage(bucket, message.usage):
            tokens_complete = False

    executions = list(
        session.scalars(select(Execution).where(Execution.created_at >= since))
    )
    for execution in executions:
        if execution.status not in TERMINAL_EXECUTION_STATUSES:
            continue
        key = _local_date(execution.created_at, tz).isoformat()
        bucket = daily.get(key)
        if bucket is None:
            continue
        if not _add_usage(bucket, execution.usage):
            tokens_complete = False

    daily_items = [daily[key] for key in sorted(daily)]
    tokens = TokenStats(
        prompt_tokens=sum(item.prompt_tokens for item in daily_items),
        completion_tokens=sum(item.completion_tokens for item in daily_items),
        total_tokens=sum(item.total_tokens for item in daily_items),
    )
    conversation_turns = sum(item.conversation_turns for item in daily_items)

    recent_rows = session.execute(
        select(Artifact, ArtifactSeries, Task, Project)
        .join(ArtifactSeries, ArtifactSeries.id == Artifact.series_id)
        .join(Task, Task.id == ArtifactSeries.task_id)
        .outerjoin(Project, Project.id == Task.project_id)
        .order_by(Artifact.created_at.desc())
        .limit(5)
    ).all()
    recent_artifacts = [
        RecentArtifact(
            artifact_id=artifact.id,
            title=artifact.title,
            version=artifact.version,
            task_id=task.id,
            task_title=task.title,
            project_id=project.id if project else None,
            project_name=project.name if project else None,
            created_at=artifact.created_at,
        )
        for artifact, series, task, project in recent_rows
    ]

    return StatsOverview(
        period_days=days,
        conversation_turns=conversation_turns,
        execution_count=len(executions),
        tokens=tokens,
        tokens_complete=tokens_complete,
        daily=daily_items,
        recent_artifacts=recent_artifacts,
    )
