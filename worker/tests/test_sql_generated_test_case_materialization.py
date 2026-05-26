"""MVQ-4 worker contract tests for explicit single-snapshot SQL scope."""

from __future__ import annotations

from pathlib import Path
import sys


WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.textbox_sql.comparison.expected_payload_parser import parse_expected_result_payload
from worker_runtime.grading.textbox_sql.scoring.question_score_policy import compute_question_score


def test_mvq4_single_generated_expected_answer_snapshot_is_parseable() -> None:
    parsed = parse_expected_result_payload(
        {
            "generated_expected_answer_id": 701,
            "solution_type": "SQL_RESULT",
            "expected_payload": None,
            "expected_payload_json": {
                "columns": ["value"],
                "rows": [[1], [2]],
                "row_count": 2,
                "truncated": False,
            },
            "expected_hash": None,
        }
    )

    assert parsed["ok"] is True
    assert parsed["source"] == "expected_payload_json"
    assert parsed["payload"]["rows"] == [[1], [2]]


def test_mvq4_no_multi_case_aggregation_is_faked_by_question_score_policy() -> None:
    score = compute_question_score(
        {
            "question_grading_task_id": 801,
            "grading_job_id": 11,
            "grading_run_id": 21,
            "comparison_id": 901,
            "comparison_method": "EXACT_RESULT_SET",
            "comparison_status": "MATCH",
            "comparison_payload_json": {
                "public_case_count": 1,
                "hidden_case_count": 2,
                "note": "MVQ-4 keeps single-comparison scoring; no per-case aggregation is applied yet.",
            },
            "mismatch_summary": None,
            "max_score": 5,
        }
    )

    assert score["raw_score"] == 5
    assert score["score_status"] == "SCORED"
    assert score["metadata_json"]["source"] == "s2w4_5_question_score_policy"
