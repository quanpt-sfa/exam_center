"""Unit tests for S2W-4.4 pure result-set comparator."""

from __future__ import annotations

from pathlib import Path
import sys


WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.textbox_sql.comparison.result_set_comparator import (  # noqa: E402
    compare_result_sets,
)


def _payload(columns: list[str], rows: list[list], *, truncated: bool = False) -> dict:
    return {
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
        "normalization_version": "s2w4_3_v1",
    }


def test_exact_result_set_match_for_identical_columns_and_rows() -> None:
    expected = _payload(["id", "value"], [[1, "a"], [2, "b"]])
    actual = _payload(["id", "value"], [[1, "a"], [2, "b"]])

    result = compare_result_sets(expected, actual, "EXACT_RESULT_SET")

    assert result["comparison_status"] == "MATCH"
    assert result["comparison_payload_json"]["column_match"] is True
    assert result["comparison_payload_json"]["row_match"] is True


def test_exact_result_set_mismatch_for_row_order_difference() -> None:
    expected = _payload(["id"], [[1], [2]])
    actual = _payload(["id"], [[2], [1]])

    result = compare_result_sets(expected, actual, "EXACT_RESULT_SET")

    assert result["comparison_status"] == "MISMATCH"
    assert result["comparison_payload_json"]["mismatch_type"] == "row_mismatch"


def test_order_insensitive_result_set_match_for_row_order_difference() -> None:
    expected = _payload(["id"], [[1], [2]])
    actual = _payload(["id"], [[2], [1]])

    result = compare_result_sets(expected, actual, "ORDER_INSENSITIVE_RESULT_SET")

    assert result["comparison_status"] == "MATCH"
    assert result["comparison_payload_json"]["row_match"] is True


def test_order_insensitive_preserves_duplicate_row_counts() -> None:
    expected = _payload(["id"], [[1], [1], [2]])
    actual = _payload(["id"], [[1], [2], [2]])

    result = compare_result_sets(expected, actual, "ORDER_INSENSITIVE_RESULT_SET")

    assert result["comparison_status"] == "MISMATCH"
    assert result["comparison_payload_json"]["mismatch_type"] == "row_multiset_mismatch"


def test_column_order_mismatch_returns_mismatch() -> None:
    expected = _payload(["id", "value"], [[1, "a"]])
    actual = _payload(["value", "id"], [["a", 1]])

    result = compare_result_sets(expected, actual, "EXACT_RESULT_SET")

    assert result["comparison_status"] == "MISMATCH"
    assert result["comparison_payload_json"]["mismatch_type"] == "column_mismatch"


def test_missing_actual_payload_returns_error() -> None:
    expected = _payload(["id"], [[1]])

    result = compare_result_sets(expected, None, "EXACT_RESULT_SET")

    assert result["comparison_status"] == "ERROR"
    assert result["comparison_payload_json"]["mismatch_type"] == "missing_actual_payload"


def test_unsupported_method_returns_needs_review() -> None:
    expected = _payload(["id"], [[1]])
    actual = _payload(["id"], [[1]])

    result = compare_result_sets(expected, actual, "NUMERIC_TOLERANCE")

    assert result["comparison_status"] == "NEEDS_REVIEW"
    assert result["comparison_payload_json"]["mismatch_type"] == "unsupported_method"


def test_stable_hashes_are_deterministic() -> None:
    expected = _payload(["id"], [[1], [2]])
    actual = _payload(["id"], [[1], [2]])

    first = compare_result_sets(expected, actual, "EXACT_RESULT_SET")
    second = compare_result_sets(expected, actual, "EXACT_RESULT_SET")

    assert first["expected_hash"] == second["expected_hash"]
    assert first["actual_hash"] == second["actual_hash"]


def test_sample_mismatch_list_is_capped() -> None:
    expected = _payload(["id"], [[1], [2], [3], [4], [5], [6], [7]])
    actual = _payload(["id"], [[101], [102], [103], [104], [105], [106], [107]])

    result = compare_result_sets(expected, actual, "EXACT_RESULT_SET")

    assert result["comparison_status"] == "MISMATCH"
    assert len(result["comparison_payload_json"]["sample_mismatches"]) <= 5


def test_missing_expected_payload_returns_needs_review() -> None:
    actual = _payload(["id"], [[1]])

    result = compare_result_sets(None, actual, "EXACT_RESULT_SET")

    assert result["comparison_status"] == "NEEDS_REVIEW"
    assert result["comparison_payload_json"]["mismatch_type"] == "missing_expected_payload"


def test_malformed_expected_payload_returns_needs_review() -> None:
    expected = {"columns": ["id"]}
    actual = _payload(["id"], [[1]])

    result = compare_result_sets(expected, actual, "EXACT_RESULT_SET")

    assert result["comparison_status"] == "NEEDS_REVIEW"
    assert result["comparison_payload_json"]["mismatch_type"] == "expected_payload_malformed"


def test_actual_truncated_returns_needs_review() -> None:
    expected = _payload(["id"], [[1], [2]])
    actual = _payload(["id"], [[1], [2]], truncated=True)

    result = compare_result_sets(expected, actual, "EXACT_RESULT_SET")

    assert result["comparison_status"] == "NEEDS_REVIEW"
    assert result["comparison_payload_json"]["mismatch_type"] == "actual_payload_truncated"
