from __future__ import annotations

from app.modules.delivery.repositories.delivery_repository import DeliveryRepository


def _question(question_template_id: int, question_no: int, *, shuffle_options: bool = True) -> dict:
    return {
        "question_grading_profile_id": question_template_id + 1000,
        "question_template_id": question_template_id,
        "input_source": "SEALED_JSON_ANSWER",
        "max_score": 1.0,
        "metadata_json": {
            "question_no": question_no,
            "authoring_question_type": "MCQ_SINGLE",
            "render_component": "RADIO_GROUP",
            "required": True,
            "shuffle_options": shuffle_options,
            "mcq_options": ["A. 10", "B. 20", "C. 30", "D. 40"],
        },
        "template_code": f"Q{question_no}",
        "question_type": "MCQ_SINGLE",
        "title": f"Question {question_no}",
        "template_text": f"Question text {question_no}",
        "default_score": 1.0,
    }


def test_generated_multiple_choice_options_are_deterministic_for_same_session() -> None:
    questions = [_question(101, 1)]

    first, first_seed, first_strategy = DeliveryRepository._materialize_runtime_questions(
        questions=questions,
        exam_session_id=501,
        exam_version_id=9001,
        randomization_mode="FIXED",
        shuffle_questions=False,
        shuffle_options=True,
    )
    second, second_seed, second_strategy = DeliveryRepository._materialize_runtime_questions(
        questions=questions,
        exam_session_id=501,
        exam_version_id=9001,
        randomization_mode="FIXED",
        shuffle_questions=False,
        shuffle_options=True,
    )

    assert first_seed == second_seed
    assert first_strategy == "MULTIPLE_CHOICE_OPTION_SESSION_SEEDED"
    assert second_strategy == first_strategy
    assert first[0]["generated_options"] == second[0]["generated_options"]
    assert [option["option_label"] for option in first[0]["generated_options"]] == ["A", "B", "C", "D"]
    assert sorted(option["original_option_id"] for option in first[0]["generated_options"]) == [1, 2, 3, 4]


def test_multiple_choice_without_option_shuffle_preserves_canonical_option_order() -> None:
    questions = [_question(201, 1)]

    materialized, _seed_hash, strategy = DeliveryRepository._materialize_runtime_questions(
        questions=questions,
        exam_session_id=777,
        exam_version_id=9001,
        randomization_mode="FIXED",
        shuffle_questions=False,
        shuffle_options=False,
    )

    generated_options = materialized[0]["generated_options"]

    assert strategy == "FIXED_PROFILE_ORDER"
    assert [option["original_option_id"] for option in generated_options] == [1, 2, 3, 4]
    assert [option["option_order"] for option in generated_options] == [1, 2, 3, 4]
    assert [option["rendered_option_text"] for option in generated_options] == ["A. 10", "B. 20", "C. 30", "D. 40"]
