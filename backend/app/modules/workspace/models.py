from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import TimestampMixin
from app.shared.db_types import UUIDType


class Workspace(TimestampMixin, Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Workspace-level model defaults; Task-level values override them.
    default_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    default_max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Optional context budget override (tokens); None = auto from model window.
    context_budget_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
