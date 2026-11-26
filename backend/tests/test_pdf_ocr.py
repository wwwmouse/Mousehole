"""PDF 路由与 OCR 编排测试（不依赖真实 VLM）。"""

from __future__ import annotations

import json

import httpx
import pymupdf
import pytest

from app.modules.document.ocr_service import process_pdf
from app.modules.document.pdf_router import ROUTE_OCR, ROUTE_TEXT, inspect_pdf
from app.modules.document.vlm_ocr import VlmOcrClient, VlmOcrConfig
from app.shared.exceptions import FileParseError, UnprocessableError


def _png_bytes() -> bytes:
    pixmap = pymupdf.Pixmap(
        pymupdf.csRGB, pymupdf.IRect(0, 0, 8, 8), False
    )
    pixmap.clear_with(255)
    return pixmap.tobytes("png")


PNG_1PX = _png_bytes()


def _text_pdf(text: str = "Hello OCR") -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=320, height=240)
    page.insert_text((40, 80), text, fontsize=16)
    data = doc.tobytes()
    doc.close()
    return data


def _image_pdf(pages: int = 1) -> bytes:
    doc = pymupdf.open()
    for _ in range(pages):
        page = doc.new_page(width=320, height=240)
        page.insert_image(page.rect, stream=PNG_1PX)
    data = doc.tobytes()
    doc.close()
    return data


def _mixed_pdf() -> bytes:
    doc = pymupdf.open()
    text_page = doc.new_page(width=320, height=240)
    text_page.insert_text((40, 80), "native page", fontsize=16)
    image_page = doc.new_page(width=320, height=240)
    image_page.insert_image(image_page.rect, stream=PNG_1PX)
    data = doc.tobytes()
    doc.close()
    return data


class _FakeVlm:
    def __init__(self) -> None:
        self.pages: list[int] = []

    def recognize_page(self, image_png: bytes, page_no: int) -> str:
        assert image_png.startswith(b"\x89PNG")
        self.pages.append(page_no)
        return f"OCR 第 {page_no} 页"


def test_inspect_routes_text_pdf_to_text_layer() -> None:
    inspection = inspect_pdf(_text_pdf())
    assert inspection.page_count == 1
    assert inspection.route == ROUTE_TEXT
    assert inspection.text_chars > 0


def test_inspect_routes_image_pdf_to_ocr() -> None:
    inspection = inspect_pdf(_image_pdf())
    assert inspection.route == ROUTE_OCR
    assert inspection.pages[0].route == ROUTE_OCR
    assert inspection.image_coverage >= 70


def test_mixed_pdf_routes_pages_independently() -> None:
    inspection = inspect_pdf(_mixed_pdf())
    assert inspection.route == "mixed"
    assert inspection.pages[0].route == ROUTE_TEXT
    assert inspection.pages[1].route == ROUTE_OCR


def test_mixed_pdf_merges_native_and_vlm_pages_in_order() -> None:
    fake = _FakeVlm()
    result = process_pdf(
        _mixed_pdf(),
        filename="mixed.pdf",
        dpi=72,
        client=fake,  # type: ignore[arg-type]
    )
    assert result.route == "mixed"
    assert [page.source for page in result.pages] == ["native", "vlm"]
    assert "native page" in result.pages[0].text
    assert "OCR 第 2 页" in result.pages[1].text
    assert fake.pages == [2]


def test_text_route_extracts_native_text() -> None:
    result = process_pdf(_text_pdf("native text"), filename="text.pdf")
    assert result.route == ROUTE_TEXT
    assert result.pages[0].source == "native"
    assert "native text" in result.pages[0].text


def test_ocr_route_renders_and_calls_vlm() -> None:
    fake = _FakeVlm()
    result = process_pdf(
        _image_pdf(pages=2),
        filename="scan.pdf",
        dpi=72,
        limit=2,
        client=fake,  # type: ignore[arg-type]
    )
    assert result.route == ROUTE_OCR
    assert result.processed_pages == 2
    assert [page.source for page in result.pages] == ["vlm", "vlm"]
    assert fake.pages == [1, 2]
    assert "OCR 第 1 页" in result.pages[0].text


def test_ocr_route_requires_client() -> None:
    with pytest.raises(UnprocessableError, match="扫描页"):
        process_pdf(_image_pdf(), filename="scan.pdf")


def test_invalid_pdf_raises_parse_error() -> None:
    with pytest.raises(FileParseError):
        inspect_pdf(b"definitely not a pdf")


def test_vlm_client_openai_payload_and_content_parsing() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["json"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": "```markdown\n第一页文字\n```"}}
                ]
            },
        )

    config = VlmOcrConfig(
        base_url="http://localhost:11434/v1",
        model="qwen3-vl:4b",
        api_key="ollama",
    )
    client = VlmOcrClient(
        config, transport=httpx.MockTransport(handler)
    )
    try:
        text = client.recognize_page(PNG_1PX, 1)
    finally:
        client.close()

    assert text == "第一页文字"
    assert captured["url"] == "http://localhost:11434/v1/chat/completions"
    content = captured["json"]["messages"][0]["content"]
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert captured["json"]["model"] == "qwen3-vl:4b"
