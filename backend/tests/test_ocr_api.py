"""OCR API/job integration tests（不调用真实 VLM）。"""

from __future__ import annotations

import time
import uuid

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.modules.ocr import repository as ocr_repository
from app.modules.ocr import service as ocr_service


def _png_bytes() -> bytes:
    pixmap = pymupdf.Pixmap(
        pymupdf.csRGB, pymupdf.IRect(0, 0, 8, 8), False
    )
    pixmap.clear_with(255)
    return pixmap.tobytes("png")


def _text_pdf(text: str = "hello native") -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=320, height=240)
    page.insert_text((40, 80), text, fontsize=16)
    data = doc.tobytes()
    doc.close()
    return data


def _image_pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=320, height=240)
    page.insert_image(page.rect, stream=_png_bytes())
    data = doc.tobytes()
    doc.close()
    return data


class _FakeVlm:
    def recognize_page(self, image_png: bytes, page_no: int) -> str:
        assert image_png.startswith(b"\x89PNG")
        return f"扫描页 {page_no} 的文字"


def _upload_pdf(client: TestClient, name: str, data: bytes) -> str:
    response = client.post(
        "/api/v1/files",
        files={"file": (name, data, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _wait_job(
    client: TestClient, file_id: str, timeout: float = 3.0
) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/files/{file_id}/ocr")
        assert response.status_code == 200, response.text
        job = response.json()
        if job is not None and job["status"] in (
            "completed",
            "failed",
        ):
            return job
        time.sleep(0.02)
    raise AssertionError("OCR job did not settle in time")


def test_text_pdf_job_completes_and_serves_pages(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch,
) -> None:
    # API 创建的任务在后台线程执行，测试中让它使用内存库。
    monkeypatch.setattr(
        ocr_service, "get_session_factory", lambda: session_factory
    )
    file_id = _upload_pdf(client, "native.pdf", _text_pdf())

    started = client.post(f"/api/v1/files/{file_id}/ocr")
    assert started.status_code == 202, started.text
    job = _wait_job(client, file_id)
    assert job["status"] == "completed", job
    assert job["route"] == "text"
    assert job["processed_pages"] == 1
    assert job["native_pages"] == 1
    assert job["ocr_pages"] == 0
    assert job["current_page"] is None

    pages = client.get(f"/api/v1/files/{file_id}/pages")
    assert pages.status_code == 200
    body = pages.json()
    assert body["total"] == 1
    assert body["pages"][0]["text_source"] == "native"
    assert "hello native" in body["pages"][0]["text"]

    content = client.get(f"/api/v1/files/{file_id}/content")
    assert content.status_code == 200
    assert "hello native" in content.json()["text"]
    assert "第 1 页" in content.json()["text"]


def test_ocr_job_persists_vlm_pages(
    client: TestClient,
    db_session: Session,
    session_factory: sessionmaker[Session],
) -> None:
    file_id = _upload_pdf(client, "scan.pdf", _image_pdf())
    job = ocr_repository.create_job(
        db_session,
        file_id=uuid.UUID(file_id),
        route="ocr",
        total_pages=1,
        image_coverage=99.9,
    )
    db_session.commit()

    ocr_service.run_job(
        job.id,
        client=_FakeVlm(),  # type: ignore[arg-type]
        session_factory=session_factory,
    )

    refreshed = client.get(f"/api/v1/files/{file_id}/ocr")
    assert refreshed.status_code == 200
    assert refreshed.json()["status"] == "completed"
    pages = client.get(f"/api/v1/files/{file_id}/pages").json()
    assert pages["pages"][0]["text_source"] == "ocr"
    assert "扫描页 1" in pages["pages"][0]["text"]


def test_ocr_rejects_non_pdf(client: TestClient) -> None:
    uploaded = client.post(
        "/api/v1/files",
        files={"file": ("notes.md", b"# hello", "text/markdown")},
    ).json()
    response = client.post(f"/api/v1/files/{uploaded['id']}/ocr")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unprocessable"


def test_pages_unknown_file_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/files/{uuid.uuid4()}/pages")
    assert response.status_code == 404
