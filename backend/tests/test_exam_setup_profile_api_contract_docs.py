"""Static contract guards for exam setup delivery/grading profile APIs."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DELIVERY_PROFILE_CONTRACT = REPO_ROOT / "docs" / "api" / "exam_version_delivery_profile_api.md"
QUESTION_GRADING_PROFILE_CONTRACT = REPO_ROOT / "docs" / "api" / "question_grading_profile_api.md"
ATOMIC_FILE_UPLOAD_CONFIG_CONTRACT = REPO_ROOT / "docs" / "api" / "file_upload_exam_version_configuration_api.md"
QUESTION_AUTHORING_CONTRACT = REPO_ROOT / "docs" / "api" / "exam_version_question_authoring_api.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_exam_setup_contract_docs_exist() -> None:
    assert DELIVERY_PROFILE_CONTRACT.exists(), f"Missing contract doc: {DELIVERY_PROFILE_CONTRACT}"
    assert QUESTION_GRADING_PROFILE_CONTRACT.exists(), f"Missing contract doc: {QUESTION_GRADING_PROFILE_CONTRACT}"
    assert ATOMIC_FILE_UPLOAD_CONFIG_CONTRACT.exists(), f"Missing contract doc: {ATOMIC_FILE_UPLOAD_CONFIG_CONTRACT}"
    assert QUESTION_AUTHORING_CONTRACT.exists(), f"Missing contract doc: {QUESTION_AUTHORING_CONTRACT}"


def test_delivery_profile_contract_documents_required_endpoints() -> None:
    content = _read(DELIVERY_PROFILE_CONTRACT)
    assert "Base path: `/api/v1`" in content
    assert "GET `/master-data/exam-versions/{exam_version_id}/delivery-profile`" in content
    assert "PUT `/master-data/exam-versions/{exam_version_id}/delivery-profile`" in content
    assert "FILE_BASED" in content
    assert "FILE_ARTIFACT" in content


def test_question_grading_profile_contract_documents_required_endpoints() -> None:
    content = _read(QUESTION_GRADING_PROFILE_CONTRACT)
    assert "Base path: `/api/v1`" in content
    assert "GET `/master-data/exam-versions/{exam_version_id}/question-grading-profiles`" in content
    assert "POST `/master-data/exam-versions/{exam_version_id}/question-grading-profiles`" in content
    assert "PATCH `/master-data/question-grading-profiles/{question_grading_profile_id}`" in content
    assert "POST `/master-data/question-grading-profiles/{question_grading_profile_id}/retire`" in content
    assert "POST `/master-data/exam-versions/{exam_version_id}/file-upload-placeholder-question`" in content
    assert "POST `/master-data/exam-versions/{exam_version_id}/configure-file-upload-manual-grading`" in content
    assert "MANUAL_RUBRIC" in content
    assert "SEALED_FILE_REF" in content


def test_atomic_file_upload_contract_documents_endpoint_and_profile_rules() -> None:
    content = _read(ATOMIC_FILE_UPLOAD_CONFIG_CONTRACT)
    assert "Base path: `/api/v1`" in content
    assert "POST /master-data/exam-versions/{exam_version_id}/configure-file-upload-manual-grading" in content
    assert "SEALED_FILE_REF" in content
    assert "MANUAL_RUBRIC" in content
    assert "FILE_BASED" in content
    assert "FILE_ARTIFACT" in content
    assert "storage_relative_path" in content
    assert "internal_storage_key" in content


def test_question_authoring_contract_documents_version_scoped_workflow() -> None:
    content = _read(QUESTION_AUTHORING_CONTRACT)
    assert "Base path: `/api/v1`" in content
    assert "GET /master-data/exam-versions/{exam_version_id}/questions" in content
    assert "POST /master-data/exam-versions/{exam_version_id}/questions" in content
    assert "PATCH /master-data/exam-versions/{exam_version_id}/questions/{question_template_id}" in content
    assert "TEXTAREA" in content
    assert "TEXTBOX_SQL" in content
    assert "FILE_UPLOAD" in content
    assert "MCQ_SINGLE" in content
    assert "Do not infer student UI from grading engine name alone." in content


def test_contract_docs_do_not_have_common_mojibake_markers() -> None:
    combined = (
        _read(DELIVERY_PROFILE_CONTRACT)
        + "\n"
        + _read(QUESTION_GRADING_PROFILE_CONTRACT)
        + "\n"
        + _read(ATOMIC_FILE_UPLOAD_CONFIG_CONTRACT)
        + "\n"
        + _read(QUESTION_AUTHORING_CONTRACT)
    )
    for marker in ["Ã„â€˜", "Ã¡Â»", "Ãƒ", "?Ã­nh"]:
        assert marker not in combined
