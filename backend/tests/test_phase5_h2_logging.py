"""Phase 5 H2: request id propagation + sensitive-value redaction."""
from __future__ import annotations

import io
import logging

from fastapi.testclient import TestClient

from app.core.logging import RedactingFilter, redact


def test_redact_known_credential_patterns() -> None:
    text = (
        "api_key=sk-abcdefgh12345678 "
        "Authorization: Bearer abc.def.ghi "
        "access_token: topsecret"
    )
    redacted = redact(text)
    assert "sk-abcdefgh12345678" not in redacted
    assert "abc.def.ghi" not in redacted
    assert "topsecret" not in redacted
    assert "***" in redacted


def test_filter_injects_request_id_and_redacts_message() -> None:
    record = logging.LogRecord(
        "mousehole.test",
        logging.INFO,
        __file__,
        1,
        "provider key sk-abcdefgh12345678 failed",
        None,
        None,
    )
    assert RedactingFilter().filter(record) is True
    assert "sk-abcdefgh12345678" not in record.getMessage()
    assert getattr(record, "request_id", None) == "-"


def test_handler_output_is_redacted() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RedactingFilter())
    logger = logging.getLogger("mousehole.test.redaction")
    previous_handlers = logger.handlers
    previous_propagate = logger.propagate
    try:
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(logging.INFO)
        logger.info("api_key=sk-abcdefgh12345678")
        output = stream.getvalue()
        assert "sk-abcdefgh12345678" not in output
        assert "***" in output
    finally:
        logger.handlers = previous_handlers
        logger.propagate = previous_propagate


def test_request_id_header_is_returned(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    request_id = response.headers.get("X-Request-ID")
    assert request_id and len(request_id) >= 8
