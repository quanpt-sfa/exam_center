from __future__ import annotations

from app.modules.delivery.repositories.delivery_repository import DeliveryRepository
from app.modules.delivery.services.delivery_service import DeliveryService


def _file_upload_variant_question(question_template_id: int) -> dict:
    return {
        "question_grading_profile_id": 4100 + question_template_id,
        "question_template_id": question_template_id,
        "input_source": "SEALED_FILE_REF",
        "max_score": 10,
        "metadata_json": {
            "question_no": 2,
            "authoring_question_type": "FILE_UPLOAD",
            "render_component": "FILE_UPLOAD",
            "required": True,
            "allowed_extensions": [".zip", ".pdf"],
            "allowed_mime_types": ["application/zip", "application/pdf"],
            "max_file_size_bytes": 4096,
            "upload_instructions": "Upload one archive that contains your final workbook.",
            "text_variants": [
                {
                    "variant_code": "FILE-A",
                    "rendered_question_text": "Upload the January reconciliation package.",
                    "variant_parameters_json": {
                        "public_label": "January",
                        "internal_storage_key": "do-not-leak",
                    },
                    "allowed_extensions": [".zip"],
                    "allowed_mime_types": ["application/zip"],
                    "max_file_size_bytes": 2048,
                    "upload_instructions": "Upload a single ZIP file only.",
                },
                {
                    "variant_code": "FILE-B",
                    "rendered_question_text": "Upload the February reconciliation package.",
                    "variant_parameters_json": {
                        "public_label": "February",
                        "storage_uri": "unsafe://hidden",
                    },
                    "allowed_extensions": [".pdf"],
                    "allowed_mime_types": ["application/pdf"],
                    "max_file_size_bytes": 1024,
                    "upload_instructions": "Upload a single PDF export.",
                },
            ],
        },
        "template_code": "FILE-UPLOAD-1",
        "question_type": "FILE_UPLOAD",
        "title": "Upload your supporting file",
        "template_text": "Upload the required supporting file.",
        "default_score": 10,
    }


class _RuntimeRepository:
    def get_session_by_id(self, session_id: int) -> dict | None:
        if int(session_id) != 51:
            return None
        return {
            "exam_session_id": 51,
            "exam_assignment_id": 41,
            "exam_sitting_id": 31,
            "student_id": 701,
            "session_code": "S-51",
            "session_no": 1,
            "session_status": "IN_PROGRESS",
            "started_at": None,
            "deadline_at": None,
            "ended_at": None,
            "time_limit_seconds": 3600,
            "extra_time_seconds": 0,
            "last_seen_at": None,
            "last_activity_at": None,
            "generated_exam_instance_id": 5001,
            "generation_status": "GENERATED",
        }

    def get_student_id_by_user_id(self, user_id: int) -> int | None:
        return 701 if int(user_id) == 19 else None

    def list_generated_paper_questions(self, session_id: int) -> list[dict]:
        _ = session_id
        materialized, _, _ = DeliveryRepository._materialize_runtime_questions(
            questions=[_file_upload_variant_question(901)],
            exam_session_id=51,
            exam_version_id=61,
            randomization_mode="PARAMETERIZED",
        )
        question = materialized[0]
        question["generated_exam_question_id"] = 8801
        question["grading_input_source"] = "SEALED_FILE_REF"
        question["grading_answer_language"] = "NONE"
        question["grading_engine_code"] = "MANUAL_RUBRIC"
        question["grading_comparison_method"] = "MANUAL_RUBRIC"
        question["grading_requires_capture"] = False
        question["grading_required_capture_type"] = None
        question["grading_profile_metadata_json"] = {"manual_review_policy": "ALWAYS"}
        question["rendered_question_payload_json"] = question.pop("payload_data")
        return [question]

    def get_or_create_submission_for_session(self, *, session_id: int, actor_user_id: int | None) -> dict:
        _ = actor_user_id
        return {
            "exam_submission_id": 12051,
            "exam_session_id": int(session_id),
            "generated_exam_instance_id": 5001,
            "submission_status": "DRAFT",
            "opened_at": None,
            "first_saved_at": None,
            "last_saved_at": None,
            "submitted_at": None,
            "sealed_at": None,
        }

    def list_current_answer_file_assets_for_submission(self, submission_id: int) -> list[dict]:
        _ = submission_id
        return []

    def list_answer_state_for_submission(self, submission_id: int) -> list[dict]:
        _ = submission_id
        return []

    def list_active_paper_assets_for_session(self, session_id: int) -> list[dict]:
        _ = session_id
        return []


