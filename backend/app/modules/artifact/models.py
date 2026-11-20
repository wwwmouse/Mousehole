from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import TimestampMixin
from app.shared.db_types import UUIDType


class ArtifactSeries(TimestampMixin, Base):
    __tablename__ = "artifact_series"
    __table_args__ = (
        UniqueConstraint("task_id", "title", name="artifact_series_title_unique"),
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
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Points at an Artifact of this series; validated in the service layer.
    current_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, nullable=True
    )


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        CheckConstraint("version > 0", name="artifact_version_positive"),
        UniqueConstraint("series_id", "version", name="artifact_version_unique"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    series_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("artifact_series.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType,
        ForeignKey("executions.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    # execution | chat | manual
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="execution"
    )
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType,
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="text/markdown"
    )
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
