"""Read-only post-seal dispatch readiness evaluation for submissions."""

from __future__ import annotations

import json

from app.core.errors import ApiError
from app.modules.submission.repositories.submission_repository import SubmissionRepository
from app.modules.submission.services.seal_guard import SubmissionProcessingGuard


class SubmissionDispatchReadinessService:
    """Evaluates what a future dispatcher should do without creating any jobs."""

    ROUTE_DIRECT_GRADING = "DIRECT_GRADING"
    ROUTE_CAPTURE_THEN_GRADING = "CAPTURE_THEN_GRADING"
    ROUTE_MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    ROUTE_NOT_READY = "NOT_READY"

    SUPPORTED_MODALITIES = {"TEXTBOX_SQL", "TEXTBOX_CODE", "STUDENT_DATABASE", "MISA_DATABASE", "AMIS_ONLINE", "HYBRID", "FILE_BASED"}
    CAPTURE_REQUIRED_MODALITIES = {"STUDENT_DATABASE", "MISA_DATABASE", "AMIS_ONLINE", "HYBRID"}
    CAPTURE_INPUT_SOURCES = {"STUDENT_DATABASE_CAPTURE", "MISA_DATABASE_CAPTURE", "AMIS_API_CAPTURE", "FILE_ARTIFACT_CAPTURE"}
    FILE_INPUT_SOURCES = {"SEALED_FILE_REF"}
    TEXT_INPUT_SOURCES = {"SEALED_TEXT_ANSWER"}
    JSON_INPUT_SOURCES = {"SEALED_JSON_ANSWER"}
    MANUAL_INPUT_SOURCES = {"MANUAL"}
    MANUAL_COMPARISON_METHODS = {"MANUAL_RUBRIC"}
    MANUAL_GRADING_ENGINE_CODES = {"MANUAL_RUBRIC", "MANUAL_RUBRIC_GRADER"}
    PYTHON_GRADING_ENGINE_CODES = {"PYTHON_CODE_RUNNER"}
    PYTHON_ANSWER_LANGUAGES = {"PYTHON"}

    def __init__(self, repository: SubmissionRepository | None = None) -> None:
        self.repository = repository or SubmissionRepository()

    @staticmethod
    def _metadata_dict(metadata_json: object) -> dict:
        if isinstance(metadata_json, dict):
            return metadata_json
        if isinstance(metadata_json, str) and metadata_json.strip():
            try:
                parsed = json.loads(metadata_json)
            except json.JSONDecodeError:
                return {}
            if isinstance(parsed, dict):
                return parsed
        return {}

    def _resolve_modality(self, delivery_profile: dict) -> str | None:
        primary_answer_source = str(delivery_profile.get("primary_answer_source") or "").strip().upper()
        delivery_mode = str(delivery_profile.get("delivery_mode") or "").strip().upper()
        metadata = self._metadata_dict(delivery_profile.get("metadata_json"))

        if primary_answer_source == "FILE_ARTIFACT" or delivery_mode == "FILE_BASED":
            return "FILE_BASED"

        if primary_answer_source == "STUDENT_DATABASE":
            return "STUDENT_DATABASE"
        if primary_answer_source == "MISA_DATABASE":
            return "MISA_DATABASE"
        if primary_answer_source == "AMIS_API":
            return "AMIS_ONLINE"
        if primary_answer_source == "MIXED" or delivery_mode == "MIXED":
            return "HYBRID"

        if primary_answer_source in {"SEALED_FORM_ANSWER", "MANUAL"}:
            candidate = (
                metadata.get("modality_code")
                or metadata.get("exam_modality")
                or metadata.get("form_modality")
                or metadata.get("answer_modality")
            )
            if candidate:
                return str(candidate).strip().upper()

        return None

    @staticmethod
    def _infer_form_delivery_profile_from_questions(question_requirements: list[dict]) -> dict | None:
        if not question_requirements:
            return None

        input_sources = {
            str(question.get("input_source") or "").strip().upper()
            for question in question_requirements
            if question.get("input_source") is not None
        }
        requires_capture = any(bool(question.get("requires_capture")) for question in question_requirements)

        if requires_capture or bool(input_sources & SubmissionDispatchReadinessService.CAPTURE_INPUT_SOURCES):
            return {
                "delivery_mode": "DATABASE_BASED",
                "primary_answer_source": "STUDENT_DATABASE",
                "requires_capture": True,
                "default_capture_profile_id": None,
                "metadata_json": {},
            }

        if input_sources and input_sources <= SubmissionDispatchReadinessService.FILE_INPUT_SOURCES:
            return {
                "delivery_mode": "FILE_BASED",
                "primary_answer_source": "FILE_ARTIFACT",
                "requires_capture": False,
                "default_capture_profile_id": None,
                "metadata_json": {},
            }

        if input_sources and input_sources <= (
            SubmissionDispatchReadinessService.TEXT_INPUT_SOURCES
            | SubmissionDispatchReadinessService.JSON_INPUT_SOURCES
            | SubmissionDispatchReadinessService.MANUAL_INPUT_SOURCES
        ):
            answer_languages = {
                str(question.get("answer_language") or "").strip().upper()
                for question in question_requirements
                if question.get("answer_language") is not None
            }
            grading_engine_codes = {
                str(question.get("grading_engine_code") or "").strip().upper()
                for question in question_requirements
                if question.get("grading_engine_code") is not None
            }
            question_types = {
                str(question.get("question_type") or "").strip().upper()
                for question in question_requirements
                if question.get("question_type") is not None
            }
            inferred_modality = "TEXTBOX_SQL"
            if (
                bool(answer_languages & SubmissionDispatchReadinessService.PYTHON_ANSWER_LANGUAGES)
                or bool(grading_engine_codes & SubmissionDispatchReadinessService.PYTHON_GRADING_ENGINE_CODES)
                or "TEXTBOX_CODE" in question_types
                or "PYTHON_FUNCTION" in question_types
                or "PYTHON_CODE" in question_types
            ):
                inferred_modality = "TEXTBOX_CODE"
            return {
                "delivery_mode": "FORM_BASED",
                "primary_answer_source": "SEALED_FORM_ANSWER",
                "requires_capture": False,
                "default_capture_profile_id": None,
                "metadata_json": {"modality_code": inferred_modality},
            }

        return {
            "delivery_mode": "MIXED",
            "primary_answer_source": "MIXED",
            "requires_capture": requires_capture,
            "default_capture_profile_id": None,
            "metadata_json": {"modality_code": "HYBRID"},
        }

    @staticmethod
    def _base_result(submission_id: int) -> dict:
        return {
            "submission_id": int(submission_id),
            "is_sealed": False,
            "dispatch_ready": False,
            "dispatch_route": SubmissionDispatchReadinessService.ROUTE_NOT_READY,
            "capture_required": False,
            "grading_required": False,
            "blockers": [],
            "modality": None,
            "exam_version_id": None,
            "capture_profile_id": None,
            "grading_profile_id": None,
            "grading_profile_summary": None,
            "required_sources": {
                "text": 0,
                "json": 0,
                "file": 0,
                "capture": 0,
                "manual": 0,
            },
        }

    @staticmethod
    def _is_question_required(question_row: dict) -> bool:
        payload = question_row.get("rendered_question_payload_json")
        answer_ui = payload.get("answer_ui") if isinstance(payload, dict) else None
        if isinstance(answer_ui, dict) and isinstance(answer_ui.get("required"), bool):
            return bool(answer_ui.get("required"))
        return True

    @staticmethod
    def _has_nonempty_text(value: object) -> bool:
        return isinstance(value, str) and bool(value.strip())

    @staticmethod
    def _is_file_ref_payload(value: object) -> bool:
        if not isinstance(value, dict):
            return False
        file_asset_id = value.get("file_asset_id")
        if file_asset_id is None:
            return False
        try:
            return int(file_asset_id) > 0
        except (TypeError, ValueError):
            return False

    def evaluate_submission(self, *, submission_id: int) -> dict:
        result = self._base_result(submission_id)

        context = self.repository.get_submission_dispatch_context(int(submission_id))
        if context is None:
            result["blockers"].append("SUBMISSION_NOT_FOUND")
            return result

        exam_version_id = context.get("exam_version_id")
        result["exam_version_id"] = int(exam_version_id) if exam_version_id is not None else None

        result["is_sealed"] = SubmissionProcessingGuard.is_submission_context_sealed(context)

        try:
            SubmissionProcessingGuard.assert_submission_context_is_sealed(
                submission_context=context,
                message="Submission must be sealed before dispatch readiness evaluation",
            )
        except ApiError as exc:
            result["blockers"].append(str(exc.details.get("blocker") or "SUBMISSION_NOT_SEALED"))
            return result

        if result["exam_version_id"] is None:
            result["blockers"].append("MISSING_EXAM_VERSION")
            return result

        question_requirements: list[dict] | None = None
        delivery_profile = self.repository.get_exam_version_delivery_profile(int(result["exam_version_id"]))
        if delivery_profile is None:
            question_requirements = self.repository.list_submission_question_dispatch_requirements(int(submission_id))
            delivery_profile = self._infer_form_delivery_profile_from_questions(question_requirements)
            if delivery_profile is None:
                result["blockers"].append("MISSING_DELIVERY_PROFILE")
                return result

        modality = self._resolve_modality(delivery_profile)
        result["modality"] = modality
        if modality is None:
            result["blockers"].append("MISSING_MODALITY")
        elif modality not in self.SUPPORTED_MODALITIES:
            result["blockers"].append("UNSUPPORTED_MODALITY")

        active_grading_profiles = self.repository.count_active_question_grading_profiles(int(result["exam_version_id"]))
        result["grading_required"] = active_grading_profiles > 0
        if active_grading_profiles <= 0:
            result["blockers"].append("MISSING_GRADING_PROFILE")

        grading_profile_summary = self.repository.get_dispatch_grading_profile_summary(int(result["exam_version_id"]))
        if grading_profile_summary is not None:
            result["grading_profile_id"] = int(grading_profile_summary["question_grading_profile_id"])
            result["grading_profile_summary"] = {
                "question_grading_profile_id": int(grading_profile_summary["question_grading_profile_id"]),
                "input_source": grading_profile_summary.get("input_source"),
                "answer_language": grading_profile_summary.get("answer_language"),
                "requires_capture": bool(grading_profile_summary.get("requires_capture")),
                "required_capture_type": grading_profile_summary.get("required_capture_type"),
                "capture_profile_code": grading_profile_summary.get("capture_profile_code"),
                "grading_engine_code": grading_profile_summary.get("grading_engine_code"),
                "comparison_method": grading_profile_summary.get("comparison_method"),
            }

        capture_required = bool(delivery_profile.get("requires_capture"))
        delivery_mode = str(delivery_profile.get("delivery_mode") or "").strip().upper()
        primary_answer_source = str(delivery_profile.get("primary_answer_source") or "").strip().upper()
        file_upload_delivery_mode = modality == "FILE_BASED" or delivery_mode == "FILE_BASED" or primary_answer_source == "FILE_ARTIFACT"
        if modality in self.CAPTURE_REQUIRED_MODALITIES:
            capture_required = True
        if question_requirements is None:
            question_requirements = self.repository.list_submission_question_dispatch_requirements(int(submission_id))
        if not question_requirements:
            result["blockers"].append("MISSING_QUESTION_REQUIREMENTS")
            result["dispatch_route"] = self.ROUTE_NOT_READY
            result["dispatch_ready"] = False
            return result

        manual_required = False
        python_grading_blocked = False
        question_capture_profile_id: int | None = None
        question_has_capture_profile = False

        for question in question_requirements:
            if not self._is_question_required(question):
                continue

            question_id = int(question["generated_exam_question_id"])
            profile_id = question.get("question_grading_profile_id")
            input_source = str(question.get("input_source") or "").strip().upper()
            requires_capture = bool(question.get("requires_capture"))
            comparison_method = str(question.get("comparison_method") or "").strip().upper()
            grading_engine_code = str(question.get("grading_engine_code") or "").strip().upper()
            answer_language = str(question.get("answer_language") or "").strip().upper()
            sealed_answer_type = str(question.get("sealed_answer_type") or "").strip().upper()
            sealed_answer_text = question.get("sealed_answer_text")
            sealed_answer_payload = question.get("sealed_answer_payload_json")
            capture_profile_id_value = question.get("capture_profile_id")
            capture_profile_code = str(question.get("capture_profile_code") or "").strip()

            if profile_id is None:
                result["blockers"].append(f"MISSING_GRADING_PROFILE_FOR_QUESTION:{question_id}")
                continue

            if capture_profile_id_value is not None:
                question_capture_profile_id = int(capture_profile_id_value)
            if capture_profile_code:
                question_has_capture_profile = True

            if input_source in self.FILE_INPUT_SOURCES:
                result["required_sources"]["file"] += 1
                has_file_ref = sealed_answer_type == "FILE_REF" and self._is_file_ref_payload(sealed_answer_payload)
                if not has_file_ref:
                    result["blockers"].append(f"MISSING_FILE_REF_ANSWER:{question_id}")
            elif input_source in self.TEXT_INPUT_SOURCES:
                result["required_sources"]["text"] += 1
                has_text = sealed_answer_type != "FILE_REF" and (
                    self._has_nonempty_text(sealed_answer_text) or isinstance(sealed_answer_payload, (dict, list))
                )
                if not has_text:
                    result["blockers"].append(f"MISSING_TEXT_ANSWER:{question_id}")
            elif input_source in self.JSON_INPUT_SOURCES:
                result["required_sources"]["json"] += 1
                has_json = isinstance(sealed_answer_payload, (dict, list))
                if not has_json:
                    result["blockers"].append(f"MISSING_JSON_ANSWER:{question_id}")
            elif input_source in self.CAPTURE_INPUT_SOURCES:
                result["required_sources"]["capture"] += 1
                capture_required = True
            elif input_source in self.MANUAL_INPUT_SOURCES:
                result["required_sources"]["manual"] += 1
                manual_required = True
                if file_upload_delivery_mode:
                    result["blockers"].append(f"FILE_UPLOAD_INPUT_SOURCE_MUST_BE_SEALED_FILE_REF:{question_id}")
            else:
                result["blockers"].append(f"UNSUPPORTED_INPUT_SOURCE:{input_source or 'UNKNOWN'}:{question_id}")

            if requires_capture:
                result["required_sources"]["capture"] += 1
                capture_required = True

            if comparison_method in self.MANUAL_COMPARISON_METHODS or grading_engine_code in self.MANUAL_GRADING_ENGINE_CODES:
                manual_required = True

            if (
                answer_language in self.PYTHON_ANSWER_LANGUAGES
                or grading_engine_code in self.PYTHON_GRADING_ENGINE_CODES
            ):
                python_grading_blocked = True
                result["blockers"].append(f"PYTHON_GRADING_NOT_READY:{question_id}")

        if python_grading_blocked:
            result["dispatch_route"] = self.ROUTE_NOT_READY
            result["dispatch_ready"] = False
            return result

        result["capture_required"] = capture_required
        delivery_capture_profile_id = delivery_profile.get("default_capture_profile_id")
        if delivery_capture_profile_id is not None:
            result["capture_profile_id"] = int(delivery_capture_profile_id)
        elif question_capture_profile_id is not None:
            result["capture_profile_id"] = int(question_capture_profile_id)
        else:
            result["capture_profile_id"] = None

        if capture_required:
            has_capture_profile = (
                result["capture_profile_id"] is not None
                or question_has_capture_profile
                or self.repository.has_active_capture_required_profile_config(int(result["exam_version_id"]))
            )
            if not has_capture_profile:
                result["blockers"].append("MISSING_CAPTURE_PROFILE")

        if "UNSUPPORTED_MODALITY" in result["blockers"] or "MISSING_MODALITY" in result["blockers"]:
            result["dispatch_route"] = self.ROUTE_MANUAL_REVIEW_REQUIRED
            result["dispatch_ready"] = False
            return result

        if result["blockers"]:
            result["dispatch_route"] = self.ROUTE_NOT_READY
            result["dispatch_ready"] = False
            return result

        if result["capture_required"] and result["grading_required"]:
            result["dispatch_route"] = self.ROUTE_CAPTURE_THEN_GRADING
            result["dispatch_ready"] = True
            return result

        if manual_required and result["grading_required"]:
            result["dispatch_route"] = self.ROUTE_MANUAL_REVIEW_REQUIRED
            result["dispatch_ready"] = True
            return result

        if result["grading_required"]:
            result["dispatch_route"] = self.ROUTE_DIRECT_GRADING
            result["dispatch_ready"] = True
            return result

        result["dispatch_route"] = self.ROUTE_MANUAL_REVIEW_REQUIRED
        result["dispatch_ready"] = False
        return result


def build_submission_dispatch_readiness_service() -> SubmissionDispatchReadinessService:
    return SubmissionDispatchReadinessService()
