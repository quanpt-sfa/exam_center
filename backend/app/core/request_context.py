"""Request context helpers and request-id middleware."""

from __future__ import annotations

from contextvars import ContextVar
from uuid import uuid4

from fastapi import FastAPI, Request


REQUEST_ID_HEADER = "X-Request-ID"
_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id(request: Request | None = None) -> str | None:
    """Return request ID from request state or context variable."""

    if request is not None:
        state_request_id = getattr(request.state, "request_id", None)
        if state_request_id:
            return str(state_request_id)
    return _request_id_ctx.get()


def install_request_context_middleware(app: FastAPI) -> None:
    """Install middleware that propagates X-Request-ID through request lifecycle."""

    @app.middleware("http")
    async def _request_id_middleware(request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid4())
        token = _request_id_ctx.set(request_id)
        request.state.request_id = request_id

        try:
            response = await call_next(request)
        finally:
            _request_id_ctx.reset(token)

        response.headers[REQUEST_ID_HEADER] = request_id
        return response
