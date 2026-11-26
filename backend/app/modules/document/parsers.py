"""Document parsers for supported reference formats (PDF/Markdown/TXT plus
JSON/YAML/CSV/HTML/CSS text assets).

Parsers are intentionally small and side-effect free. They receive raw bytes and
return cleaned text; they never touch the database or storage layer.

Failure is always explicit: corrupt or empty documents raise FileParseError so a
caller can never mistake an empty string for successfully extracted content.
"""

from __future__ import annotations

import re
from io import BytesIO

from app.shared.exceptions import FileParseError

_MULTI_BLANK_LINE = re.compile(r"\n{3,}")


def _normalize_text(text: str) -> str:
    """Normalize newlines, strip trailing whitespace and squeeze blank lines."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = _MULTI_BLANK_LINE.sub("\n\n", text)
    return text.strip("\n")


def _decode_text(data: bytes) -> str:
    """Decode bytes using the encodings supported by the MVP.

    Order follows the product contract (utf-8-sig, utf-16, gb18030, latin-1).
    utf-16 is only attempted when a BOM is present, otherwise even-length
    non-UTF-8 input (for example GB18030) would be silently mis-decoded as
    UTF-16 before gb18030 gets a chance.
    """
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return data.decode("utf-16")
        except UnicodeDecodeError:
            pass
    try:
        return data.decode("gb18030")
    except UnicodeDecodeError:
        pass
    return data.decode("latin-1")


def parse_pdf(data: bytes) -> str:
    """Extract text from a PDF, page by page.

    PyMuPDF is the primary parser: it handles malformed xref tables and
    Chinese font encodings better than pypdf for real-world handbooks.
    pypdf remains a fallback only when PyMuPDF cannot open the file.
    """
    pages: list[str] = []
    page_count = 0
    try:
        import pymupdf

        doc = pymupdf.open(stream=data, filetype="pdf")
        try:
            if doc.needs_pass:
                raise FileParseError("PDF 已加密，当前不支持带密码读取")
            page_count = doc.page_count
            pages = [page.get_text("text") or "" for page in doc]
        finally:
            doc.close()
    except FileParseError:
        raise
    except Exception:
        # 最后再尝试 pypdf；某些极端文件仍可能只被其中一个库接受。
        try:
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(data))
            pages = [page.extract_text() or "" for page in reader.pages]
            page_count = len(pages)
        except FileParseError:
            raise
        except Exception as exc:
            raise FileParseError(f"PDF 解析失败：{exc}") from exc

    text = "\n".join(pages).strip()

    # 扫描版/图片型 PDF 通常只有封面等零星文字，正文没有文本层。
    # 明确失败，避免把几百个空白字符当成“解析成功”而让预览/对话一片空白。
    if page_count >= 3 and len(text) < 10 * page_count:
        raise FileParseError(
            f"该 PDF 可能是扫描版/图片型：{page_count} 页仅提取到 {len(text)} 个字符，"
            "没有可用文本层。当前不支持 OCR；请上传可复制文字的 PDF，"
            "或使用原始页面预览。"
        )

    if not text:
        raise FileParseError("PDF 中未提取到文本")
    return text


def parse_text(data: bytes) -> str:
    """Decode and clean a plain text file."""
    return _normalize_text(_decode_text(data))


def parse_markdown(data: bytes) -> str:
    """Markdown is text; the MVP does not strip markup."""
    return parse_text(data)
