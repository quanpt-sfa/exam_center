"""Smoke-level workflow guard for visual-paper + file-upload answer MVP."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNBOOK = REPO_ROOT / "docs" / "file_upload_answer_workflow_runbook.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_runbook_exists() -> None:
    assert RUNBOOK.exists(), f"Missing runbook: {RUNBOOK}"


def test_runbook_contains_required_workflow_assertions() -> None:
    content = _read(RUNBOOK)
    required = [
        "question_grading_profile.input_source = SEALED_FILE_REF",
        "taking-payload.answer_ui.ui_mode = FILE_UPLOAD",
        "Upload tạo `answer_state.FILE_REF`",
        "Seal snapshot `FILE_REF`",
        "Missing required file block seal",
        "Dispatch route `MANUAL_REVIEW_REQUIRED`",
        "Manual review list có sealed file answer",
        "Không lộ expected answer",
        "Không lộ internal storage key/absolute path",
    ]
    for item in required:
        assert item in content


def test_runbook_has_api_sequences_for_admin_student_staff() -> None:
    content = _read(RUNBOOK)
    endpoints = [
        "POST /api/v1/master-data/exam-versions/{exam_version_id}/file-upload-placeholder-question",
        "GET /api/v1/exam-sessions/{session_id}/taking-payload",
        "POST /api/v1/submissions/{submission_id}/answers/{generated_exam_question_id}/file",
        "POST /api/v1/submissions/{submission_id}/seal",
        "GET /api/v1/grading/manual-review/file-answers",
        "GET /api/v1/grading/manual-review/file-answers/{sealed_answer_id}/content",
        "POST /api/v1/grading/manual-review/file-answers/{sealed_answer_id}/score",
    ]
    for endpoint in endpoints:
        assert endpoint in content


def test_runbook_utf8_no_common_mojibake_markers() -> None:
    content = _read(RUNBOOK)
    for marker in ["Ä‘", "á»", "Ã", "?ính", "Ã„â€˜", "Ã¡Â»", "Ãƒ"]:
        assert marker not in content
