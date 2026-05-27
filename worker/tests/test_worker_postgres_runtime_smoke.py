"""Worker PostgreSQL runtime smoke against an explicit test-only database."""

from __future__ import annotations

import os

from psycopg.rows import dict_row
import psycopg
import pytest

from worker_runtime.db_env import build_postgres_conninfo_from_env


pytestmark = [
    pytest.mark.postgres,
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION") != "1",
        reason="Set EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION=1 to run PostgreSQL integration tests",
    ),
]


def _require_safe_test_database() -> str:
    database = str(os.getenv("POSTGRES_DB") or "").strip()
    if not database:
        pytest.skip("Missing POSTGRES_DB for worker PostgreSQL runtime smoke")
    normalized = database.lower()
    if normalized != "exam_sys_test" and not normalized.endswith("_test"):
        pytest.fail(
            "Worker PostgreSQL runtime smoke refuses to run against a non-test database. "
            "Set POSTGRES_DB to exam_sys_test or a name ending with _test."
        )
    return database


def test_worker_runtime_connects_to_safe_postgres_test_db() -> None:
    database = _require_safe_test_database()
    required_envs = [
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    ]
    missing = [name for name in required_envs if not str(os.getenv(name) or "").strip()]
    if missing:
        pytest.skip(f"Missing required DB env for worker PostgreSQL runtime smoke: {', '.join(missing)}")

    with psycopg.connect(build_postgres_conninfo_from_env(), autocommit=False) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    current_database() AS database_name,
                    current_user AS database_user,
                    CURRENT_TIMESTAMP AS server_timestamp
                """
            )
            row = cur.fetchone()

    if row is None:
        raise AssertionError("Worker PostgreSQL runtime smoke failed to read database metadata")

    assert str(row["database_name"]) == database
    assert str(row["database_user"]) == str(os.getenv("POSTGRES_USER"))
    assert row["server_timestamp"] is not None
