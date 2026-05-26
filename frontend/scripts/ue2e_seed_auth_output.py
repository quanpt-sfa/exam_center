#!/usr/bin/env python3
"""Pure helpers for UE2E seed-auth-principals token output policy."""

from __future__ import annotations

import re
from typing import Any
from typing import Mapping


REDACTED_TOKEN_VALUE = "<redacted>"
JWT_LIKE_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")


def _env_text(env: Mapping[str, str], key: str, fallback: str = "") -> str:
    return str(env.get(key, fallback)).strip()


def _is_true(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def machine_emit_allowed(env: Mapping[str, str]) -> bool:
    run_integration = _is_true(_env_text(env, "UE2E_RUN_INTEGRATION", "0"))
    auth_mode = _env_text(env, "UE2E_AUTH_MODE", "bearer").lower()
    return run_integration and auth_mode == "bearer"


def validate_emit_request(*, emit_tokens: bool, env: Mapping[str, str]) -> None:
    if not emit_tokens:
        return
    if machine_emit_allowed(env):
        return
    raise RuntimeError(
        "seed-auth-principals --emit-tokens requires UE2E_RUN_INTEGRATION=1 and UE2E_AUTH_MODE=bearer"
    )


def _principal_payload(principal: Mapping[str, Any], *, student_expected: bool) -> dict[str, Any]:
    student_id = principal.get("student_id")
    return {
        "username": str(principal["username"]),
        "user_id": int(principal["user_id"]),
        "person_id": int(principal["person_id"]),
        "student_id": (int(student_id) if student_expected and student_id is not None else None),
        "roles": list(principal["roles"]),
    }


def build_seed_auth_payload(*, principals: Mapping[str, Mapping[str, Any]], emit_tokens: bool) -> dict[str, Any]:
    admin = principals["admin"]
    owner = principals["owner"]
    non_owner = principals["non_owner"]

    if emit_tokens:
        token_output = "raw_machine_mode"
        tokens = {
            "admin_access_token": str(admin["access_token"]),
            "owner_access_token": str(owner["access_token"]),
            "non_owner_access_token": str(non_owner["access_token"]),
        }
    else:
        token_output = "redacted"
        tokens = {
            "admin_access_token": REDACTED_TOKEN_VALUE,
            "owner_access_token": REDACTED_TOKEN_VALUE,
            "non_owner_access_token": REDACTED_TOKEN_VALUE,
        }

    return {
        "scenario": "seed_auth_principals",
        "token_type": "bearer",
        "token_output": token_output,
        "principals": {
            "admin": _principal_payload(admin, student_expected=False),
            "owner": _principal_payload(owner, student_expected=True),
            "non_owner": _principal_payload(non_owner, student_expected=True),
        },
        "tokens": tokens,
    }