def test_file_upload_variant_materialization_preserves_original_link_and_constraints() -> None:
    first, first_seed, first_strategy = DeliveryRepository._materialize_runtime_questions(
        questions=[_file_upload_variant_question(901)],
        exam_session_id=51,
        exam_version_id=61,
        randomization_mode="PARAMETERIZED",
    )
    second, second_seed, second_strategy = DeliveryRepository._materialize_runtime_questions(
        questions=[_file_upload_variant_question(901)],
        exam_session_id=51,
        exam_version_id=61,
        randomization_mode="PARAMETERIZED",
    )

    assert first_seed == second_seed
    assert first_strategy == second_strategy == "TEXT_MANUAL_SESSION_SEEDED"

    question = first[0]
    assert question["question_type"] == "FILE_UPLOAD"
    assert question["original_question_id"] == 901
    assert question["canonical_question_order"] == 2
    assert question["display_question_order"] == question["question_order"]
    assert question["variant_code"] in {"FILE-A", "FILE-B"}
    assert second[0]["rendered_question_text"] == question["rendered_question_text"]
    assert second[0]["payload_data"]["answer_ui"] == question["payload_data"]["answer_ui"]
    assert question["variant_parameters_json"] in ({"public_label": "January", "variant_index": 1, "variant_count": 2}, {"public_label": "February", "variant_index": 2, "variant_count": 2})
    assert "internal_storage_key" not in question["variant_parameters_json"]
    assert "storage_uri" not in question["variant_parameters_json"]

    answer_ui = question["payload_data"]["answer_ui"]
    assert answer_ui["input_source"] == "SEALED_FILE_REF"
    assert answer_ui["allowed_extensions"] in ([".zip"], [".pdf"])
    if answer_ui["allowed_extensions"] == [".zip"]:
        assert "application/zip" in answer_ui["allowed_mime_types"]
    else:
        assert answer_ui["allowed_mime_types"] == ["application/pdf"]
    assert answer_ui["max_file_size_bytes"] in (2048, 1024)
    assert answer_ui["upload_instructions"] in {"Upload a single ZIP file only.", "Upload a single PDF export."}


def test_file_upload_runtime_exposes_constraints_but_hides_original_linkage() -> None:
    service = DeliveryService(repository=_RuntimeRepository())

    payload = service.get_exam_taking_payload(session_id=51, current_user={"user_id": 19, "roles": ["STUDENT"]})
    question = payload["paper"]["questions"][0]

    assert question["generated_exam_question_id"] == 8801
    assert question["question_type"] == "FILE_UPLOAD"
    assert "original_question_id" not in question
    assert "source_exam_question_id" not in question
    assert "canonical_question_order" not in question
    assert question["answer_ui"]["ui_mode"] == "FILE_UPLOAD"
    assert question["answer_ui"]["input_source"] == "SEALED_FILE_REF"
    assert question["answer_ui"]["upload_instructions"]
    assert question["file_upload_policy"]["upload_instructions"] == question["answer_ui"]["upload_instructions"]
    assert question["file_upload_policy"]["allowed_extensions"] == question["answer_ui"]["allowed_extensions"]
    assert question["rendered_question_text"] in {
        "Upload the January reconciliation package.",
        "Upload the February reconciliation package.",
    }
