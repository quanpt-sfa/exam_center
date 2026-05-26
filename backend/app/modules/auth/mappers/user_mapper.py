"""Mapper utilities for auth user payloads."""

from __future__ import annotations


def to_auth_user_payload(user_row: dict, roles: list[str], permissions: list[str]) -> dict:
    """Map DB user row and role data to API-safe auth payload."""

    return {
        "user_id": int(user_row["user_id"]),
        "username": user_row.get("username"),
        "email": user_row.get("email_login"),
        "display_name": user_row.get("display_name"),
        "roles": roles,
        "permissions": permissions,
        "active": str(user_row.get("user_status", "")).upper() == "ACTIVE",
        "status": user_row.get("user_status"),
    }
