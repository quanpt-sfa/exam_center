"""Unit tests for deterministic SQL result normalization and hashing."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
from decimal import Decimal
from pathlib import Path
import sys

WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.textbox_sql.result_normalizer import normalize_result_set
from worker_runtime.grading.textbox_sql.result_normalizer import stable_result_hash


def test_normalization_is_deterministic() -> None:
    columns = ["id", "amount", "created_at", "blob"]
    rows = [
        (1, Decimal("10.25"), datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc), b"abc"),
        (2, Decimal("11.50"), datetime(2026, 1, 2, 3, 5, 5, tzinfo=timezone.utc), b"xyz"),
    ]

    payload_a = normalize_result_set(columns, rows, truncated=False)
    payload_b = normalize_result_set(columns, rows, truncated=False)

    assert payload_a == payload_b
    assert payload_a["normalization_version"] == "s2w4_3_v1"
    assert payload_a["row_count"] == 2


def test_same_payload_yields_same_hash() -> None:
    payload = normalize_result_set(["id"], [(1,), (2,)])

    hash_a = stable_result_hash(payload)
    hash_b = stable_result_hash(payload)

    assert hash_a == hash_b


def test_different_payload_yields_different_hash() -> None:
    payload_a = normalize_result_set(["id"], [(1,), (2,)])
    payload_b = normalize_result_set(["id"], [(1,), (3,)])

    hash_a = stable_result_hash(payload_a)
    hash_b = stable_result_hash(payload_b)

    assert hash_a != hash_b
