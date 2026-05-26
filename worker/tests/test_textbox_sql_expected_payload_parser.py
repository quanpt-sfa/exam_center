"""Unit tests for S2W-4.4 expected payload parser."""

from __future__ import annotations

from pathlib import Path
import sys


WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.textbox_sql.comparison.expected_payload_parser import (  # noqa: E402
    parse_expected_result_payload,
)


def test_parse_normalized_expected_payload_json() -> None:
    row = {
        "generated_expected_answer_id": 1,
        "solution_type": "SQL_RESULT",
        "expected_payload_json": {
            "columns": ["value"],
            "rows": [[1]],
            "row_count": 1,
            "normalization_version": "s2w4_3_v1",
        },
        "expected_hash": None,
    }

    parsed = parse_expected_result_payload(row)

    assert parsed["ok"] is True
    assert parsed["source"] == "expected_payload_json"
    payload = parsed["payload"]
    assert payload is not None
    assert payload["columns"] == ["value"]
    assert payload["rows"] == [[1]]
    assert payload["row_count"] == 1
    assert payload["truncated"] is False
    assert parsed["expected_hash"] is not None


def test_parse_expected_payload_json_string() -> None:
    row = {
        "expected_payload": '{"columns":["id"],"rows":[[1],[2]]}',
        "expected_hash": None,
    }

    parsed = parse_expected_result_payload(row)

    assert parsed["ok"] is True
    assert parsed["source"] == "expected_payload"
    assert parsed["payload"]["columns"] == ["id"]
    assert parsed["payload"]["rows"] == [[1], [2]]


def test_hash_only_expected_payload_is_not_sufficient() -> None:
    row = {
        "expected_payload": None,
        "expected_payload_json": None,
        "expected_hash": "a" * 64,
    }

    parsed = parse_expected_result_payload(row)

    assert parsed["ok"] is False
    assert parsed["source"] == "expected_hash_only"
    assert parsed["error_code"] == "hash_only_expected_payload"
    assert parsed["expected_hash"] == "a" * 64


def test_malformed_expected_payload_is_handled_safely() -> None:
    row = {
        "expected_payload": "{this-is-not-json}",
    }

    parsed = parse_expected_result_payload(row)

    assert parsed["ok"] is False
    assert parsed["source"] == "expected_payload"
    assert parsed["error_code"] == "invalid_expected_payload_json_text"
    assert parsed["payload"] is None
