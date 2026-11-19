"""Document parsers for the MVP file types: PDF, Markdown and TXT.

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
    """Extract text from a PDF, page by page."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency is in requirements
        raise FileParseError("缺少 PDF 解析依赖 pypdf") from exc

    try:
        reader = PdfReader(BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages).strip()
    except FileParseError:
        raise
    except Exception as exc:  # pypdf raises many exception types for bad input
        raise FileParseError(f"PDF 解析失败：{exc}") from exc

    if not text:
        raise FileParseError("PDF 中未提取到文本")
    return text


def parse_text(data: bytes) -> str:
    """Decode and clean a plain text file."""
    return _normalize_text(_decode_text(data))


def parse_markdown(data: bytes) -> str:
    """Markdown is text; the MVP does not strip markup."""
    return parse_text(data)
