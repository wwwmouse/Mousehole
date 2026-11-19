from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.modules.document.parsers import parse_pdf, parse_text
from app.modules.document.service import extract_text
from app.shared.exceptions import FileParseError


def build_minimal_pdf(text: str = "Hello PDF") -> bytes:
    """Build a minimal single-page PDF whose text pypdf can extract.

    Constructed by hand (no external PDF writer) so the test has no extra
    dependency; the xref table is computed from the real object offsets.
    """
    content = f"BT /F1 24 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref_offset = len(out)
    size = len(objects) + 1
    out += f"xref\n0 {size}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += (
        f"trailer\n<< /Size {size} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode("ascii")
    return bytes(out)


def test_parse_pdf_extracts_text() -> None:
    text = parse_pdf(build_minimal_pdf("Hello PDF"))
    assert "Hello PDF" in text


def test_parse_pdf_invalid_bytes_raises_file_parse_error() -> None:
    with pytest.raises(FileParseError):
        parse_pdf(b"this is definitely not a pdf")


def test_parse_pdf_without_text_raises() -> None:
    with pytest.raises(FileParseError, match="PDF 中未提取到文本"):
        parse_pdf(build_minimal_pdf(""))


def test_parse_text_normalizes_newlines_and_blank_lines() -> None:
    raw = "# Title\r\n\r\n\r\nBody   \r\nEnd\r\n".encode("utf-8")
    assert parse_text(raw) == "# Title\n\nBody\nEnd"


def test_parse_text_supports_utf8_sig() -> None:
    assert parse_text("héllo".encode("utf-8-sig")) == "héllo"


def test_parse_text_supports_utf16_with_bom() -> None:
    assert parse_text("中文资料".encode("utf-16")) == "中文资料"


def test_parse_text_supports_gb18030() -> None:
    assert parse_text("中文资料".encode("gb18030")) == "中文资料"


def test_extract_text_dispatches_on_extension() -> None:
    assert extract_text("md", b"# hi") == "# hi"
    assert extract_text(".markdown", b"# hi") == "# hi"
    assert extract_text("txt", b"plain text") == "plain text"
    assert "Hello PDF" in extract_text("pdf", build_minimal_pdf("Hello PDF"))


def test_extract_text_rejects_unknown_type() -> None:
    with pytest.raises(FileParseError) as excinfo:
        extract_text("docx", b"PK\x03\x04")
    assert excinfo.value.status_code == 422
    assert "不支持" in excinfo.value.message


def test_extract_text_never_returns_empty_string() -> None:
    with pytest.raises(FileParseError):
        extract_text("txt", b"")
    with pytest.raises(FileParseError):
        extract_text("txt", b"   \n\n   ")


def test_upload_pdf_and_read_extracted_content(client: TestClient) -> None:
    pdf = build_minimal_pdf("Hello PDF")
    uploaded = client.post(
        "/api/v1/files", files={"file": ("paper.pdf", pdf, "application/pdf")}
    )
    assert uploaded.status_code == 201, uploaded.text
    body = uploaded.json()
    assert body["file_type"] == "pdf"
    assert body["mime_type"] == "application/pdf"

    content = client.get(f"/api/v1/files/{body['id']}/content")
    assert content.status_code == 200, content.text
    payload = content.json()
    assert "Hello PDF" in payload["text"]
    assert payload["truncated"] is False


def test_upload_markdown_content_is_cleaned(client: TestClient) -> None:
    uploaded = client.post(
        "/api/v1/files",
        files={"file": ("notes.md", b"# Title\r\n\r\n\r\nBody   \r\n", "text/markdown")},
    )
    assert uploaded.status_code == 201, uploaded.text
    content = client.get(f"/api/v1/files/{uploaded.json()['id']}/content")
    assert content.status_code == 200, content.text
    assert content.json()["text"] == "# Title\n\nBody"


def test_upload_gb18030_txt_content(client: TestClient) -> None:
    uploaded = client.post(
        "/api/v1/files",
        files={"file": ("notes.txt", "中文资料".encode("gb18030"), "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    content = client.get(f"/api/v1/files/{uploaded.json()['id']}/content")
    assert content.status_code == 200, content.text
    assert content.json()["text"] == "中文资料"
