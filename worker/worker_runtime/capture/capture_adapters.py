"""Capture adapter boundary for S2W-5.4 safe DSN-guarded integration."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any
from typing import Mapping
from typing import Protocol
from typing import runtime_checkable

from worker_runtime.capture.capture_dsn_guard import validate_capture_source_dsn_from_env


def _stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@runtime_checkable
class CaptureAdapter(Protocol):
    """Protocol boundary for capture sources used by worker runtime."""

    def collect_capture(
        self,
        *,
        capture_job_id: int,
        exam_submission_id: int,
        submission_seal_id: int,
        capture_type: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Collect source payload and return canonical capture artifact+dataset shape."""


class DeterministicTestCaptureAdapter:
    """Deterministic test-only adapter with stable output and row cap."""

    def __init__(self, *, max_rows: int = 10) -> None:
        self._max_rows = max(1, int(max_rows))

    def collect_capture(
        self,
        *,
        capture_job_id: int,
        exam_submission_id: int,
        submission_seal_id: int,
        capture_type: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        seed = (
            f"capture-job:{int(capture_job_id)}|submission:{int(exam_submission_id)}|"
            f"seal:{int(submission_seal_id)}|type:{str(capture_type)}"
        )

        desired_rows = 5
        rows: list[dict[str, Any]] = []
        for index in range(desired_rows):
            token = hashlib.sha256(f"{seed}|row:{index}".encode("utf-8")).hexdigest()[:16]
            rows.append(
                {
                    "row_no": index + 1,
                    "token": token,
                    "capture_type": str(capture_type),
                }
            )

        capped_rows = rows[: self._max_rows]
        dataset_schema = [
            {"name": "row_no", "type": "integer"},
            {"name": "token", "type": "text"},
            {"name": "capture_type", "type": "text"},
        ]

        artifact_payload = {
            "adapter": "deterministic-test",
            "seed": seed,
            "metadata": dict(metadata or {}),
            "rows_capped": len(capped_rows),
        }

        return {
            "adapter_name": "deterministic-test",
            "artifact_payload": artifact_payload,
            "artifact_hash": _stable_hash(artifact_payload),
            "dataset_schema": dataset_schema,
            "dataset_schema_hash": _stable_hash(dataset_schema),
            "dataset_rows": capped_rows,
            "row_count": len(capped_rows),
        }


class PostgresCaptureAdapter:
    """DSN-guarded placeholder for future production capture implementation."""

    def __init__(
        self,
        *,
        source_dsn: str,
        validation_result: dict[str, Any],
    ) -> None:
        self._source_dsn = str(source_dsn).strip()
        self._validation_result = dict(validation_result)

    @classmethod
    def from_env(cls) -> "PostgresCaptureAdapter":
        validation = validate_capture_source_dsn_from_env()
        if not bool(validation.get("is_valid")):
            reason = str(validation.get("reason_code") or "capture_dsn_guard_failed")
            message = str(validation.get("message") or "Capture source DSN validation failed")
            raise RuntimeError(f"{reason}: {message}")

        source_dsn = str(os.getenv("STUDENT_CAPTURE_SOURCE_DSN", "")).strip()
        if not source_dsn:
            raise RuntimeError("source_dsn_missing: STUDENT_CAPTURE_SOURCE_DSN is required")

        return cls(source_dsn=source_dsn, validation_result=validation)

    def collect_capture(
        self,
        *,
        capture_job_id: int,
        exam_submission_id: int,
        submission_seal_id: int,
        capture_type: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        _ = capture_job_id
        _ = exam_submission_id
        _ = submission_seal_id
        _ = capture_type
        _ = metadata
        raise NotImplementedError(
            "PostgresCaptureAdapter is a guarded boundary only in S2W-5.4; "
            "production source capture is not enabled yet."
        )


def _allow_test_adapter_override(*, explicit_allow_for_tests: bool | None = None) -> bool:
    if explicit_allow_for_tests is None:
        allow_token = str(os.getenv("ALLOW_STUDENT_CAPTURE_APP_DB_DSN_FOR_TESTS", "")).strip() == "1"
    else:
        allow_token = bool(explicit_allow_for_tests)

    if not allow_token:
        return False

    return bool(os.getenv("PYTEST_CURRENT_TEST")) or str(
        os.getenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION", "")
    ).strip() == "1"


def create_capture_adapter_from_env(
    *,
    adapter_mode: str | None = None,
    deterministic_max_rows: int = 10,
    allow_test_override: bool | None = None,
) -> CaptureAdapter:
    """Create capture adapter with explicit opt-in for test-only deterministic mode."""

    mode = str(adapter_mode or os.getenv("STUDENT_CAPTURE_ADAPTER_MODE", "postgres")).strip().lower()

    if mode in {"", "postgres"}:
        return PostgresCaptureAdapter.from_env()

    if mode in {"deterministic-test", "test-deterministic", "test"}:
        if not _allow_test_adapter_override(explicit_allow_for_tests=allow_test_override):
            raise RuntimeError(
                "deterministic_test_adapter_forbidden: "
                "set ALLOW_STUDENT_CAPTURE_APP_DB_DSN_FOR_TESTS=1 and run in explicit test context"
            )
        return DeterministicTestCaptureAdapter(max_rows=deterministic_max_rows)

    raise ValueError(f"unsupported_capture_adapter_mode: {mode}")
