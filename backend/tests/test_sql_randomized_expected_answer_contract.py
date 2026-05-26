from __future__ import annotations

from app.modules.delivery.repositories.delivery_repository import DeliveryRepository
from app.modules.delivery.services.delivery_service import DeliveryService


def _sql_variant_question(question_template_id: int, *, question_type: str = "TEXTBOX_SQL") -> dict:
    return {
        "question_grading_profile_id": 3000 + question_template_id,
        "question_template_id": question_template_id,
        "input_source": "SEALED_TEXT_ANSWER",
        "max_score": 10,
        "metadata_json": {
            "question_no": 1,
            "authoring_question_type": question_type,
            "render_component": "TEXTAREA",
            "required": True,
            "text_variants": [
                {
                    "variant_code": "SQL-A",
                    "rendered_question_text": "Return only active customers.",
                    "variant_parameters_json": {"dataset": "A", "expected_answer_json": {"leak": True}},
                    "expected_answer_json": {
                        "columns": ["customer_id"],
                        "rows": [[1], [2]],
                        "row_count": 2,
                        "truncated": False,
                    },
                },
                {
                    "variant_code": "SQL-B",
                    "rendered_question_text": "Return only inactive customers.",
                    "variant_parameters_json": {"dataset": "B", "seed": "private-seed"},
                    "expected_answer_json": {
                        "columns": ["customer_id"],
                        "rows": [[3]],
                        "row_count": 1,
                        "truncated": False,
                    },
                },
            ],
        },
        "template_code": "SQL-1",
        "question_type": question_type,
        "title": "Randomized SQL question",
        "template_text": "Write SQL for the selected customer set.",
        "default_score": 10,
    }


def test_randomized_sql_variant_materialization_persists_expected_answer_snapshot() -> None:
    materialized, _seed_hash, prepare_strategy = DeliveryRepository._materialize_runtime_questions(
        questions=[_sql_variant_question(501)],
        exam_session_id=8801,
        exam_version_id=4401,
        randomization_mode="PARAMETERIZED",
    )

    assert prepare_strategy == "TEXT_MANUAL_SESSION_SEEDED"
    question = materialized[0]

    assert question["question_type"] == "SQL_QUERY"
    assert question["variant_code"] in {"SQL-A", "SQL-B"}
    assert "seed" not in question["variant_parameters_json"]
    assert "expected_answer_json" not in question["variant_parameters_json"]

    snapshot = question["generated_expected_answer_snapshot"]
    assert snapshot is not None
    assert snapshot["answer_order"] == 1
    assert snapshot["solution_type"] == "SQL_RESULT"
    assert snapshot["expected_payload"] is None
    assert snapshot["expected_payload_json"]["columns"] == ["customer_id"]
    assert snapshot["expected_hash"]
    assert snapshot["metadata_json"]["snapshot_source"].startswith("variant_")


def test_student_runtime_view_hides_expected_answer_fields_for_sql_question() -> None:
    question = {
        "generated_exam_question_id": 901,
        "original_question_id": 21,
        "source_exam_question_id": None,
        "canonical_section_order": 1,
        "canonical_question_order": 1,
        "display_question_order": 1,
        "question_order": 1,
        "question_code": "SQL-1",
        "question_type": "SQL_QUERY",
        "variant_code": "SQL-A",
        "rendered_question_text": "Return only active customers.",
        "rendered_question_payload_json": {
            "answer_ui": {"ui_mode": "TEXTAREA", "input_source": "SEALED_TEXT_ANSWER"},
            "expected_payload_json": {"rows": [[1]]},
            "expected_answer_json": {"rows": [[1]]},
            "expected_answer_text": "SELECT * FROM customer",
            "expected_hash": "x" * 64,
            "solution_type": "SQL_RESULT",
            "generated_expected_answer": {"private": True},
        },
        "score": 10.0,
    }

    mapped = DeliveryService._student_runtime_question_view(question)

    rendered = mapped["rendered_question_payload_json"]
    assert "expected_payload_json" not in rendered
    assert "expected_answer_json" not in rendered
    assert "expected_answer_text" not in rendered
    assert "expected_hash" not in rendered
    assert "solution_type" not in rendered
    assert "generated_expected_answer" not in rendered
