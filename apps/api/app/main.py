"""FastAPI application factory."""
from __future__ import annotations

import importlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.router import api_router
from app.core.body_limit import BodyLimitMiddleware
from app.core.config import get_settings
from app.core.error_handlers import install_error_handlers
from app.core.logging import configure_logging
from app.core.rate_limit_middleware import GlobalRateLimitMiddleware
from app.core.request_context import RequestIdMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Resource startup/shutdown hook.

    Only releases SQLAlchemy engine pools on shutdown. This is NOT a
    full graceful drain: in-flight HTTP requests and worker jobs are
    the process manager's responsibility.
    """
    logger.info("app_startup")
    try:
        yield
    finally:
        logger.info("app_shutdown")
        _dispose("main", "app.db.session", "engine")
        _dispose("health", "app.db.session", "health_engine")


def _dispose(label: str, module: str, attr: str) -> None:
    try:
        eng = getattr(importlib.import_module(module), attr)
        eng.dispose()
    except Exception:
        logger.exception("engine_dispose_failed label=%s", label)


def create_app() -> FastAPI:
    settings = get_settings()

    level = settings.log_level or (
        "DEBUG" if settings.debug else "INFO"
    )
    configure_logging(level, fmt=settings.log_format)

    app = FastAPI(
        title=settings.project_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=_lifespan,
    )

    # ------------------------------------------------------------------
    # Middleware composition. add_middleware PREPENDS; the last added is
    # the OUTERMOST layer. Execution order (outer → inner):
    #
    #   RequestId
    #     CORS
    #       TrustedHost
    #         BodyLimit
    #           GlobalRateLimit
    #             FastAPI router
    #
    # Rationale and consequences:
    #   * RequestId outermost — every error path carries an ID.
    #   * CORS outside short-circuit layers so 400/413/429 responses
    #     still carry Access-Control-* headers.
    #   * TrustedHost before size/rate work.
    #   * BodyLimit runs BEFORE GlobalRateLimit. Declared oversized
    #     requests (Content-Length > max_request_bytes) are rejected
    #     without consuming any global rate budget.
    #   * For streaming/chunked requests with no Content-Length, the
    #     size is unknown when GlobalRateLimit runs. A later streaming
    #     overflow may therefore consume one unit of the global rate
    #     budget before the eventual 413 is produced. This is
    #     acceptable: it avoids buffering the entire body just to
    #     decide whether the request should be rate-accounted.
    # ------------------------------------------------------------------
    if (
        settings.rate_limit_enabled
        and settings.rate_limit_global_per_minute > 0
    ):
        app.add_middleware(
            GlobalRateLimitMiddleware,
            limit_per_minute=settings.rate_limit_global_per_minute,
            trusted_proxies_raw=settings.trusted_proxies,
        )

    if settings.max_request_bytes > 0:
        app.add_middleware(
            BodyLimitMiddleware,
            max_bytes=settings.max_request_bytes,
        )

    trusted = settings.trusted_hosts_list
    if trusted and trusted != ["*"]:
        app.add_middleware(
            TrustedHostMiddleware, allowed_hosts=trusted
        )

    cors_origins = settings.cors_origins_list
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=settings.cors_allow_credentials,
            allow_methods=settings.cors_allowed_methods_list,
            allow_headers=settings.cors_allowed_headers_list,
            expose_headers=settings.cors_exposed_headers_list,
        )

    app.add_middleware(
        RequestIdMiddleware,
        header_name=settings.request_id_header,
        accept_incoming=settings.request_id_accept_incoming,
    )

    install_error_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
