"""Structured FastAPI error handling (M36).

Coexists with existing ``AppError`` semantics and adds:

  * a single canonical error envelope with ``request_id``
  * safe ``HTTPException`` mapping (preserves ``detail``)
  * safe validation-error mapping (preserves ``detail``)
  * safe SQLAlchemy classification
  * safe handling of unexpected exceptions
  * ``Retry-After`` header + ``retry_after`` body field on 429

Envelope::

    {"error": {"code": ..., "message": ..., "request_id": ...}}
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import (
    IntegrityError,
    OperationalError,
    SQLAlchemyError,
)
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError
from app.core.request_context import get_request_id

logger = logging.getLogger(__name__)


def _envelope(code: str, message: str) -> dict[str, Any]:
    body: dict[str, Any] = {
        "error": {"code": code, "message": message}
    }
    rid = get_request_id()
    if rid:
        body["error"]["request_id"] = rid
    return body


def install_error_handlers(app: FastAPI) -> None:
    """Register M36 error handlers."""

    @app.exception_handler(AppError)
    async def _app_error(
        request: Request, exc: AppError
    ) -> JSONResponse:
        logger.warning(
            "app_error code=%s status=%s path=%s",
            exc.code,
            exc.status_code,
            request.url.path,
        )
        headers: dict[str, str] = {}
        if exc.status_code == 401:
            headers["WWW-Authenticate"] = "Bearer"

        body = _envelope(exc.code, exc.message)
        retry_after = getattr(exc, "retry_after", None)
        if exc.status_code == 429 and retry_after is not None:
            retry_after = max(1, int(retry_after))
            headers["Retry-After"] = str(retry_after)
            body["error"]["retry_after"] = retry_after

        return JSONResponse(
            status_code=exc.status_code,
            content=body,
            headers=headers,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        logger.info(
            "http_exception status=%s path=%s",
            exc.status_code,
            request.url.path,
        )
        detail = exc.detail
        message = (
            detail
            if isinstance(detail, str) and detail
            else "Request failed."
        )
        code = (
            "HTTP_ERROR"
            if exc.status_code >= 500
            else "REQUEST_ERROR"
        )
        body = _envelope(code, message)
        body["detail"] = jsonable_encoder(detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=body,
            headers=dict(exc.headers or {}),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.info(
            "validation_error path=%s", request.url.path
        )
        body = _envelope(
            "VALIDATION_ERROR", "Request validation failed."
        )
        errors = jsonable_encoder(exc.errors())
        body["detail"] = errors
        body["errors"] = errors
        return JSONResponse(status_code=422, content=body)

    @app.exception_handler(SQLAlchemyError)
    async def _db_error(
        request: Request, exc: SQLAlchemyError
    ) -> JSONResponse:
        logger.exception(
            "database_error path=%s", request.url.path
        )
        if isinstance(exc, OperationalError):
            code, status, message = (
                "DATABASE_UNAVAILABLE",
                503,
                "Database is unavailable.",
            )
        elif isinstance(exc, IntegrityError):
            code, status, message = (
                "DATA_INTEGRITY_ERROR",
                409,
                "Request conflicts with existing data.",
            )
        else:
            code, status, message = (
                "INTERNAL_ERROR",
                500,
                "Internal server error.",
            )
        return JSONResponse(
            status_code=status,
            content=_envelope(code, message),
        )

    @app.exception_handler(Exception)
    async def _unexpected(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(
            "unhandled_exception path=%s", request.url.path
        )
        return JSONResponse(
            status_code=500,
            content=_envelope(
                "INTERNAL_ERROR", "Internal server error."
            ),
        )


__all__ = ["install_error_handlers"]
