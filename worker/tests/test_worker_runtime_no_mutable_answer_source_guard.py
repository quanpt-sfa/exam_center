"""Static guards for runtime orchestration mutable-answer and log-redaction safety."""

from __future__ import annotations

from pathlib import Path
import sys


WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.runtime_logging import sanitize_log_value


def test_runtime_orchestration_does_not_reference_submission_answer_state_table() -> None:
    runtime_root = WORKER_SRC / "worker_runtime"
    targets = [
        runtime_root / "cli.py",
        runtime_root / "runtime_loop.py",
        runtime_root / "runtime_logging.py",
    ]

    for target in targets:
        content = target.read_text(encoding="utf-8")
        lowered = content.lower()
        assert "submission.answer_state" not in lowered
        assert "from submission.answer_state" not in lowered
        assert "join submission.answer_state" not in lowered


def test_runtime_log_sanitization_excludes_raw_answer_and_capture_rows() -> None:
    payload = {
        "message": "password=top-secret dsn=postgresql://exam_sys_app:pw-secret@localhost:5432/exam_sys_dev",
        "raw_answer": "SELECT * FROM students",
        "capture_dataset_rows": [{"student_code": "S001", "score": 10}],
        "artifact_payload": {"foo": "bar"},
    }

    sanitized = sanitize_log_value(payload)
    blob = str(sanitized).lower()

    assert "top-secret" not in blob
    assert "pw-secret" not in blob
    assert "postgresql://" not in blob
    assert "select * from students" not in blob
    assert "student_code" not in blob
    assert sanitized["raw_answer"] == "<redacted>"
    assert sanitized["capture_dataset_rows"] == "<redacted>"
    assert sanitized["artifact_payload"] == "<redacted>"
