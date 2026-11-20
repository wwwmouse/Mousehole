from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for errors that map to explicit HTTP responses."""

    status_code = 400
    code = "bad_request"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class UnsupportedFileTypeError(AppError):
    status_code = 415
    code = "unsupported_file_type"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"


class UnprocessableError(AppError):
    status_code = 422
    code = "unprocessable"


class StorageError(AppError):
    status_code = 500
    code = "storage_error"


class FileParseError(AppError):
    status_code = 422
    code = "file_parse_error"


class ProviderNotConfiguredError(AppError):
    status_code = 422
    code = "provider_not_configured"


class ModelRequiredError(AppError):
    status_code = 422
    code = "model_required"


class ProviderError(AppError):
    status_code = 502
    code = "provider_error"

    def __init__(self, message: str, *, transient: bool = False, **kwargs) -> None:
        super().__init__(message, **kwargs)
        self.transient = transient
