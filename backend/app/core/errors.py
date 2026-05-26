"""Centralized API error handlers for exam-sys-next."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.permissions import PermissionDeniedError
from app.core.request_context import get_request_id
from app.core.responses import error_response


class ApiError(Exception):
    """Application-level API exception with explicit error contract fields."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


_SENSITIVE_DETAIL_TERMS = (
    "token",
    "refresh",
    "access",
    "password",
    "secret",
    "cookie",
    "authorization",
    "auth",
    "session",
    "jti",
    "header",
    "payload",
)


def _is_sensitive_detail_key(key: object) -> bool:
    normalized = str(key).strip().lower()
    return bool(normalized) and any(term in normalized for term in _SENSITIVE_DETAIL_TERMS)


def _normalize_error_details(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return _normalize_error_details(value.value)
    if isinstance(value, Mapping):
        normalized_map: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            if _is_sensitive_detail_key(raw_key):
                continue
            normalized_key = str(raw_key)
            normalized_value = _normalize_error_details(raw_value)
            normalized_map[normalized_key] = normalized_value
        return normalized_map
    if isinstance(value, list | tuple | set):
        return [_normalize_error_details(item) for item in value]
    return str(value)


def _error_headers(request_id: str | None) -> dict[str, str]:
    if not request_id:
        return {}
    return {"X-Request-ID": request_id}


def install_error_handlers(app: FastAPI) -> None:
    """Register API error handlers with a consistent error contract."""

    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = get_request_id(request)
        raw_errors = exc.errors()
        cleaned_errors = []
        for err in raw_errors:
            cleaned_err = dict(err)
            if "ctx" in cleaned_err and isinstance(cleaned_err["ctx"], dict):
                ctx = dict(cleaned_err["ctx"])
                for k, v in ctx.items():
                    if isinstance(v, Exception):
                        ctx[k] = str(v)
                cleaned_err["ctx"] = ctx
            cleaned_errors.append(cleaned_err)

        payload = error_response(
            code="validation_error",
            message="Request validation failed",
            details={"errors": cleaned_errors},
            request_id=request_id,
        )
        return JSONResponse(status_code=422, content=payload, headers=_error_headers(request_id))

    @app.exception_handler(PermissionDeniedError)
    async def _permission_denied_handler(request: Request, exc: PermissionDeniedError) -> JSONResponse:
        request_id = get_request_id(request)
        payload = error_response(
            code="permission_denied",
            message=str(exc),
            details={},
            request_id=request_id,
        )
        return JSONResponse(status_code=403, content=payload, headers=_error_headers(request_id))

    @app.exception_handler(ApiError)
    async def _api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        request_id = get_request_id(request)
        payload = error_response(
            code=exc.code,
            message=exc.message,
            details=_normalize_error_details(exc.details),
            request_id=request_id,
        )
        return JSONResponse(status_code=exc.status_code, content=payload, headers=_error_headers(request_id))

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = get_request_id(request)

        if exc.status_code == 404:
            payload = error_response(
                code="not_found",
                message="Resource not found",
                details={},
                request_id=request_id,
            )
        elif exc.status_code == 403:
            payload = error_response(
                code="permission_denied",
                message="Permission denied",
                details={},
                request_id=request_id,
            )
        elif exc.status_code == 401:
            payload = error_response(
                code="unauthorized",
                message="Authentication required",
                details={},
                request_id=request_id,
            )
        else:
            payload = error_response(
                code="http_error",
                message=str(exc.detail),
                details={},
                request_id=request_id,
            )

        return JSONResponse(status_code=exc.status_code, content=payload, headers=_error_headers(request_id))

    @app.exception_handler(Exception)
    async def _unexpected_exception_handler(request: Request, _: Exception) -> JSONResponse:
        request_id = get_request_id(request)
        payload = error_response(
            code="internal_error",
            message="Unexpected server error",
            details={},
            request_id=request_id,
        )
        return JSONResponse(status_code=500, content=payload, headers=_error_headers(request_id))
