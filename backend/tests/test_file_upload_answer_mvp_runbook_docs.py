"""Static guards for file-upload-answer MVP runbook and API-first sequence."""

from __future__ import annotations

from conftest import CONTRACTS_DEPLOYMENT_ROOT


RUNBOOK = CONTRACTS_DEPLOYMENT_ROOT / "file_upload_answer_mvp_runbook.md"


REQUIRED_TERMS = [
    "Visual paper asset",
    "Student answer file asset",
    "Capture artifact",
    "POST /api/v1/master-data/exams/{exam_id}/versions/{exam_version_id}/paper-assets",
    "PUT /api/v1/master-data/exam-versions/{exam_version_id}/delivery-profile",
    "POST /api/v1/master-data/exam-versions/{exam_version_id}/question-grading-profiles",
    "POST /api/v1/delivery/setup/sittings",
    "GET /api/v1/exam-sessions/{session_id}/taking-payload",
    "POST /api/v1/submissions/{submission_id}/answers/{generated_exam_question_id}/file",
    "POST /api/v1/submissions/{submission_id}/seal",
    "GET /api/v1/grading/manual-review/file-answers",
    "GET /api/v1/grading/manual-review/file-answers/{sealed_answer_id}/content",
    "POST /api/v1/grading/manual-review/file-answers/{sealed_answer_id}/score",
]


MOJIBAKE_MARKERS = [
    "Ã„â€˜",
    "Ãƒ",
    "Ã¡Â»",
]


def test_runbook_exists() -> None:
    assert RUNBOOK.exists(), f"Missing runbook: {RUNBOOK}"


def test_runbook_covers_api_first_workflow_and_sequences() -> None:
    content = RUNBOOK.read_text(encoding="utf-8")
    for term in REQUIRED_TERMS:
        assert term in content
    assert "Frontend only calls backend `/api/v1`" in content
    assert "does not call worker or database directly" in content


def test_runbook_utf8_vietnamese_has_no_mojibake() -> None:
    content = RUNBOOK.read_text(encoding="utf-8")
    assert "Submit by attached file" in content
    assert "Manual rubric review" in content
    for marker in MOJIBAKE_MARKERS:
        assert marker not in content
