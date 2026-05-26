"""Service layer for S2W-4.4 expected-vs-actual comparison writes."""

from __future__ import annotations

from typing import Any

from worker_runtime.grading.textbox_sql.comparison.expected_payload_parser import (
    parse_expected_result_payload,
)
from worker_runtime.grading.textbox_sql.comparison.result_set_comparator import (
    compare_result_sets,
)
from worker_runtime.grading.textbox_sql_comparison_repository import (
    TextboxSqlComparisonRepository,
)


_SUPPORTED_METHODS = {"EXACT_RESULT_SET", "ORDER_INSENSITIVE_RESULT_SET"}
_ALLOWED_DB_METHODS = {
    "EXACT_RESULT_SET",
    "ORDER_INSENSITIVE_RESULT_SET",
    "NUMERIC_TOLERANCE",
    "TEXT_RULE",
    "ACCOUNTING_BALANCE_CHECK",
    "LEDGER_RECONCILIATION",
    "API_FIELD_MATCH",
    "FILE_ARTIFACT_MATCH",
    "MANUAL_RUBRIC",
    "CUSTOM",
}


class TextboxSqlComparisonService:
    """Processes one comparison candidate at a time."""

    def __init__(
        self,
        *,
        repository: TextboxSqlComparisonRepository | None = None,
    ) -> None:
        self._repository = repository or TextboxSqlComparisonRepository()

    def process_next_comparison(
        self,
        grading_job_id: int,
        grading_run_id: int,
        worker_id: str | None = None,
    ) -> dict[str, Any]:
        candidate = self._repository.claim_next_comparison_candidate(
            grading_job_id=int(grading_job_id),
            grading_run_id=int(grading_run_id),
            worker_id=worker_id,
        )
        if candidate is None:
            return {
                "processed": False,
                "reason": "no_comparison_candidate",
            }

        method_raw = None
        profile_snapshot_json = candidate.get("profile_snapshot_json")
        if isinstance(profile_snapshot_json, dict):
            method_raw = profile_snapshot_json.get("comparison_method")

        method = str(method_raw or "").strip().upper()
        db_method = self._safe_db_method(method)

        actual_result_type = str(candidate.get("actual_result_type") or "")

        if actual_result_type == "SQL_RUNTIME_ERROR":
            metadata = candidate.get("actual_result_metadata_json")
            error_code = metadata.get("error_code") if isinstance(metadata, dict) else None
            comparison_result = {
                "comparison_method": db_method,
                "comparison_status": "ERROR",
                "expected_hash": candidate.get("expected_hash"),
                "actual_hash": candidate.get("actual_result_hash"),
                "mismatch_summary": "SQL runtime error result cannot be compared as result set.",
                "comparison_payload_json": {
                    "method": db_method,
                    "comparison_version": "s2w4_4_v1",
                    "actual_result_id": int(candidate.get("actual_result_id") or 0),
                    "generated_expected_answer_id": candidate.get("generated_expected_answer_id"),
                    "expected_source": "not_compared_due_runtime_error",
                    "column_match": False,
                    "row_match": False,
                    "expected_row_count": 0,
                    "actual_row_count": int(candidate.get("actual_result_row_count") or 0),
                    "mismatch_type": "actual_runtime_error",
                    "sample_mismatches": [],
                    "actual_result_type": actual_result_type,
                    "actual_error_code": str(error_code) if error_code is not None else None,
                },
            }
            persisted = self._repository.write_comparison(
                candidate=candidate,
                comparison=comparison_result,
                worker_id=worker_id,
            )
            return {
                "processed": True,
                "question_grading_task_id": int(persisted["question_grading_task_id"]),
                "comparison_id": int(persisted["comparison_id"]),
                "comparison_method": str(persisted["comparison_method"]),
                "comparison_status": str(persisted["comparison_status"]),
            }

        if actual_result_type != "SQL_RESULT_SET":
            comparison_result = {
                "comparison_method": db_method,
                "comparison_status": "NEEDS_REVIEW",
                "expected_hash": candidate.get("expected_hash"),
                "actual_hash": candidate.get("actual_result_hash"),
                "mismatch_summary": "Actual result type is unsupported for S2W-4.4 comparison.",
                "comparison_payload_json": {
                    "method": db_method,
                    "comparison_version": "s2w4_4_v1",
                    "actual_result_id": int(candidate.get("actual_result_id") or 0),
                    "generated_expected_answer_id": candidate.get("generated_expected_answer_id"),
                    "expected_source": "unsupported_actual_result_type",
                    "column_match": False,
                    "row_match": False,
                    "expected_row_count": 0,
                    "actual_row_count": int(candidate.get("actual_result_row_count") or 0),
                    "mismatch_type": "unsupported_actual_result_type",
                    "sample_mismatches": [],
                    "actual_result_type": actual_result_type,
                },
            }
            persisted = self._repository.write_comparison(
                candidate=candidate,
                comparison=comparison_result,
                worker_id=worker_id,
            )
            return {
                "processed": True,
                "question_grading_task_id": int(persisted["question_grading_task_id"]),
                "comparison_id": int(persisted["comparison_id"]),
                "comparison_method": str(persisted["comparison_method"]),
                "comparison_status": str(persisted["comparison_status"]),
            }

        if method not in _SUPPORTED_METHODS:
            comparison_result = {
                "comparison_method": db_method,
                "comparison_status": "NEEDS_REVIEW",
                "expected_hash": candidate.get("expected_hash"),
                "actual_hash": candidate.get("actual_result_hash"),
                "mismatch_summary": "Unsupported comparison method for S2W-4.4 result-set comparator.",
                "comparison_payload_json": {
                    "method": db_method,
                    "comparison_version": "s2w4_4_v1",
                    "actual_result_id": int(candidate.get("actual_result_id") or 0),
                    "generated_expected_answer_id": candidate.get("generated_expected_answer_id"),
                    "expected_source": "unsupported_method",
                    "column_match": False,
                    "row_match": False,
                    "expected_row_count": 0,
                    "actual_row_count": int(candidate.get("actual_result_row_count") or 0),
                    "mismatch_type": "unsupported_method",
                    "sample_mismatches": [{"method": method or None}],
                },
            }
            persisted = self._repository.write_comparison(
                candidate=candidate,
                comparison=comparison_result,
                worker_id=worker_id,
            )
            return {
                "processed": True,
                "question_grading_task_id": int(persisted["question_grading_task_id"]),
                "comparison_id": int(persisted["comparison_id"]),
                "comparison_method": str(persisted["comparison_method"]),
                "comparison_status": str(persisted["comparison_status"]),
            }

        parse_result = parse_expected_result_payload(
            {
                "generated_expected_answer_id": candidate.get("generated_expected_answer_id"),
                "solution_type": candidate.get("solution_type"),
                "expected_payload": candidate.get("expected_payload"),
                "expected_payload_json": candidate.get("expected_payload_json"),
                "expected_hash": candidate.get("expected_hash"),
            }
        )

        actual_payload = candidate.get("actual_result_payload_json")
        actual_payload = actual_payload if isinstance(actual_payload, dict) else None

        if not bool(parse_result.get("ok")):
            comparison_result = {
                "comparison_method": db_method,
                "comparison_status": "NEEDS_REVIEW",
                "expected_hash": parse_result.get("expected_hash"),
                "actual_hash": candidate.get("actual_result_hash"),
                "mismatch_summary": "Expected payload cannot be parsed for result-set comparison.",
                "comparison_payload_json": {
                    "method": db_method,
                    "comparison_version": "s2w4_4_v1",
                    "actual_result_id": int(candidate.get("actual_result_id") or 0),
                    "generated_expected_answer_id": candidate.get("generated_expected_answer_id"),
                    "expected_source": str(parse_result.get("source") or "unknown"),
                    "column_match": False,
                    "row_match": False,
                    "expected_row_count": 0,
                    "actual_row_count": int(candidate.get("actual_result_row_count") or 0),
                    "mismatch_type": "expected_payload_unparseable",
                    "sample_mismatches": [
                        {
                            "error_code": parse_result.get("error_code"),
                            "error_message": parse_result.get("error_message"),
                        }
                    ],
                },
            }
            persisted = self._repository.write_comparison(
                candidate=candidate,
                comparison=comparison_result,
                worker_id=worker_id,
            )
            return {
                "processed": True,
                "question_grading_task_id": int(persisted["question_grading_task_id"]),
                "comparison_id": int(persisted["comparison_id"]),
                "comparison_method": str(persisted["comparison_method"]),
                "comparison_status": str(persisted["comparison_status"]),
            }

        compare_result = compare_result_sets(
            parse_result.get("payload"),
            actual_payload,
            method,
        )

        compare_payload = compare_result.get("comparison_payload_json")
        if isinstance(compare_payload, dict):
            compare_payload = dict(compare_payload)
        else:
            compare_payload = {}

        compare_payload["actual_result_id"] = int(candidate.get("actual_result_id") or 0)
        compare_payload["generated_expected_answer_id"] = candidate.get("generated_expected_answer_id")
        compare_payload["expected_source"] = str(parse_result.get("source") or "unknown")

        comparison_result = {
            "comparison_method": db_method,
            "comparison_status": str(compare_result.get("comparison_status") or "NEEDS_REVIEW"),
            "expected_hash": parse_result.get("expected_hash") or compare_result.get("expected_hash"),
            "actual_hash": candidate.get("actual_result_hash") or compare_result.get("actual_hash"),
            "mismatch_summary": str(compare_result.get("mismatch_summary") or ""),
            "comparison_payload_json": compare_payload,
        }

        persisted = self._repository.write_comparison(
            candidate=candidate,
            comparison=comparison_result,
            worker_id=worker_id,
        )

        return {
            "processed": True,
            "question_grading_task_id": int(persisted["question_grading_task_id"]),
            "comparison_id": int(persisted["comparison_id"]),
            "comparison_method": str(persisted["comparison_method"]),
            "comparison_status": str(persisted["comparison_status"]),
        }

    def _safe_db_method(self, method: str) -> str:
        normalized = str(method or "").strip().upper()
        if normalized in _ALLOWED_DB_METHODS:
            return normalized
        return "CUSTOM"
