"""PDF OCR 编排层：路由 -> 文本层 / 渲染 -> VLM -> 页级结果。

本模块不依赖数据库、API 或任务队列，先把“路由 + OCR”做成可测试的纯服务；
后续接入 File/Job/Chat 时再接持久化与进度。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pymupdf

from app.modules.document.pdf_router import (
    ROUTE_OCR,
    ROUTE_TEXT,
    inspect_pdf,
)
from app.modules.document.vlm_ocr import VlmOcrClient
from app.shared.exceptions import FileParseError, UnprocessableError

ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class OcrPage:
    page_no: int
    text: str
    source: str  # native | vlm


@dataclass(frozen=True)
class PdfOcrResult:
    filename: str
    route: str
    page_count: int
    processed_pages: int
    image_coverage: float
    dpi: int
    pages: tuple[OcrPage, ...]

    @property
    def truncated(self) -> bool:
        return self.processed_pages < self.page_count

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "route": self.route,
            "page_count": self.page_count,
            "processed_pages": self.processed_pages,
            "truncated": self.truncated,
            "image_coverage": self.image_coverage,
            "dpi": self.dpi,
            "pages": [
                {
                    "page_no": page.page_no,
                    "source": page.source,
                    "text": page.text,
                }
                for page in self.pages
            ],
        }

    def to_markdown(self) -> str:
        chunks = [
            f"## 第 {page.page_no} 页\n\n{page.text}".rstrip()
            for page in self.pages
        ]
        return "\n\n---\n\n".join(chunks)


def _open_pdf(data: bytes) -> pymupdf.Document:
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 - 统一转成显式解析错误
        raise FileParseError(f"PDF 打开失败：{exc}") from exc
    if doc.needs_pass:
        doc.close()
        raise FileParseError("PDF 已加密，当前不支持带密码读取")
    if doc.page_count <= 0:
        doc.close()
        raise FileParseError("PDF 没有页面")
    return doc


def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def process_pdf(
    data: bytes,
    *,
    filename: str,
    threshold: float = 70.0,
    dpi: int = 200,
    limit: int | None = None,
    client: VlmOcrClient | None = None,
    progress: ProgressCallback | None = None,
) -> PdfOcrResult:
    """按图像覆盖率路由并提取页级文本。

    - text 路由：PyMuPDF 直接读取文字层；
    - ocr 路由：PyMuPDF 渲染页面为 PNG，逐页交给 VLM；
    - limit 仅用于抽样/测试，结果会标记 truncated。
    """
    if dpi < 72:
        raise ValueError("dpi 不能低于 72")
    if limit is not None and limit <= 0:
        raise ValueError("limit 必须大于 0")

    inspection = inspect_pdf(data, threshold=threshold)
    total = inspection.page_count
    if limit is not None:
        total = min(total, limit)

    page_routes = {
        page.page_no: page.route for page in inspection.pages
    }
    ocr_pages = [
        page_no
        for page_no in range(1, total + 1)
        if page_routes[page_no] == ROUTE_OCR
    ]
    if ocr_pages and client is None:
        raise UnprocessableError(
            "该 PDF 包含扫描页，需要配置 OCR VLM 后才能读取"
        )

    doc = _open_pdf(data)
    pages: list[OcrPage] = []
    try:
        for page_no, page in enumerate(doc, start=1):
            if page_no > total:
                break
            if progress is not None:
                progress(page_no, total)

            if page_routes[page_no] == ROUTE_TEXT:
                text = _normalize(page.get_text("text"))
                source = "native"
            else:
                assert client is not None
                pixmap = page.get_pixmap(
                    dpi=dpi,
                    colorspace=pymupdf.csRGB,
                    alpha=False,
                )
                try:
                    image_png = pixmap.tobytes("png")
                    text = _normalize(
                        client.recognize_page(image_png, page_no)
                    )
                finally:
                    pixmap = None
                source = "vlm"

            pages.append(
                OcrPage(page_no=page_no, text=text, source=source)
            )
    finally:
        doc.close()

    return PdfOcrResult(
        filename=filename,
        route=inspection.route,
        page_count=inspection.page_count,
        processed_pages=len(pages),
        image_coverage=inspection.image_coverage,
        dpi=dpi,
        pages=tuple(pages),
    )
