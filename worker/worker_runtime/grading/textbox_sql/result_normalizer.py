"""Deterministic normalization and hashing for SQL result sets."""

from __future__ import annotations

from base64 import b64encode
from datetime import date
from datetime import datetime
from datetime import time
from decimal import Decimal
import hashlib
import json
from typing import Any


_NORMALIZATION_VERSION = "s2w4_3_v1"


def _to_json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        return "base64:" + b64encode(raw).decode("ascii")
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k): _to_json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_value(v) for v in value]
    return str(value)


def normalize_result_set(
    columns: list[str],
    rows: list[tuple | dict],
    *,
    truncated: bool = False,
) -> dict[str, Any]:
    normalized_columns = [str(col) for col in columns]
    normalized_rows: list[list[Any]] = []

    for row in rows:
        if isinstance(row, dict):
            row_values = [_to_json_value(row.get(col)) for col in normalized_columns]
            normalized_rows.append(row_values)
            continue

        sequence = list(row)
        row_values: list[Any] = []
        for idx, _ in enumerate(normalized_columns):
            row_values.append(_to_json_value(sequence[idx] if idx < len(sequence) else None))
        normalized_rows.append(row_values)

    return {
        "columns": normalized_columns,
        "rows": normalized_rows,
        "row_count": len(normalized_rows),
        "truncated": bool(truncated),
        "normalization_version": _NORMALIZATION_VERSION,
    }


def stable_result_hash(payload: dict) -> str:
    canonical_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
