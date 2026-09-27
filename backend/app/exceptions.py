"""Shared exception types and FastAPI-wide error handling."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for expected application errors.

    Subclasses may define class-level defaults (status_code/code/message) or
    override any of them per-instance with keyword arguments:
        raise AppError(status_code=422, code="unsupported_mode", message="...")
    Positional args are forwarded to Exception (e.g. NotFoundError("x"));
    the payload still comes from the class-level `message`.
    """

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"
    message: str = "An unexpected error occurred."

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args)
        if "status_code" in kwargs:
            self.status_code = int(kwargs["status_code"])  # type: ignore[arg-type]
        if "code" in kwargs:
            self.code = str(kwargs["code"])  # type: ignore[arg-type]
        if "message" in kwargs:
            self.message = str(kwargs["message"])  # type: ignore[arg-type]


class DatabaseUnavailableError(AppError):
    """Raised when a PostgreSQL connection cannot be established."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "database_unavailable"
    message = "Database is unavailable."


class NotFoundError(AppError):
    """Requested resource does not exist (HTTP 404)."""

    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "Resource not found."


class InvalidFileError(AppError):
    """Uploaded file failed validation (HTTP 400)."""

    status_code = status.HTTP_400_BAD_REQUEST
    code = "invalid_file"
    message = "The uploaded file is not supported."


class FileTooLargeError(AppError):
    """Uploaded file exceeds the configured size limit (HTTP 413)."""

    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    code = "file_too_large"
    message = "The uploaded file exceeds the allowed size."


class StorageError(AppError):
    """File could not be stored or retrieved (HTTP 500)."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "storage_error"
    message = "Document storage operation failed."


def _error_payload(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def register_exception_handlers(app: FastAPI) -> None:
    """Install consistent JSON error responses for the whole API."""

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(exc.code, exc.message),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_payload("validation_error", "Request validation failed."),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_payload("internal_error", "An unexpected error occurred."),
        )
