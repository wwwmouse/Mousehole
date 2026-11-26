"""PDF 路由：用图像覆盖率决定每页走 OCR 还是文本层。

规则（产品约定）：
    每页 α = 该页图片覆盖面积 / 该页面积 × 100
    α >= 70  → OCR 页：渲染页面为图片，交给 VLM 识别
    α <  70  → 文本页：直接用 PyMuPDF 读取文字层

文档可能混合两种页：逐页判定，最后按页码合并；
doc.route 为 text / ocr / mixed。
"""

from __future__ import annotations

from dataclasses import dataclass

import pymupdf

from app.shared.exceptions import FileParseError

ROUTE_TEXT = "text"
ROUTE_OCR = "ocr"
ROUTE_MIXED = "mixed"

# 产品阈值：图像覆盖率 >= 70% 的页视为扫描页。
DEFAULT_IMAGE_COVERAGE_THRESHOLD = 70.0


@dataclass(frozen=True)
class PageStats:
    page_no: int
    image_coverage: float  # 0–100
    text_chars: int
    route: str  # text | ocr


@dataclass(frozen=True)
class PdfInspection:
    page_count: int
    image_coverage: float  # 全文档 0–100
    text_chars: int
    threshold: float
    route: str  # text | ocr | mixed
    pages: tuple[PageStats, ...]


def _clip_rect(
    rect: pymupdf.Rect, page_rect: pymupdf.Rect
) -> tuple[float, float, float, float] | None:
    x0 = max(float(rect.x0), float(page_rect.x0))
    y0 = max(float(rect.y0), float(page_rect.y0))
    x1 = min(float(rect.x1), float(page_rect.x1))
    y1 = min(float(rect.y1), float(page_rect.y1))
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1, y1


def _union_area(rects: list[tuple[float, float, float, float]]) -> float:
    """求若干轴对齐矩形的并集面积，避免多张图片重叠时重复计数。"""
    if not rects:
        return 0.0
    xs = sorted({r[0] for r in rects} | {r[2] for r in rects})
    area = 0.0
    for left, right in zip(xs, xs[1:]):
        if right <= left:
            continue
        intervals = sorted(
            (r[1], r[3])
            for r in rects
            if r[0] < right and r[2] > left
        )
        merged: list[list[float]] = []
        for start, end in intervals:
            if not merged or start > merged[-1][1]:
                merged.append([start, end])
            else:
                merged[-1][1] = max(merged[-1][1], end)
        covered_height = sum(end - start for start, end in merged)
        area += (right - left) * covered_height
    return area


def _page_image_area(page: pymupdf.Page) -> float:
    page_rect = page.rect
    clipped: list[tuple[float, float, float, float]] = []
    seen_xrefs: set[int] = set()
    for image in page.get_images(full=True):
        xref = int(image[0])
        if xref in seen_xrefs:
            continue
        seen_xrefs.add(xref)
        try:
            rects = page.get_image_rects(xref)
        except Exception:  # noqa: BLE001 - 单张图片异常不应让整页失败
            continue
        for rect in rects:
            clipped_rect = _clip_rect(rect, page_rect)
            if clipped_rect is not None:
                clipped.append(clipped_rect)
    return _union_area(clipped)


def _open_pdf(data: bytes) -> pymupdf.Document:
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # PyMuPDF 对坏文件可能抛多种异常
        raise FileParseError(f"PDF 打开失败：{exc}") from exc
    if doc.needs_pass:
        doc.close()
        raise FileParseError("PDF 已加密，当前不支持带密码读取")
    if doc.page_count <= 0:
        doc.close()
        raise FileParseError("PDF 没有页面")
    return doc


def inspect_pdf(
    data: bytes,
    *,
    threshold: float = DEFAULT_IMAGE_COVERAGE_THRESHOLD,
) -> PdfInspection:
    """统计图片覆盖率并给出路由；覆盖率使用全文档面积加权。"""
    if not 0 <= threshold <= 100:
        raise ValueError("threshold 必须在 0–100 之间")

    doc = _open_pdf(data)
    try:
        page_stats: list[PageStats] = []
        total_page_area = 0.0
        total_image_area = 0.0
        total_text_chars = 0
        for page_no, page in enumerate(doc, start=1):
            page_area = float(page.rect.width * page.rect.height)
            image_area = _page_image_area(page)
            text_chars = len(page.get_text("text").strip())
            total_page_area += page_area
            total_image_area += image_area
            total_text_chars += text_chars
            coverage = (image_area / page_area * 100) if page_area > 0 else 0.0
            page_coverage = min(100.0, coverage)
            page_route = (
                ROUTE_OCR
                if page_coverage >= threshold
                else ROUTE_TEXT
            )
            page_stats.append(
                PageStats(
                    page_no=page_no,
                    image_coverage=page_coverage,
                    text_chars=text_chars,
                    route=page_route,
                )
            )

        image_coverage = (
            min(100.0, total_image_area / total_page_area * 100)
            if total_page_area > 0
            else 0.0
        )
        ocr_pages = sum(
            1 for page in page_stats if page.route == ROUTE_OCR
        )
        if ocr_pages == 0:
            route = ROUTE_TEXT
        elif ocr_pages == len(page_stats):
            route = ROUTE_OCR
        else:
            route = ROUTE_MIXED
        return PdfInspection(
            page_count=doc.page_count,
            image_coverage=round(image_coverage, 2),
            text_chars=total_text_chars,
            threshold=threshold,
            route=route,
            pages=tuple(page_stats),
        )
    finally:
        doc.close()
