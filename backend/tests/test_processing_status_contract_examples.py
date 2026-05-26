"""Contract fixture validation for ACF-4 processing status golden examples."""

from __future__ import annotations

import json
from pathlib import Path

from app.modules.submission.processing_status_models import ProcessingOverallStatus


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "processing_status"

REQUIRED_TOP_LEVEL_KEYS = {
    "exam_submission_id",
    "overall_status",
    "is_terminal",
    "can_retry",
    "pending_reason",
    "failure_reason",
    "seal",
    "capture",
    "grading",
    "tasks",
    "results",
    "score",
    "timestamps",
}

REQUIRED_NESTED_KEYS = {
    "seal": {"submission_seal_id", "seal_status", "sealed_at", "sealed_answer_count", "has_sealed_answer"},
    "capture": {
        "required",
        "status",
        "capture_job_id",
        "capture_profile_id",
        "artifact_count",
        "dataset_count",
        "latest_event_type",
        "latest_error_code",
        "latest_error_message_sanitized",
    },
    "grading": {
        "grading_job_id",
        "grading_job_status",
        "grading_run_id",
        "grading_run_status",
        "worker_id",
        "claimed_at",
        "finished_at",
        "latest_event_type",
    },
    "tasks": {
        "total",
        "queued",
        "running",
        "waiting_capture",
        "completed",
        "failed",
        "needs_review",
        "by_input_source",
        "by_answer_language",
    },
    "results": {"actual_result_count", "comparison_count", "question_score_count"},
    "score": {"submission_score_id", "total_score", "max_score", "score_status", "finalized_at"},
    "timestamps": {"created_at", "updated_at", "latest_activity_at"},
}

EXPECTED_FIXTURE_TERMINAL = {
    "waiting_grading.json": False,
    "waiting_capture.json": False,
    "capturing.json": False,
    "grading.json": False,
    "completed.json": True,
    "capture_failed.json": True,
    "grading_failed.json": True,
    "needs_review.json": True,
}

FORBIDDEN_TOKENS = [
    "answer_state",
    "answer_text",
    "sealed_answer_text",
    "raw_answer",
    "row_payload_json",
    "capture_dataset_row",
    "password",
    "dsn",
    "traceback",
    "select *",
]


def _load_fixture(name: str) -> dict:
    path = FIXTURE_DIR / name
    assert path.exists(), f"Missing fixture: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_processing_status_contract_fixtures_match_required_schema() -> None:
    assert FIXTURE_DIR.exists()

    allowed_enum = {item.value for item in ProcessingOverallStatus}

    for fixture_name, expected_terminal in EXPECTED_FIXTURE_TERMINAL.items():
        payload = _load_fixture(fixture_name)

        assert REQUIRED_TOP_LEVEL_KEYS.issubset(payload.keys())
        assert payload["overall_status"] in allowed_enum
        assert payload["is_terminal"] is expected_terminal

        for nested_name, nested_keys in REQUIRED_NESTED_KEYS.items():
            nested_payload = payload[nested_name]
            assert isinstance(nested_payload, dict)
            assert nested_keys.issubset(nested_payload.keys())

        rendered = json.dumps(payload).lower()
        for token in FORBIDDEN_TOKENS:
            assert token not in rendered


def test_processing_status_contract_fixtures_terminal_vs_active_sets() -> None:
    terminal_statuses = {"COMPLETED", "CAPTURE_FAILED", "GRADING_FAILED", "NEEDS_REVIEW"}
    active_statuses = {"WAITING_GRADING", "WAITING_CAPTURE", "CAPTURING", "GRADING"}

    for fixture_name in EXPECTED_FIXTURE_TERMINAL:
        payload = _load_fixture(fixture_name)
        status = str(payload["overall_status"])
        is_terminal = bool(payload["is_terminal"])

        if status in terminal_statuses:
            assert is_terminal is True
        if status in active_statuses:
            assert is_terminal is False
