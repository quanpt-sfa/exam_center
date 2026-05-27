"""Safety guard for capture source DSN isolation from application persistence DB."""

from __future__ import annotations

import os
import re
from typing import Any

from psycopg.conninfo import conninfo_to_dict
from psycopg.conninfo import make_conninfo

from worker_runtime.db_env import required_postgres_db_name


def build_app_db_dsn_from_env() -> str:
    """Build application DB DSN from POSTGRES_* environment variables."""

    password = os.getenv("POSTGRES_PASSWORD") or os.getenv("PGPASSWORD")
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

    cleaned = {
        str(key): str(value)
        for key, value in params.items()
        if value is not None and str(value).strip() != ""
    }
    return make_conninfo("", **cleaned)


def parse_csv_env(raw: str | None) -> list[str]:
    if raw is None:
        return []

    parsed: list[str] = []
    for token in str(raw).split(","):
        value = token.strip()
        if value and value not in parsed:
            parsed.append(value)
    return parsed


def redact_sensitive_text(value: str | None) -> str:
    text = str(value or "")
    text = re.sub(r"(?i)(password\s*=\s*)([^\s;]+)", r"\1<redacted>", text)
    text = re.sub(r"(?i)(postgres(?:ql)?://[^:\s]+:)([^@\s]+)@", r"\1<redacted>@", text)
    return text


def _parse_identity(dsn: str) -> dict[str, Any]:
    try:
        info = conninfo_to_dict(str(dsn))
    except Exception as exc:  # noqa: BLE001
        return {"error": redact_sensitive_text(str(exc)), "identity": None}

    identity = {
        "host": str(info.get("host") or info.get("hostaddr") or "localhost").strip().lower(),
        "port": str(info.get("port") or "5432").strip(),
        "dbname": str(info.get("dbname") or info.get("database") or info.get("user") or "").strip().lower(),
        "user": str(info.get("user") or "").strip().lower(),
        "sslmode": str(info.get("sslmode") or "prefer").strip().lower(),
    }
    return {"error": None, "identity": identity}


def _identity_summary(identity: dict[str, str] | None) -> str:
    if not identity:
        return "host=<empty> port=<empty> dbname=<empty> user=<empty> sslmode=<empty>"
    return (
        f"host={identity.get('host') or '<empty>'} "
        f"port={identity.get('port') or '<empty>'} "
        f"dbname={identity.get('dbname') or '<empty>'} "
        f"user={identity.get('user') or '<empty>'} "
        f"sslmode={identity.get('sslmode') or '<empty>'}"
    )


def _is_equivalent_source_database(source_identity: dict[str, str], app_identity: dict[str, str]) -> bool:
    return (
        source_identity.get("host") == app_identity.get("host")
        and source_identity.get("port") == app_identity.get("port")
        and source_identity.get("dbname") == app_identity.get("dbname")
    )


def validate_capture_source_dsn(
    *,
    source_dsn: str | None,
    app_dsn: str | None,
    allow_app_db_for_tests: bool = False,
    allowed_schemas_raw: str | None = None,
    allowed_tables_raw: str | None = None,
) -> dict[str, Any]:
    """Validate capture source DSN isolation against app DB identity."""

    allowed_schemas = parse_csv_env(allowed_schemas_raw)
    allowed_tables = parse_csv_env(allowed_tables_raw)

    source_raw = str(source_dsn or "").strip()
    app_raw = str(app_dsn or "").strip()

    result: dict[str, Any] = {
        "is_valid": True,
        "reason_code": "ok",
        "message": "Capture source DSN validation passed.",
        "warnings": [],
        "allow_app_db_for_tests": bool(allow_app_db_for_tests),
        "allowed_schemas": allowed_schemas,
        "allowed_tables": allowed_tables,
        "source_dsn_redacted": redact_sensitive_text(source_raw),
        "app_dsn_redacted": redact_sensitive_text(app_raw),
        "source_identity_summary": None,
        "app_identity_summary": None,
        "source_matches_app_db": False,
    }

    if not source_raw:
        return {
            **result,
            "is_valid": False,
            "reason_code": "source_dsn_missing",
            "message": (
                "STUDENT_CAPTURE_SOURCE_DSN is required for capture route and missing DSN is fail-closed; "
                "no fallback to application DB DSN is allowed."
            ),
        }

    parsed_source = _parse_identity(source_raw)
    if parsed_source.get("error"):
        return {
            **result,
            "is_valid": False,
            "reason_code": "source_dsn_invalid",
            "message": "STUDENT_CAPTURE_SOURCE_DSN is invalid and cannot be parsed safely.",
            "warnings": [
                {
                    "reason_code": "source_dsn_invalid",
                    "message": str(parsed_source.get("error") or "invalid source dsn"),
                }
            ],
        }

    parsed_app = _parse_identity(app_raw)
    if parsed_app.get("error"):
        return {
            **result,
            "is_valid": False,
            "reason_code": "app_dsn_invalid",
            "message": "Application DB DSN is invalid; capture safety equivalence check cannot continue.",
            "warnings": [
                {
                    "reason_code": "app_dsn_invalid",
                    "message": str(parsed_app.get("error") or "invalid app dsn"),
                }
            ],
        }

    source_identity = parsed_source.get("identity") or {}
    app_identity = parsed_app.get("identity") or {}
    source_summary = _identity_summary(source_identity)
    app_summary = _identity_summary(app_identity)
    equivalent = _is_equivalent_source_database(source_identity, app_identity)

    if equivalent and not allow_app_db_for_tests:
        return {
            **result,
            "is_valid": False,
            "reason_code": "source_dsn_matches_app_db",
            "message": (
                "Capture source DSN points to the same DB endpoint as application persistence DB; "
                "blocked in production."
            ),
            "source_identity_summary": source_summary,
            "app_identity_summary": app_summary,
            "source_matches_app_db": True,
        }

    if equivalent and allow_app_db_for_tests:
        return {
            **result,
            "is_valid": True,
            "reason_code": "source_dsn_matches_app_db_test_override",
            "message": "Capture source DSN matches app DB endpoint but is allowed by explicit test override.",
            "warnings": [
                {
                    "reason_code": "source_dsn_matches_app_db_test_override",
                    "message": "App DB equivalence accepted only because test override is enabled.",
                }
            ],
            "source_identity_summary": source_summary,
            "app_identity_summary": app_summary,
            "source_matches_app_db": True,
        }

    return {
        **result,
        "source_identity_summary": source_summary,
        "app_identity_summary": app_summary,
        "source_matches_app_db": False,
    }


def validate_capture_source_dsn_from_env(*, allow_app_db_for_tests: bool | None = None) -> dict[str, Any]:
    """Validate capture source DSN using configured runtime environment values."""

    if allow_app_db_for_tests is None:
        allow_app_db_for_tests = str(os.getenv("ALLOW_STUDENT_CAPTURE_APP_DB_DSN_FOR_TESTS", "")).strip() == "1"

    source_dsn = os.getenv("STUDENT_CAPTURE_SOURCE_DSN")
    return validate_capture_source_dsn(
        source_dsn=source_dsn,
        app_dsn=(build_app_db_dsn_from_env() if str(source_dsn or "").strip() else None),
        allow_app_db_for_tests=bool(allow_app_db_for_tests),
        allowed_schemas_raw=os.getenv("STUDENT_CAPTURE_ALLOWED_SCHEMAS"),
        allowed_tables_raw=os.getenv("STUDENT_CAPTURE_ALLOWED_TABLES"),
    )
