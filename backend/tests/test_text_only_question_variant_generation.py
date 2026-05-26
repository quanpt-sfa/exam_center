from __future__ import annotations

from app.modules.delivery.repositories.delivery_repository import DeliveryRepository


def _question(
    question_template_id: int,
    question_no: int,
    *,
    template_text: str,
    variant_prefix: str,
    authoring_question_type: str = "TEXTAREA",
) -> dict:
    return {
        "question_grading_profile_id": 1000 + question_template_id,
        "question_template_id": question_template_id,
        "input_source": "SEALED_TEXT_ANSWER",
        "max_score": 5,
        "metadata_json": {
            "question_no": question_no,
            "authoring_question_type": authoring_question_type,
            "text_variants": [
                {
                    "variant_code": f"{variant_prefix}-A",
                    "rendered_question_text": f"{template_text} variant A",
                    "variant_parameters_json": {"public_label": "A", "answer_key": "secret-a"},
                },
                {
                    "variant_code": f"{variant_prefix}-B",
                    "rendered_question_text": f"{template_text} variant B",
                    "variant_parameters_json": {"public_label": "B", "rubric": {"private": True}},
                },
                {
                    "variant_code": f"{variant_prefix}-C",
                    "rendered_question_text": f"{template_text} variant C",
                    "variant_parameters_json": {"public_label": "C", "seed": "do-not-persist"},
                },
            ],
        },
        "template_code": f"Q{question_no}",
        "question_type": authoring_question_type,
        "title": f"Question {question_no}",
        "template_text": template_text,
        "default_score": 5,
    }


def test_materialize_runtime_questions_is_deterministic_per_session() -> None:
    questions = [
        _question(101, 1, template_text="Explain asset valuation", variant_prefix="VAL"),
        _question(102, 2, template_text="Explain cash flow", variant_prefix="CASH", authoring_question_type="MANUAL_TEXT"),
        _question(103, 3, template_text="Explain audit trail", variant_prefix="AUD"),
        _question(104, 4, template_text="Explain variance", variant_prefix="VAR"),
    ]

    first, seed_hash, prepare_strategy = DeliveryRepository._materialize_runtime_questions(
        questions=questions,
        exam_session_id=7001,
        exam_version_id=301,
        randomization_mode="PARAMETERIZED",
    )
    second, second_seed_hash, second_prepare_strategy = DeliveryRepository._materialize_runtime_questions(
        questions=questions,
        exam_session_id=7001,
        exam_version_id=301,
        randomization_mode="PARAMETERIZED",
    )

    assert prepare_strategy == "TEXT_MANUAL_SESSION_SEEDED"
    assert second_prepare_strategy == "TEXT_MANUAL_SESSION_SEEDED"
    assert seed_hash == second_seed_hash
    assert [
        (item["question_template_id"], item["question_order"], item["display_question_order"], item["variant_code"], item["rendered_question_text"])
        for item in first
    ] == [
        (item["question_template_id"], item["question_order"], item["display_question_order"], item["variant_code"], item["rendered_question_text"])
        for item in second
    ]
    assert all(item["question_order"] == index for index, item in enumerate(first, start=1))
    assert all(item["display_question_order"] == index for index, item in enumerate(first, start=1))
    assert all("answer_key" not in item["variant_parameters_json"] for item in first)
    assert all("rubric" not in item["variant_parameters_json"] for item in first)
    assert all("seed" not in item["variant_parameters_json"] for item in first)


def test_materialize_runtime_questions_changes_variant_or_order_across_sessions() -> None:
    questions = [
        _question(201, 1, template_text="Explain bank reconciliation", variant_prefix="BR"),
        _question(202, 2, template_text="Explain posting logic", variant_prefix="PL", authoring_question_type="MANUAL_TEXT"),
        _question(203, 3, template_text="Explain accrual timing", variant_prefix="AT"),
        _question(204, 4, template_text="Explain stock count", variant_prefix="SC"),
    ]

    first, _, _ = DeliveryRepository._materialize_runtime_questions(
        questions=questions,
        exam_session_id=7101,
        exam_version_id=302,
        randomization_mode="PARAMETERIZED",
    )
    second, _, _ = DeliveryRepository._materialize_runtime_questions(
        questions=questions,
        exam_session_id=7102,
        exam_version_id=302,
        randomization_mode="PARAMETERIZED",
    )

    first_signature = [(item["question_template_id"], item["variant_code"], item["question_order"]) for item in first]
    second_signature = [(item["question_template_id"], item["variant_code"], item["question_order"]) for item in second]

    assert first_signature != second_signature


def test_materialize_runtime_questions_keeps_canonical_order_for_fixed_mode() -> None:
    questions = [
        _question(301, 1, template_text="Explain depreciation", variant_prefix="DEP"),
        _question(302, 2, template_text="Explain journal entry", variant_prefix="JE", authoring_question_type="MANUAL_TEXT"),
    ]

    materialized, _, prepare_strategy = DeliveryRepository._materialize_runtime_questions(
        questions=questions,
        exam_session_id=7201,
        exam_version_id=401,
        randomization_mode="FIXED",
    )

    assert prepare_strategy == "FIXED_PROFILE_ORDER"
    assert [item["question_template_id"] for item in materialized] == [301, 302]
    assert [item["question_order"] for item in materialized] == [1, 2]
    assert materialized[0]["canonical_question_order"] == 1
    assert materialized[1]["canonical_question_order"] == 2