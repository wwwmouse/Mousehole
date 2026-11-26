from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OcrJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    file_id: uuid.UUID
    status: str
    route: str
    total_pages: int
    processed_pages: int
    image_coverage: float
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    current_page: int | None = None
    native_pages: int = 0
    ocr_pages: int = 0


class FilePageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    page_no: int
    text: str
    text_source: str
    confidence: float | None


class FilePagesRead(BaseModel):
    file_id: uuid.UUID
    total: int
    offset: int
    limit: int
    pages: list[FilePageRead]
