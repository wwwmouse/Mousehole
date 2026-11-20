from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.shared.db_types import UUIDType, UsageJSON
from app.shared.enums import ExecutionStatus, ExecutionStepStatus


class Execution(Base):
    __tablename__ = "executions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="execution_status_valid",
        ),
        UniqueConstraint("task_id", "sequence", name="execution_sequence_unique"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("tasks.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ExecutionStatus.PENDING.value
    )
    # Skill snapshot (thin layer; code registry today, DB entity later).
    skill_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    skill_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Model configuration snapshot for this execution (never rewritten later).
    model_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    usage: Mapped[dict | None] = mapped_column(UsageJSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ExecutionStep(Base):
    __tablename__ = "execution_steps"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'skipped')",
            name="execution_step_status_valid",
        ),
        UniqueConstraint("execution_id", "sequence", name="execution_step_sequence_unique"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("executions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ExecutionStepStatus.PENDING.value
    )
    input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExecutionFileSnapshot(Base):
    __tablename__ = "execution_file_snapshots"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('project_inherited', 'task_added', 'skill_asset')",
            name="snapshot_source_type_valid",
        ),
        CheckConstraint(
            "usage_mode IN ('direct', 'summarized')",
            name="snapshot_usage_mode_valid",
        ),
        UniqueConstraint("execution_id", "file_id", name="execution_file_unique"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("executions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("files.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    filename_snapshot: Mapped[str] = mapped_column(String(512), nullable=False)
    content_hash_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    usage_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
