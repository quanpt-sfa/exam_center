"""Pure result-set comparator functions for S2W-4.4."""

from __future__ import annotations

from collections import Counter
import json
from typing import Any

from worker_runtime.grading.textbox_sql.result_normalizer import stable_result_hash


_COMPARISON_VERSION = "s2w4_4_v1"
_MAX_SAMPLE_MISMATCHES = 5
_SUPPORTED_METHODS = {"EXACT_RESULT_SET", "ORDER_INSENSITIVE_RESULT_SET"}


def _normalize_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _normalize_json_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_json_value(v) for v in value]
    if isinstance(value, tuple):
        return [_normalize_json_value(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _normalize_payload(payload: dict[str, Any], *, label: str) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(payload, dict):
        return None, f"{label}_payload_not_object"

    columns = payload.get("columns")
    rows = payload.get("rows")

    if not isinstance(columns, list):
        return None, f"{label}_columns_missing_or_invalid"
    if not isinstance(rows, list):
        return None, f"{label}_rows_missing_or_invalid"

    normalized_columns = [str(col) for col in columns]
    normalized_rows: list[list[Any]] = []

    for row in rows:
        if isinstance(row, dict):
            row_values = [_normalize_json_value(row.get(col)) for col in normalized_columns]
            normalized_rows.append(row_values)
            continue

        if isinstance(row, (list, tuple)):
            sequence = list(row)
            normalized_rows.append(
                [
                    _normalize_json_value(sequence[idx] if idx < len(sequence) else None)
                    for idx, _ in enumerate(normalized_columns)
                ]
            )
            continue

        return None, f"{label}_row_type_invalid"

    row_count_raw = payload.get("row_count")
    row_count = int(row_count_raw) if isinstance(row_count_raw, int) and row_count_raw >= 0 else len(normalized_rows)

    return (
        {
            "columns": normalized_columns,
            "rows": normalized_rows,
            "row_count": row_count,
            "truncated": bool(payload.get("truncated", False)),
            "normalization_version": str(payload.get("normalization_version") or _COMPARISON_VERSION),
        },
        None,
    )


def _canonical_row_key(row: list[Any]) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _build_result(
    *,
    method: str,
    comparison_status: str,
    mismatch_summary: str,
    mismatch_type: str,
    column_match: bool,
    row_match: bool,
    expected_payload: dict[str, Any] | None,
    actual_payload: dict[str, Any] | None,
    sample_mismatches: list[dict[str, Any]],
) -> dict:
    expected_columns = list(expected_payload.get("columns", [])) if expected_payload else []
    actual_columns = list(actual_payload.get("columns", [])) if actual_payload else []
    expected_row_count = int(expected_payload.get("row_count", 0)) if expected_payload else 0
    actual_row_count = int(actual_payload.get("row_count", 0)) if actual_payload else 0

    comparison_payload_json = {
        "method": method,
        "comparison_version": _COMPARISON_VERSION,
        "column_match": bool(column_match),
        "row_match": bool(row_match),
        "expected_columns": expected_columns,
        "actual_columns": actual_columns,
        "expected_row_count": expected_row_count,
        "actual_row_count": actual_row_count,
        "mismatch_type": mismatch_type,
        "sample_mismatches": list(sample_mismatches[:_MAX_SAMPLE_MISMATCHES]),
    }

    expected_hash = stable_result_hash(expected_payload) if expected_payload is not None else None
    actual_hash = stable_result_hash(actual_payload) if actual_payload is not None else None

    return {
        "comparison_status": comparison_status,
        "mismatch_summary": mismatch_summary,
        "comparison_payload_json": comparison_payload_json,
        "expected_hash": expected_hash,
        "actual_hash": actual_hash,
    }


def compare_result_sets(expected_payload: dict | None, actual_payload: dict | None, method: str) -> dict:
    normalized_method = str(method or "").strip().upper()

    if normalized_method not in _SUPPORTED_METHODS:
        return _build_result(
            method=normalized_method or "UNKNOWN",
            comparison_status="NEEDS_REVIEW",
            mismatch_summary="Unsupported comparison method.",
            mismatch_type="unsupported_method",
            column_match=False,
            row_match=False,
            expected_payload=None,
            actual_payload=None,
            sample_mismatches=[{"method": normalized_method or None}],
        )

    if expected_payload is None:
        return _build_result(
            method=normalized_method,
            comparison_status="NEEDS_REVIEW",
            mismatch_summary="Expected payload is missing.",
            mismatch_type="missing_expected_payload",
            column_match=False,
            row_match=False,
            expected_payload=None,
            actual_payload=None,
            sample_mismatches=[],
        )

    if actual_payload is None:
        return _build_result(
            method=normalized_method,
            comparison_status="ERROR",
            mismatch_summary="Actual payload is missing.",
            mismatch_type="missing_actual_payload",
            column_match=False,
            row_match=False,
            expected_payload=None,
            actual_payload=None,
            sample_mismatches=[],
        )

    normalized_expected, expected_error = _normalize_payload(expected_payload, label="expected")
    if expected_error is not None or normalized_expected is None:
        return _build_result(
            method=normalized_method,
            comparison_status="NEEDS_REVIEW",
            mismatch_summary="Expected payload is malformed.",
            mismatch_type="expected_payload_malformed",
            column_match=False,
            row_match=False,
            expected_payload=None,
            actual_payload=None,
            sample_mismatches=[{"error": expected_error}],
        )

    normalized_actual, actual_error = _normalize_payload(actual_payload, label="actual")
    if actual_error is not None or normalized_actual is None:
        return _build_result(
            method=normalized_method,
            comparison_status="ERROR",
            mismatch_summary="Actual payload is malformed.",
            mismatch_type="actual_payload_malformed",
            column_match=False,
            row_match=False,
            expected_payload=normalized_expected,
            actual_payload=None,
            sample_mismatches=[{"error": actual_error}],
        )

    if bool(normalized_actual.get("truncated")):
        return _build_result(
            method=normalized_method,
            comparison_status="NEEDS_REVIEW",
            mismatch_summary="Actual payload is truncated; automatic row-level comparison is not trusted.",
            mismatch_type="actual_payload_truncated",
            column_match=normalized_expected["columns"] == normalized_actual["columns"],
            row_match=False,
            expected_payload=normalized_expected,
            actual_payload=normalized_actual,
            sample_mismatches=[],
        )

    expected_columns = normalized_expected["columns"]
    actual_columns = normalized_actual["columns"]
    column_match = expected_columns == actual_columns

    if not column_match:
        return _build_result(
            method=normalized_method,
            comparison_status="MISMATCH",
            mismatch_summary="Columns do not match.",
            mismatch_type="column_mismatch",
            column_match=False,
            row_match=False,
            expected_payload=normalized_expected,
            actual_payload=normalized_actual,
            sample_mismatches=[
                {
                    "expected_columns": expected_columns,
                    "actual_columns": actual_columns,
                }
            ],
        )

    expected_rows = normalized_expected["rows"]
    actual_rows = normalized_actual["rows"]

    if normalized_method == "EXACT_RESULT_SET":
        row_match = expected_rows == actual_rows
        if row_match:
            return _build_result(
                method=normalized_method,
                comparison_status="MATCH",
                mismatch_summary="Rows and columns match exactly.",
                mismatch_type="none",
                column_match=True,
                row_match=True,
                expected_payload=normalized_expected,
                actual_payload=normalized_actual,
                sample_mismatches=[],
            )

        sample_mismatches: list[dict[str, Any]] = []
        for idx in range(min(len(expected_rows), len(actual_rows))):
            if expected_rows[idx] != actual_rows[idx]:
                sample_mismatches.append(
                    {
                        "index": idx,
                        "expected_row": expected_rows[idx],
                        "actual_row": actual_rows[idx],
                    }
                )
                if len(sample_mismatches) >= _MAX_SAMPLE_MISMATCHES:
                    break

        if len(sample_mismatches) < _MAX_SAMPLE_MISMATCHES and len(expected_rows) != len(actual_rows):
            sample_mismatches.append(
                {
                    "expected_row_count": len(expected_rows),
                    "actual_row_count": len(actual_rows),
                }
            )

        return _build_result(
            method=normalized_method,
            comparison_status="MISMATCH",
            mismatch_summary="Row order or row values do not match exactly.",
            mismatch_type="row_mismatch",
            column_match=True,
            row_match=False,
            expected_payload=normalized_expected,
            actual_payload=normalized_actual,
            sample_mismatches=sample_mismatches,
        )

    expected_counter = Counter(_canonical_row_key(row) for row in expected_rows)
    actual_counter = Counter(_canonical_row_key(row) for row in actual_rows)

    if expected_counter == actual_counter:
        return _build_result(
            method=normalized_method,
            comparison_status="MATCH",
            mismatch_summary="Rows match as a multiset.",
            mismatch_type="none",
            column_match=True,
            row_match=True,
            expected_payload=normalized_expected,
            actual_payload=normalized_actual,
            sample_mismatches=[],
        )

    sample_mismatches = []
    all_keys = sorted(set(expected_counter.keys()) | set(actual_counter.keys()))
    for key in all_keys:
        expected_count = expected_counter.get(key, 0)
        actual_count = actual_counter.get(key, 0)
        if expected_count != actual_count:
            sample_mismatches.append(
                {
                    "row": json.loads(key),
                    "expected_count": expected_count,
                    "actual_count": actual_count,
                }
            )
            if len(sample_mismatches) >= _MAX_SAMPLE_MISMATCHES:
                break

    return _build_result(
        method=normalized_method,
        comparison_status="MISMATCH",
        mismatch_summary="Rows do not match as a multiset.",
        mismatch_type="row_multiset_mismatch",
        column_match=True,
        row_match=False,
        expected_payload=normalized_expected,
        actual_payload=normalized_actual,
        sample_mismatches=sample_mismatches,
    )
