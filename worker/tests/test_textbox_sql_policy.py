"""Unit tests for TEXTBOX_SQL read-only policy validator."""

from __future__ import annotations

from pathlib import Path
import sys

WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.textbox_sql.sql_policy import validate_read_only_sql


def test_policy_allows_simple_select() -> None:
    result = validate_read_only_sql(" SELECT 1 AS value; ")

    assert result["is_allowed"] is True
    assert result["normalized_sql"] == "SELECT 1 AS value"
    assert result["reason_code"] is None
    assert result["message"] is None


def test_policy_allows_with_query() -> None:
    result = validate_read_only_sql("WITH x AS (SELECT 1) SELECT * FROM x")

    assert result["is_allowed"] is True
    assert result["normalized_sql"] == "WITH x AS (SELECT 1) SELECT * FROM x"


def test_policy_rejects_empty_sql() -> None:
    result = validate_read_only_sql("   \n  ")

    assert result["is_allowed"] is False
    assert result["reason_code"] == "empty_sql"


def test_policy_rejects_mutating_and_ddl_keywords() -> None:
    for sql_text in [
        "INSERT INTO t VALUES (1)",
        "UPDATE t SET a = 1",
        "DELETE FROM t",
        "DROP TABLE t",
        "ALTER TABLE t ADD COLUMN b int",
    ]:
        result = validate_read_only_sql(sql_text)
        assert result["is_allowed"] is False
        assert result["reason_code"] in {"statement_type_not_allowed", "forbidden_keyword_detected"}


def test_policy_rejects_multiple_statements() -> None:
    result = validate_read_only_sql("SELECT 1; SELECT 2")

    assert result["is_allowed"] is False
    assert result["reason_code"] == "multiple_statements_not_allowed"


def test_policy_rejects_comment_obfuscated_dangerous_keyword_mvp() -> None:
    result = validate_read_only_sql("SELECT 1 DR/**/OP")

    assert result["is_allowed"] is False
    assert result["reason_code"] == "forbidden_keyword_detected"
