"""Unit tests for worker runtime identity utilities."""

from __future__ import annotations

from pathlib import Path
import sys


WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.worker_identity import ensure_worker_role_suffix
from worker_runtime.worker_identity import generate_worker_id


def test_worker_id_uses_explicit_value() -> None:
    worker_id = generate_worker_id(
        role="grading",
        worker_id="explicit-worker-id",
        worker_id_prefix="ignored-prefix",
        hostname="ignored-host",
        pid=999,
    )

    assert worker_id == "explicit-worker-id"


def test_worker_id_generated_when_missing() -> None:
    worker_id = generate_worker_id(
        role="capture",
        worker_id=None,
        worker_id_prefix="wro",
        hostname="Node-A",
        pid=321,
    )

    assert worker_id == "wro-node-a-p321-capture"


def test_worker_role_suffix_is_stable() -> None:
    first = ensure_worker_role_suffix("wro-node-a-p321", role="dispatcher")
    second = ensure_worker_role_suffix(first, role="dispatcher")

    assert first == "wro-node-a-p321-dispatcher"
    assert second == first
