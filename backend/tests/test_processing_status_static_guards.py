"""Static guard tests for S2W-6 processing status repository safety rules."""

from __future__ import annotations

import re
from pathlib import Path


def _repository_source() -> str:
    path = Path(__file__).resolve().parents[1] / "app" / "modules" / "submission" / "repositories" / "submission_processing_status_repository.py"
    return path.read_text(encoding="utf-8")


def _submission_api_source() -> str:
    path = Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "submission.py"
    return path.read_text(encoding="utf-8")


def _submission_use_case_source() -> str:
    path = Path(__file__).resolve().parents[1] / "app" / "modules" / "submission" / "use_cases" / "submission_runtime.py"
    return path.read_text(encoding="utf-8")


def _processing_status_endpoint_block() -> str:
    source = _submission_api_source().lower()
    match = re.search(
        r"def\s+get_submission_processing_status\s*\(.*?(?=\n\n@router|\Z)",
        source,
        flags=re.DOTALL,
    )
    assert match is not None
    return match.group(0)


def test_processing_status_repository_and_endpoint_do_not_reference_forbidden_read_columns() -> None:
    source = _repository_source().lower()
    endpoint_block = _processing_status_endpoint_block()
    forbidden_tokens = [
        "answer_state",
        "original_answer_text",
        "answer_text",
        "sealed_answer_text",
        "raw_answer",
        "answer_payload_json",
        "row_payload_json",
        "raw_payload_json",
    ]
    for token in forbidden_tokens:
        assert token not in source
        assert token not in endpoint_block


def test_processing_status_repository_does_not_reference_capture_dataset_row_table() -> None:
    source = _repository_source().lower()
    assert "capture_dataset_row" not in source


def test_processing_status_repository_avoids_select_star_from_sensitive_tables() -> None:
    source = _repository_source().lower()
    assert re.search(r"select\s+\*\s+from\s+submission\.answer_state", source) is None
    assert re.search(r"select\s+\*\s+from\s+submission\.sealed_answer", source) is None
    assert re.search(r"select\s+\*\s+from\s+capture\.capture_dataset_row", source) is None


def test_processing_status_repository_and_endpoint_contain_no_mutation_sql() -> None:
    repository_source = _repository_source().lower()
    endpoint_block = _processing_status_endpoint_block()
    forbidden_patterns = [
        r"\binsert\s+into\b",
        r"\bupdate\b",
        r"\bdelete\s+from\b",
        r"\btruncate\b",
        r"\balter\s+table\b",
        r"\bdrop\s+table\b",
    ]
    for pattern in forbidden_patterns:
        assert re.search(pattern, repository_source) is None
        assert re.search(pattern, endpoint_block) is None


def test_processing_status_endpoint_block_does_not_reference_answer_state_or_raw_payloads() -> None:
    block = _processing_status_endpoint_block()
    assert "answer_state" not in block
    assert "answer_text" not in block
    assert "answer_payload_json" not in block
    assert "row_payload_json" not in block


def test_processing_status_endpoint_keeps_current_user_dependency_and_passes_it_to_use_case() -> None:
    block = _processing_status_endpoint_block()
    assert "_: dict = depends(require_submission_access)" not in block
    assert "current_user: dict = depends(require_submission_access)" in block
    assert "current_user=current_user" in block
    assert "access_service=access_service" in block


def test_processing_status_use_case_enforces_submission_access_before_status_read() -> None:
    source = _submission_use_case_source().lower()
    match = re.search(
        r"def\s+execute_get_submission_processing_status\s*\(.*?(?=\n\ndef\s+|\Z)",
        source,
        flags=re.DOTALL,
    )
    assert match is not None
    block = match.group(0)
    assert "assert_submission_access" in block
    assert "current_user" in block