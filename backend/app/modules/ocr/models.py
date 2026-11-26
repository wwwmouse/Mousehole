"""OCR 派生数据：页级文本与页面准备任务。"""

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
from app.infrastructure.database.mixins import TimestampMixin
from app.shared.db_types import UUIDType


class FilePage(Base):
    __tablename__ = "file_pages"
    __table_args__ = (
        UniqueConstraint("file_id", "page_no", name="file_page_unique"),
        CheckConstraint(
            "text_source IN ('native', 'ocr')",
            name="file_page_text_source_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_source: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OcrJob(TimestampMixin, Base):
    __tablename__ = "ocr_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ocr_job_status_valid",
        ),
        CheckConstraint(
            "route IN ('text', 'ocr', 'mixed')",
            name="ocr_job_route_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    route: Mapped[str] = mapped_column(String(20), nullable=False)
    total_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_pages: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    image_coverage: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
