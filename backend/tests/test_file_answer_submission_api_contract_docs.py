"""Static contract guards for file-answer submission API documentation."""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
FILE_ANSWER_CONTRACT = REPO_ROOT / "docs" / "api" / "file_answer_submission_api.md"
DELIVERY_CONTRACT = REPO_ROOT / "docs" / "api" / "delivery_submission_api.md"

REQUIRED_ENDPOINTS = [
    "POST /submissions/{submission_id}/answers/{generated_exam_question_id}/file",
    "GET /submissions/{submission_id}/answers/{generated_exam_question_id}/file",
    "GET /submissions/{submission_id}/answers/{generated_exam_question_id}/file/content",
    "DELETE /submissions/{submission_id}/answers/{generated_exam_question_id}/file",
    "POST /submissions/{submission_id}/seal",
]

REQUIRED_ERROR_CODES = [
    "SUBMISSION_NOT_FOUND",
    "SUBMISSION_NOT_OWNED",
    "SUBMISSION_ALREADY_SEALED",
    "QUESTION_NOT_FOUND",
    "QUESTION_NOT_FILE_UPLOAD",
    "FILE_TOO_LARGE",
    "UNSUPPORTED_FILE_TYPE",
    "FILE_UPLOAD_NOT_CONFIGURED",
    "FILE_STORAGE_ERROR",
]

REQUIRED_POLICY_TOKENS = [
    ".zip",
    ".pdf",
    ".docx",
    ".xlsx",
    ".csv",
    ".sql",
    ".txt",
    ".json",
    "application/x-zip-compressed",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/csv",
    "application/sql",
    "application/octet-stream",
    "text/json",
]

FORBIDDEN_PAYLOAD_FIELDS = [
    '"expected_answer"',
    '"generated_expected_answer"',
    '"reference_solution"',
    '"solution_sql"',
]

MOJIBAKE_MARKERS = ["Ä‘", "á»", "Ã", "?ính", "Ã„â€˜", "Ãƒ", "Ã¡Â»"]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _json_blocks(text: str) -> list[str]:
    return re.findall(r"```json\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)


def test_file_answer_contract_doc_exists() -> None:
    assert FILE_ANSWER_CONTRACT.exists(), f"Missing contract doc: {FILE_ANSWER_CONTRACT}"


def test_required_file_answer_endpoints_are_documented() -> None:
    content = _read(FILE_ANSWER_CONTRACT)
    assert "Base path: `/api/v1`" in content
    for endpoint in REQUIRED_ENDPOINTS:
        assert endpoint in content


def test_required_error_codes_are_documented() -> None:
    content = _read(FILE_ANSWER_CONTRACT)
    for code in REQUIRED_ERROR_CODES:
        assert code in content


def test_canonical_file_policy_is_documented() -> None:
    content = _read(FILE_ANSWER_CONTRACT)
    assert "Canonical file policy (backend authoritative)" in content
    for token in REQUIRED_POLICY_TOKENS:
        assert token in content


def test_delivery_contract_file_policy_example_matches_supported_types() -> None:
    content = _read(DELIVERY_CONTRACT)
    for token in REQUIRED_POLICY_TOKENS:
        assert token in content


def test_taking_payload_examples_do_not_add_expected_answer_fields() -> None:
    file_contract_blocks = _json_blocks(_read(FILE_ANSWER_CONTRACT))
    delivery_contract_blocks = _json_blocks(_read(DELIVERY_CONTRACT))
    candidate_blocks = [
        block
        for block in (file_contract_blocks + delivery_contract_blocks)
        if "question_type" in block and ("answer_ui" in block or "questions" in block)
    ]
    assert candidate_blocks, "No taking-payload-like JSON blocks found for contract validation"
    joined = "\n".join(candidate_blocks).lower()
    for forbidden in FORBIDDEN_PAYLOAD_FIELDS:
        assert forbidden.lower() not in joined


def test_docs_do_not_document_absolute_storage_paths() -> None:
    content = _read(FILE_ANSWER_CONTRACT)
    assert "storage_relative_path" not in content
    assert "internal_storage_key" not in content
    assert re.search(r"[A-Za-z]:\\\\", content) is None
    assert "/var/private/" not in content
    assert "/home/" not in content
def test_contract_uses_sealed_file_ref_for_direct_file_upload() -> None:
    content = _read(FILE_ANSWER_CONTRACT)
    assert "input_source = SEALED_FILE_REF" in content
    assert "Không dùng `MANUAL` làm `input_source`" in content
    assert "MANUAL_RUBRIC" in content
    assert "phương thức chấm" in content


def test_contract_separates_visual_student_and_capture_artifacts() -> None:
    content = _read(FILE_ANSWER_CONTRACT)
    assert "Visual paper asset" in content
    assert "Student answer file asset" in content
    assert "Capture artifact" in content


def test_utf8_vietnamese_labels_are_preserved_without_mojibake() -> None:
    file_content = _read(FILE_ANSWER_CONTRACT)
    delivery_content = _read(DELIVERY_CONTRACT)
    assert "Đính kèm bài làm" in file_content
    assert "Đính kèm bài làm" in delivery_content
    combined = file_content + "\n" + delivery_content
    for marker in MOJIBAKE_MARKERS:
        assert marker not in combined
