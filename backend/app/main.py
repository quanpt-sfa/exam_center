"""FastAPI entrypoint for exam-sys-next greenfield API."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.core.config import get_settings, validate_runtime_configuration
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging
from app.core.request_context import install_request_context_middleware
from app.infrastructure.database.pool import close_pool, initialize_pool


settings = get_settings()
validate_runtime_configuration()
configure_logging()


@asynccontextmanager
async def _lifespan(_: FastAPI):
    try:
        initialize_pool()
    except Exception:
        # Keep API startup resilient; DB health endpoint reports availability.
        pass

    try:
        yield
    finally:
        close_pool()

app = FastAPI(
    title="Exam Sys Next API",
    version=settings.app_version,
    lifespan=_lifespan,
)

install_error_handlers(app)
install_request_context_middleware(app)

if settings.cors_allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(v1_router, prefix=settings.api_prefix)
