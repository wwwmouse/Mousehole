from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from app.api.deps import DbSession
from app.modules.ocr import service as ocr_service
from app.modules.ocr.schemas import FilePagesRead, OcrJobRead

router = APIRouter()


def _job_read(db: DbSession, job) -> OcrJobRead:
    native_pages, ocr_pages = ocr_service.page_source_counts(
        db, job.file_id
    )
    current_page = None
    if job.status in ("pending", "running"):
        current_page = min(job.total_pages, job.processed_pages + 1)
    return OcrJobRead.model_validate(job).model_copy(
        update={
            "current_page": current_page,
            "native_pages": native_pages,
            "ocr_pages": ocr_pages,
        }
    )


@router.post(
    "/files/{file_id}/ocr",
    response_model=OcrJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_ocr(file_id: uuid.UUID, db: DbSession) -> OcrJobRead:
    """创建页面准备任务：文本页直接提取，扫描页调用 OCR。"""
    return _job_read(db, ocr_service.start_job(db, file_id))


@router.get(
    "/files/{file_id}/ocr",
    response_model=OcrJobRead | None,
)
def get_latest_ocr_job(
    file_id: uuid.UUID, db: DbSession
) -> OcrJobRead | None:
    job = ocr_service.latest_job(db, file_id)
    return _job_read(db, job) if job is not None else None


@router.get(
    "/files/{file_id}/pages",
    response_model=FilePagesRead,
)
def list_file_pages(
    file_id: uuid.UUID,
    db: DbSession,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> FilePagesRead:
    total, pages = ocr_service.list_pages(
        db, file_id, offset=offset, limit=limit
    )
    return FilePagesRead(
        file_id=file_id,
        total=total,
        offset=offset,
        limit=limit,
        pages=pages,
    )
