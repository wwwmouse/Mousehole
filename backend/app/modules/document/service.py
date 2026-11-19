"""Document processing service: dispatch raw file bytes to the right parser."""

from __future__ import annotations

from app.modules.document.parsers import parse_markdown, parse_pdf, parse_text
from app.shared.exceptions import FileParseError

SUPPORTED_FILE_TYPES = ("pdf", "md", "markdown", "txt")

_PARSERS = {
    "pdf": parse_pdf,
    "md": parse_markdown,
    "markdown": parse_markdown,
    "txt": parse_text,
}


def normalize_file_type(file_type: str | None) -> str:
    """Return the canonical lowercase extension without a leading dot."""
    return (file_type or "").strip().lower().lstrip(".")


def extract_text(file_type: str | None, data: bytes) -> str:
    """Extract text for a supported file type.

    Unknown types and empty extraction raise FileParseError instead of
    silently returning an empty string.
    """
    parser = _PARSERS.get(normalize_file_type(file_type))
    if parser is None:
        raise FileParseError(
            f"不支持的文件类型：{file_type or '未知'}",
            details={"file_type": file_type, "supported": list(SUPPORTED_FILE_TYPES)},
        )
    try:
        text = parser(data)
    except FileParseError:
        raise
    except Exception as exc:
        raise FileParseError(f"文件解析失败：{exc}") from exc
    if not text or not text.strip():
        raise FileParseError("文件中未提取到文本")
    return text
