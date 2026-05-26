from __future__ import annotations

from pathlib import Path

from app.modules.delivery.mappers.delivery_mapper import map_generated_question_row


def test_mvq1_migration_declares_original_linkage_foundation() -> None:
    migration = (
        Path(__file__).resolve().parents[3]
        / "db"
        / "postgres"
        / "01_migrations"
        / "0136_add_generated_question_original_linkage_foundation.sql"
    )
    text = migration.read_text(encoding="utf-8")

    assert "ADD COLUMN IF NOT EXISTS original_question_id" in text
    assert "ADD COLUMN IF NOT EXISTS source_exam_question_id" in text
    assert "ADD COLUMN IF NOT EXISTS canonical_question_order" in text
    assert "ADD COLUMN IF NOT EXISTS display_question_order" in text
    assert "ADD COLUMN IF NOT EXISTS question_grading_profile_id" in text
    assert "display_question_order = COALESCE(display_question_order, question_order)" in text
    assert "variant_parameters_json" in text


def test_generated_question_mapper_prefers_display_order_and_sanitizes_sensitive_payload() -> None:
    mapped = map_generated_question_row(
        {
            "generated_exam_question_id": 501,
            "original_question_id": 101,
            "source_exam_question_id": None,
            "canonical_section_order": 2,
            "canonical_question_order": 4,
            "display_question_order": 7,
            "question_order": 3,
            "question_code": "Q-7",
            "question_type": "MULTIPLE_CHOICE",
            "variant_code": "B",
            "rendered_question_text": "Pick one",
            "rendered_question_payload_json": {
                "prompt": "Pick one",
                "correct_option_ids": [2],
                "hidden_tests": [{"name": "secret"}],
                "internal_seed": "abc",
                "answer_ui": {"required": True},
            },
            "score": 2,
        }
    )

    assert mapped["generated_exam_question_id"] == 501
    assert mapped["original_question_id"] == 101
    assert mapped["canonical_section_order"] == 2
    assert mapped["canonical_question_order"] == 4
    assert mapped["display_question_order"] == 7
    assert mapped["question_order"] == 7
    assert mapped["variant_code"] == "B"
    assert mapped["rendered_question_payload_json"] == {
        "prompt": "Pick one",
        "answer_ui": {"required": True},
    }