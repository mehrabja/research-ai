"""FastAPI application factory."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()

    configure_logging(
        "DEBUG" if settings.debug else "INFO"
    )

    app = FastAPI(
        title=settings.project_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    @app.exception_handler(AppError)
    async def _handle_app_error(
        _: Request,
        exc: AppError,
    ) -> JSONResponse:
        logger.warning(
            "AppError code=%s status=%s",
            exc.code,
            exc.status_code,
        )

        headers: dict[str, str] = {}

        if exc.status_code == 401:
            headers["WWW-Authenticate"] = "Bearer"

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
            headers=headers,
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(
        _: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception("Unhandled exception")

        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Internal server error.",
                }
            },
        )

    app.include_router(
        api_router,
        prefix=settings.api_prefix,
    )

    return app


app = create_app()
