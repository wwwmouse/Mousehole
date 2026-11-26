from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.ocr.models import FilePage, OcrJob


def create_job(
    session: Session,
    *,
    file_id: uuid.UUID,
    route: str,
    total_pages: int,
    image_coverage: float,
) -> OcrJob:
    job = OcrJob(
        file_id=file_id,
        status="pending",
        route=route,
        total_pages=total_pages,
        processed_pages=0,
        image_coverage=image_coverage,
    )
    session.add(job)
    session.flush()
    return job


def get_job(session: Session, job_id: uuid.UUID) -> OcrJob | None:
    return session.get(OcrJob, job_id)


def latest_job(session: Session, file_id: uuid.UUID) -> OcrJob | None:
    return session.scalars(
        select(OcrJob)
        .where(OcrJob.file_id == file_id)
        .order_by(OcrJob.created_at.desc(), OcrJob.id.desc())
        .limit(1)
    ).first()


def active_job(session: Session, file_id: uuid.UUID) -> OcrJob | None:
    return session.scalars(
        select(OcrJob)
        .where(
            OcrJob.file_id == file_id,
            OcrJob.status.in_(("pending", "running")),
        )
        .order_by(OcrJob.created_at.desc())
        .limit(1)
    ).first()


def mark_started(session: Session, job: OcrJob) -> None:
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    job.processed_pages = 0
    session.flush()


def mark_progress(session: Session, job: OcrJob, processed: int) -> None:
    job.processed_pages = processed
    session.flush()


def mark_completed(session: Session, job: OcrJob) -> None:
    job.status = "completed"
    job.completed_at = datetime.now(timezone.utc)
    job.error = None
    session.flush()


def mark_failed(session: Session, job: OcrJob, error: str) -> None:
    job.status = "failed"
    job.completed_at = datetime.now(timezone.utc)
    job.error = error[:4000]
    session.flush()


def list_pages(
    session: Session,
    file_id: uuid.UUID,
    *,
    offset: int = 0,
    limit: int = 50,
) -> list[FilePage]:
    return list(
        session.scalars(
            select(FilePage)
            .where(FilePage.file_id == file_id)
            .order_by(FilePage.page_no)
            .offset(offset)
            .limit(limit)
        )
    )


def count_pages(session: Session, file_id: uuid.UUID) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(FilePage)
            .where(FilePage.file_id == file_id)
        )
        or 0
    )


def page_source_counts(
    session: Session, file_id: uuid.UUID
) -> tuple[int, int]:
    """返回 (native_pages, ocr_pages)。"""
    rows = session.execute(
        select(FilePage.text_source, func.count())
        .where(FilePage.file_id == file_id)
        .group_by(FilePage.text_source)
    ).all()
    counts = {source: int(count) for source, count in rows}
    return counts.get("native", 0), counts.get("ocr", 0)


def all_pages(session: Session, file_id: uuid.UUID) -> list[FilePage]:
    return list(
        session.scalars(
            select(FilePage)
            .where(FilePage.file_id == file_id)
            .order_by(FilePage.page_no)
        )
    )


def delete_pages(session: Session, file_id: uuid.UUID) -> None:
    session.execute(
        FilePage.__table__.delete().where(FilePage.file_id == file_id)
    )
    session.flush()


def add_page(
    session: Session,
    *,
    file_id: uuid.UUID,
    page_no: int,
    text: str,
    text_source: str,
    confidence: float | None = None,
) -> FilePage:
    page = FilePage(
        file_id=file_id,
        page_no=page_no,
        text=text,
        text_source=text_source,
        confidence=confidence,
    )
    session.add(page)
    session.flush()
    return page


def recover_interrupted_jobs(session: Session) -> int:
    jobs = list(
        session.scalars(
            select(OcrJob).where(OcrJob.status.in_(("pending", "running")))
        )
    )
    for job in jobs:
        mark_failed(session, job, "服务重启，任务中断；请重新发起 OCR")
    if jobs:
        session.commit()
    return len(jobs)
