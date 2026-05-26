"""Safety guard for TEXTBOX_SQL sandbox DSN isolation from persistence DB."""

from __future__ import annotations

import os
from typing import Any

from psycopg.conninfo import conninfo_to_dict
from psycopg.conninfo import make_conninfo

from worker_runtime.db_env import required_postgres_db_name


def build_app_db_dsn_from_env() -> str:
    """Build app persistence DSN from POSTGRES_* environment variables."""

    password = os.getenv("POSTGRES_PASSWORD")
    if password in {None, ""}:
        password = os.getenv("PGPASSWORD")

    params = {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": os.getenv("POSTGRES_PORT", "5432"),
        "dbname": required_postgres_db_name(),
        "user": os.getenv("POSTGRES_USER", "exam_sys_app"),
        "sslmode": os.getenv("POSTGRES_SSLMODE", "prefer"),
        "connect_timeout": os.getenv("POSTGRES_CONNECT_TIMEOUT", "3"),
    }
    if password:
        params["password"] = password

    sanitized = {
        str(k): str(v)
        for k, v in params.items()
        if v is not None and str(v).strip() != ""
    }
    return make_conninfo("", **sanitized)


def validate_textbox_sql_executor_dsn(
    executor_dsn: str | None,
    app_dsn: str | None,
    *,
    allow_app_db_for_tests: bool = False,
) -> dict[str, Any]:
    """Validate sandbox DSN safety against app persistence DSN equivalence."""

    allowed_schemas = _parse_allowed_schemas(os.getenv("TEXTBOX_SQL_ALLOWED_SCHEMAS"))
    result = {
        "is_valid": True,
        "reason_code": "ok",
        "message": "TEXTBOX_SQL executor DSN validation passed.",
        "warnings": [],
        "allowed_schemas": allowed_schemas,
    }

    executor_raw = str(executor_dsn).strip() if executor_dsn else ""
    app_raw = str(app_dsn).strip() if app_dsn else ""

    if not executor_raw:
        result["reason_code"] = "executor_dsn_missing"
        result["message"] = (
            "TEXTBOX_SQL_EXECUTOR_DSN is not configured; execution remains disabled and "
            "queries return controlled SQL_RUNTIME_ERROR without fallback to app DB."
        )
        result["warnings"].append(
            {
                "reason_code": "executor_dsn_missing",
                "message": result["message"],
            }
        )
        return result

    parsed_executor = _parse_identity(executor_raw)
    if parsed_executor.get("error"):
        return {
            **result,
            "is_valid": False,
            "reason_code": "executor_dsn_invalid",
            "message": "TEXTBOX_SQL_EXECUTOR_DSN is invalid and cannot be parsed safely.",
            "warnings": [],
        }

    if not app_raw:
        result["reason_code"] = "app_dsn_missing"
        result["message"] = "App persistence DSN is unavailable; equivalence check skipped."
        result["warnings"].append(
            {
                "reason_code": "app_dsn_missing",
                "message": result["message"],
            }
        )
        return result

    parsed_app = _parse_identity(app_raw)
    if parsed_app.get("error"):
        return {
            **result,
            "is_valid": False,
            "reason_code": "app_dsn_invalid",
            "message": "Application persistence DSN is invalid; cannot perform safety equivalence check.",
            "warnings": [],
        }

    executor_identity = parsed_executor["identity"]
    app_identity = parsed_app["identity"]

    if executor_identity == app_identity:
        summary = (
            "Executor DSN matches application persistence DB identity "
            f"({_identity_summary(executor_identity)})."
        )
        if allow_app_db_for_tests:
            result["reason_code"] = "executor_dsn_matches_app_db_test_override"
            result["message"] = summary + " Allowed by explicit test-only override."
            result["warnings"].append(
                {
                    "reason_code": "executor_dsn_matches_app_db_test_override",
                    "message": result["message"],
                }
            )
            return result

        return {
            **result,
            "is_valid": False,
            "reason_code": "executor_dsn_matches_app_db",
            "message": summary,
            "warnings": [],
        }

    if _same_database_different_user(executor_identity, app_identity):
        warning = (
            "Executor DSN points to same host/port/dbname as app DB but with a different user "
            f"(executor={_identity_summary(executor_identity)} app={_identity_summary(app_identity)})."
        )
        result["reason_code"] = "ok_with_warnings"
        result["warnings"].append(
            {
                "reason_code": "executor_dsn_same_database_different_user",
                "message": warning,
            }
        )

    return result


def _parse_allowed_schemas(raw: str | None) -> list[str]:
    if raw is None:
        return []
    parsed: list[str] = []
    for token in str(raw).split(","):
        clean = token.strip()
        if clean and clean not in parsed:
            parsed.append(clean)
    return parsed


def _parse_identity(dsn: str) -> dict[str, Any]:
    try:
        info = conninfo_to_dict(str(dsn))
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "identity": None}

    host = str(info.get("host") or info.get("hostaddr") or "localhost").strip().lower()
    port = str(info.get("port") or "5432").strip()

    dbname = str(info.get("dbname") or info.get("database") or info.get("user") or "").strip().lower()
    user = str(info.get("user") or "").strip().lower()
    sslmode = str(info.get("sslmode") or "prefer").strip().lower()

    identity = {
        "host": host,
        "port": port,
        "dbname": dbname,
        "user": user,
        "sslmode": sslmode,
    }
    return {"error": None, "identity": identity}


def _identity_summary(identity: dict[str, str]) -> str:
    return (
        f"host={identity.get('host') or '<empty>'} "
        f"port={identity.get('port') or '<empty>'} "
        f"dbname={identity.get('dbname') or '<empty>'} "
        f"user={identity.get('user') or '<empty>'} "
        f"sslmode={identity.get('sslmode') or '<empty>'}"
    )


def _same_database_different_user(executor_identity: dict[str, str], app_identity: dict[str, str]) -> bool:
    return (
        executor_identity.get("host") == app_identity.get("host")
        and executor_identity.get("port") == app_identity.get("port")
        and executor_identity.get("dbname") == app_identity.get("dbname")
        and executor_identity.get("user") != app_identity.get("user")
    )
