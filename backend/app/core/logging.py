"""Logging setup, request-id propagation and sensitive-data redaction (Phase 5 H2).

Rules (AGENTS.md §4.7): API keys, full file contents and full prompts must never
reach logs. This module provides a single place for stdlib logging configuration
and a best-effort redaction filter for the values we *can* detect by pattern.
"""
from __future__ import annotations

import logging
import re
import uuid
from contextvars import ContextVar
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings

REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="-")

_LOG_FORMAT = (
    "%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Patterns are deliberately conservative: they must never make a failure
# unreadable, only strip credential-like values.
_SENSITIVE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"sk-[A-Za-z0-9_\-]{8,}"), "sk-***"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE), "Bearer ***"),
    (
        re.compile(
            r"(?i)(api[_-]?key|authorization|access[_-]?token)\s*([=:])\s*[^\s,;\"']+"
        ),
        r"\1\2***",
    ),
)

_HANDLER_MARK = "_mousehole_handler"


def redact(text: str) -> str:
    """Return *text* with recognizable credentials replaced by `***`."""
    if not text:
        return text
    result = text
    for pattern, replacement in _SENSITIVE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


class RedactingFilter(logging.Filter):
    """Inject request_id and redact sensitive values in the final message."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = REQUEST_ID.get()
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - broken format args must not crash logging
            return True
        redacted = redact(message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def _make_handler() -> logging.Handler:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
    )
    handler.addFilter(RedactingFilter())
    setattr(handler, _HANDLER_MARK, True)
    return handler


def configure_logging(level: str | None = None) -> None:
    """Configure root logging once; safe to call from create_app() repeatedly."""
    resolved = (level or get_settings().log_level or "INFO").upper()
    numeric = getattr(logging, resolved, logging.INFO)
    root = logging.getLogger()
    if not any(getattr(h, _HANDLER_MARK, False) for h in root.handlers):
        root.addHandler(_make_handler())
    root.setLevel(numeric)
    # Keep third-party noise below our own request/execution logs.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a request id to logs and expose it as X-Request-ID."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        token = REQUEST_ID.set(request_id)
        try:
            response = await call_next(request)
        finally:
            REQUEST_ID.reset(token)
        response.headers["X-Request-ID"] = request_id
        return response
