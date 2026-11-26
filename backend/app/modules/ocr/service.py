# 模块职责：OCR 任务服务：创建任务、后台逐页处理、进度、页文本和中断恢复。
# 对外函数：
# - start_job(session, file_id)：创建并提交页面准备任务。
# - latest_job(session, file_id)：读取最新任务状态。
# - page_source_counts(session, file_id)：统计 native/ocr 页数。
# - list_pages(session, file_id, *, offset=0, limit=50)：分页读取页文本。
# - get_pages_text(session, file_id)：有页文本时返回按页拼接文本，否则 None；供读取链路优先使用。
# - run_job(job_id, *, client=None, session_factory=None)：同步执行任务（API 线程/测试）。
# - recover_interrupted(session)：把上次进程残留的 running 任务标记 failed。
# - shutdown_worker()：关闭后台线程池。
"""OCR 任务服务：创建任务、后台逐页处理、页级文本读取。"""

from __future__ import annotations

import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pymupdf
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.session import get_session_factory
from app.modules.document.pdf_router import (
    ROUTE_OCR,
    ROUTE_TEXT,
    inspect_pdf,
)
from app.modules.document.vlm_ocr import VlmOcrClient, VlmOcrConfig
from app.modules.file import service as file_service
from app.modules.file.storage import get_storage
from app.modules.ocr import repository
from app.modules.ocr.models import FilePage, OcrJob
from app.shared.exceptions import (
    ConflictError,
    NotFoundError,
    UnprocessableError,
)

logger = logging.getLogger("mousehole.ocr")

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ocr-job")


def _dpi() -> int:
    return int(os.getenv("OCR_DPI", "200"))


def _threshold() -> float:
    return float(os.getenv("OCR_IMAGE_COVERAGE_THRESHOLD", "70"))


def start_job(session: Session, file_id: uuid.UUID) -> OcrJob:
    """创建并提交一次页面准备任务（文本页 native + 扫描页 OCR）。"""
    file = file_service.get_file(session, file_id)
    if file.file_type != "pdf":
        raise UnprocessableError(
            "只有 PDF 支持页面准备/OCR",
            details={"file_id": str(file_id), "file_type": file.file_type},
        )
    active = repository.active_job(session, file.id)
    if active is not None:
        raise ConflictError(
            "该文件已有运行中的页面准备任务",
            details={"job_id": str(active.id), "status": active.status},
        )

    data = get_storage().read(file.storage_key)
    inspection = inspect_pdf(data, threshold=_threshold())
    job = repository.create_job(
        session,
        file_id=file.id,
        route=inspection.route,
        total_pages=inspection.page_count,
        image_coverage=inspection.image_coverage,
    )
    session.commit()
    session.refresh(job)
    _executor.submit(_submit_job, job.id)
    return job


def _submit_job(job_id: uuid.UUID) -> None:
    try:
        run_job(job_id)
    except Exception:  # noqa: BLE001 - 后台线程必须留日志，不能静默
        logger.exception("ocr job %s crashed", job_id)


def latest_job(session: Session, file_id: uuid.UUID) -> OcrJob | None:
    file_service.get_file(session, file_id)
    return repository.latest_job(session, file_id)


def page_source_counts(
    session: Session, file_id: uuid.UUID
) -> tuple[int, int]:
    return repository.page_source_counts(session, file_id)


def list_pages(
    session: Session,
    file_id: uuid.UUID,
    *,
    offset: int = 0,
    limit: int = 50,
) -> tuple[int, list[FilePage]]:
    file_service.get_file(session, file_id)
    return (
        repository.count_pages(session, file_id),
        repository.list_pages(
            session, file_id, offset=offset, limit=limit
        ),
    )


def get_pages_text(session: Session, file_id: uuid.UUID) -> str | None:
    """有页级文本时返回按页拼接的文本；没有则 None。"""
    pages = repository.all_pages(session, file_id)
    if not pages:
        return None
    chunks: list[str] = []
    for page in pages:
        header = f"--- 第 {page.page_no} 页 ---"
        chunks.append(f"{header}\n{page.text}".rstrip())
    return "\n\n".join(chunks)


def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def run_job(
    job_id: uuid.UUID,
    *,
    client: VlmOcrClient | None = None,
    session_factory: sessionmaker[Session] | None = None,
) -> None:
    """同步执行任务；API 线程与测试都可调用。"""
    factory = session_factory or get_session_factory()
    with factory() as session:
        job = repository.get_job(session, job_id)
        if job is None:
            raise NotFoundError(
                "OCR 任务不存在", details={"job_id": str(job_id)}
            )
        if job.status not in ("pending", "running"):
            return

        owns_client = False
        doc: pymupdf.Document | None = None
        try:
            file = file_service.get_file(session, job.file_id)
            data = get_storage().read(file.storage_key)
            inspection = inspect_pdf(data, threshold=_threshold())
            routes = {
                page.page_no: page.route for page in inspection.pages
            }

            repository.delete_pages(session, file.id)
            repository.mark_started(session, job)
            session.commit()

            if any(
                route == ROUTE_OCR for route in routes.values()
            ) and client is None:
                client = VlmOcrClient(VlmOcrConfig.from_env())
                owns_client = True

            doc = pymupdf.open(stream=data, filetype="pdf")
            for page_no, page in enumerate(doc, start=1):
                page_route = routes.get(page_no, ROUTE_TEXT)
                if page_route == ROUTE_TEXT:
                    text = _normalize(page.get_text("text"))
                    source = "native"
                else:
                    assert client is not None
                    pixmap = page.get_pixmap(
                        dpi=_dpi(),
                        colorspace=pymupdf.csRGB,
                        alpha=False,
                    )
                    try:
                        text = _normalize(
                            client.recognize_page(
                                pixmap.tobytes("png"), page_no
                            )
                        )
                    finally:
                        pixmap = None
                    source = "ocr"

                repository.add_page(
                    session,
                    file_id=file.id,
                    page_no=page_no,
                    text=text,
                    text_source=source,
                )
                repository.mark_progress(session, job, page_no)
                session.commit()

            repository.mark_completed(session, job)
            session.commit()
        except Exception as exc:  # noqa: BLE001 - 失败必须落库并清理半成品
            session.rollback()
            message = getattr(exc, "message", None) or (
                f"{exc.__class__.__name__}: {exc}"
            )
            try:
                job = repository.get_job(session, job_id)
                if job is not None:
                    repository.delete_pages(session, job.file_id)
                    repository.mark_failed(session, job, str(message))
                    session.commit()
            except Exception:  # noqa: BLE001
                session.rollback()
                logger.exception(
                    "failed to mark ocr job %s as failed", job_id
                )
            logger.warning("ocr job %s failed: %s", job_id, message)
        finally:
            if doc is not None:
                doc.close()
            if owns_client and client is not None:
                client.close()


def recover_interrupted(session: Session) -> int:
    return repository.recover_interrupted_jobs(session)


def shutdown_worker() -> None:
    _executor.shutdown(wait=False, cancel_futures=True)
