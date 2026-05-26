"""Parser for expected result payload snapshots used in S2W-4.4 comparisons."""

from __future__ import annotations

import json
from typing import Any

from worker_runtime.grading.textbox_sql.result_normalizer import stable_result_hash


_COMPARISON_NORMALIZATION_VERSION = "s2w4_4_v1"


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


def _normalize_payload_shape(payload: dict[str, Any]) -> dict[str, Any]:
    columns = payload.get("columns")
    rows = payload.get("rows")

    if not isinstance(columns, list):
        raise ValueError("expected_columns_missing_or_invalid")
    if not isinstance(rows, list):
        raise ValueError("expected_rows_missing_or_invalid")

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

        raise ValueError("expected_row_type_invalid")

    row_count_raw = payload.get("row_count")
    if isinstance(row_count_raw, int) and row_count_raw >= 0:
        row_count = row_count_raw
    else:
        row_count = len(normalized_rows)

    return {
        "columns": normalized_columns,
        "rows": normalized_rows,
        "row_count": int(row_count),
        "truncated": bool(payload.get("truncated", False)),
        "normalization_version": str(payload.get("normalization_version") or _COMPARISON_NORMALIZATION_VERSION),
    }


def parse_expected_result_payload(expected_row: dict) -> dict:
    """Parse expected answer row into normalized result-set payload.

    Returns:
    {
      ok: bool,
      payload: dict | None,
      expected_hash: str | None,
      source: str,
      error_code: str | None,
      error_message: str | None,
    }
    """

    if not isinstance(expected_row, dict):
        return {
            "ok": False,
            "payload": None,
            "expected_hash": None,
            "source": "invalid_input",
            "error_code": "invalid_expected_row",
            "error_message": "Expected row must be a dictionary.",
        }

    expected_hash_raw = expected_row.get("expected_hash")
    expected_hash = str(expected_hash_raw).strip() if expected_hash_raw else None

    if expected_row.get("expected_payload_json") is not None:
        source = "expected_payload_json"
        payload_json = expected_row.get("expected_payload_json")
        if not isinstance(payload_json, dict):
            return {
                "ok": False,
                "payload": None,
                "expected_hash": expected_hash,
                "source": source,
                "error_code": "invalid_expected_payload_json",
                "error_message": "expected_payload_json must be an object.",
            }
        try:
            normalized_payload = _normalize_payload_shape(payload_json)
        except ValueError as exc:
            return {
                "ok": False,
                "payload": None,
                "expected_hash": expected_hash,
                "source": source,
                "error_code": "malformed_expected_payload",
                "error_message": str(exc),
            }

        return {
            "ok": True,
            "payload": normalized_payload,
            "expected_hash": expected_hash or stable_result_hash(normalized_payload),
            "source": source,
            "error_code": None,
            "error_message": None,
        }

    if expected_row.get("expected_payload"):
        source = "expected_payload"
        payload_text = str(expected_row.get("expected_payload") or "")
        try:
            decoded = json.loads(payload_text)
        except json.JSONDecodeError:
            return {
                "ok": False,
                "payload": None,
                "expected_hash": expected_hash,
                "source": source,
                "error_code": "invalid_expected_payload_json_text",
                "error_message": "expected_payload is not valid JSON.",
            }

        if not isinstance(decoded, dict):
            return {
                "ok": False,
                "payload": None,
                "expected_hash": expected_hash,
                "source": source,
                "error_code": "invalid_expected_payload_json_text",
                "error_message": "expected_payload JSON must decode to an object.",
            }

        try:
            normalized_payload = _normalize_payload_shape(decoded)
        except ValueError as exc:
            return {
                "ok": False,
                "payload": None,
                "expected_hash": expected_hash,
                "source": source,
                "error_code": "malformed_expected_payload",
                "error_message": str(exc),
            }

        return {
            "ok": True,
            "payload": normalized_payload,
            "expected_hash": expected_hash or stable_result_hash(normalized_payload),
            "source": source,
            "error_code": None,
            "error_message": None,
        }

    if expected_hash:
        return {
            "ok": False,
            "payload": None,
            "expected_hash": expected_hash,
            "source": "expected_hash_only",
            "error_code": "hash_only_expected_payload",
            "error_message": "Expected hash without payload is not sufficient for row-level comparison in S2W-4.4.",
        }

    return {
        "ok": False,
        "payload": None,
        "expected_hash": None,
        "source": "missing_expected_payload",
        "error_code": "missing_expected_payload",
        "error_message": "Expected payload is missing.",
    }
