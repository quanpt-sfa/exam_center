"""Sandboxed TEXTBOX_SQL executor with read-only policy enforcement."""

from __future__ import annotations

import re
from time import perf_counter
from typing import Any

from psycopg import connect

from worker_runtime.grading.textbox_sql.result_normalizer import normalize_result_set
from worker_runtime.grading.textbox_sql.result_normalizer import stable_result_hash
from worker_runtime.grading.textbox_sql.sql_policy import validate_read_only_sql


class TextboxSqlExecutor:
    """Executes read-only SQL against a sandbox DSN and normalizes result payloads."""

    def __init__(
        self,
        *,
        executor_dsn: str | None,
        statement_timeout_ms: int = 3000,
        max_rows: int = 100,
        max_columns: int = 50,
        allowed_schemas: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        self._executor_dsn = str(executor_dsn).strip() if executor_dsn else None
        self._statement_timeout_ms = max(1, int(statement_timeout_ms))
        self._max_rows = max(1, int(max_rows))
        self._max_columns = max(1, int(max_columns))
        self._allowed_schemas = tuple(
            str(schema).strip()
            for schema in (allowed_schemas or [])
            if str(schema).strip()
        )

    def execute(self, sql_text: str) -> dict[str, Any]:
        started = perf_counter()

        policy = validate_read_only_sql(sql_text)
        if not bool(policy.get("is_allowed")):
            return self._error_result(
                started=started,
                error_code=str(policy.get("reason_code") or "policy_rejected"),
                error_message=str(policy.get("message") or "SQL policy rejected query."),
                normalized_sql=None,
            )

        normalized_sql = str(policy.get("normalized_sql") or "")

        if not self._executor_dsn:
            return self._error_result(
                started=started,
                error_code="executor_dsn_not_configured",
                error_message="SQL executor DSN is not configured.",
                normalized_sql=normalized_sql,
            )

        try:
            with connect(self._executor_dsn, autocommit=False) as conn:
                with conn.cursor() as cur:
                    cur.execute("SET TRANSACTION READ ONLY")
                    cur.execute(f"SET LOCAL statement_timeout = {int(self._statement_timeout_ms)}")
                    cur.execute(normalized_sql)

                    description = cur.description or []
                    columns = [
                        str(col.name) if hasattr(col, "name") else str(col[0])
                        for col in description
                    ]

                    if len(columns) > self._max_columns:
                        return self._error_result(
                            started=started,
                            error_code="max_columns_exceeded",
                            error_message=(
                                f"Query returned {len(columns)} columns which exceeds "
                                f"the configured max_columns={self._max_columns}."
                            ),
                            normalized_sql=normalized_sql,
                        )

                    fetched_rows = cur.fetchmany(self._max_rows + 1)
                    truncated = len(fetched_rows) > self._max_rows
                    rows = fetched_rows[: self._max_rows]

                    normalized_payload = normalize_result_set(columns, rows, truncated=truncated)
                    result_hash = stable_result_hash(normalized_payload)

                conn.rollback()

        except Exception as exc:  # noqa: BLE001
            return self._error_result(
                started=started,
                error_code="sql_execution_error",
                error_message=self._sanitize_error_message(str(exc)),
                normalized_sql=normalized_sql,
            )

        runtime_ms = int((perf_counter() - started) * 1000)
        return {
            "ok": True,
            "result_type": "SQL_RESULT_SET",
            "runtime_ms": runtime_ms,
            "normalized_sql": normalized_sql,
            "payload": normalized_payload,
            "result_hash": result_hash,
            "error_code": None,
            "error_message": None,
            "executor_metadata": self._executor_metadata(),
        }

    def _error_result(
        self,
        *,
        started: float,
        error_code: str,
        error_message: str,
        normalized_sql: str | None,
    ) -> dict[str, Any]:
        runtime_ms = int((perf_counter() - started) * 1000)
        return {
            "ok": False,
            "result_type": "SQL_RUNTIME_ERROR",
            "runtime_ms": runtime_ms,
            "normalized_sql": normalized_sql,
            "payload": None,
            "result_hash": None,
            "error_code": str(error_code),
            "error_message": self._sanitize_error_message(error_message),
            "executor_metadata": self._executor_metadata(),
        }

    def _executor_metadata(self) -> dict[str, Any]:
        return {
            "allowed_schemas": list(self._allowed_schemas),
        }

    def _sanitize_error_message(self, message: str) -> str:
        safe = (message or "SQL execution failed.").strip()
        safe = safe.splitlines()[0]

        if self._executor_dsn:
            safe = safe.replace(self._executor_dsn, "[dsn-redacted]")

        safe = re.sub(r"(?i)password\s*=\s*[^\s;]+", "password=<redacted>", safe)
        safe = re.sub(r"(?i)(postgres(?:ql)?://[^:\s]+:)[^@\s]+@", r"\1<redacted>@", safe)

        if len(safe) > 500:
            safe = safe[:500].rstrip() + "..."

        return safe or "SQL execution failed."
