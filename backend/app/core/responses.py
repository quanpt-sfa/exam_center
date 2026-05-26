"""Response helpers for API success and error contracts."""

from __future__ import annotations

from typing import Any


def success_response(data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a consistent success envelope."""

    return {
        "ok": True,
        "data": data or {},
        "error": None,
    }


def error_response(
    *,
    code: str,
    message: str,
    details: dict[str, Any] | None,
    request_id: str | None,
) -> dict[str, Any]:
    """Return the required error payload contract."""

    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request_id,
        }
    }
