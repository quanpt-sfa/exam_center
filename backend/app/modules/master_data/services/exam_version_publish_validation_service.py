"""Service for validating exam version publish-readiness."""

from __future__ import annotations

from app.modules.master_data.common.errors import MasterDataNotFoundError
from app.modules.master_data.repositories.exam_repository import ExamRepository
from app.modules.master_data.repositories.exam_version_repository import ExamVersionRepository
from app.modules.master_data.services.exam_version_delivery_profile_service import (
    ExamVersionDeliveryProfileService,
)


class ExamVersionPublishValidationService:
    """Validates exam version state and required configuration before publish."""

    RANDOMIZATION_MODES = {"FIXED", "RANDOM_FROM_BANK", "PARAMETERIZED", "HYBRID"}

    CAPTURE_REQUIRED_MODALITIES = {
        "STUDENT_DATABASE",
        "MISA_DATABASE",
        "AMIS_ONLINE",
        "HYBRID",
    }
    AUTO_GRADED_ENGINES = {"MCQ_AUTO_GRADER", "SQL_RESULT_COMPARATOR", "TEXT_RULE", "TEXTBOX_SQL"}
    PYTHON_AUTO_GRADED_ENGINES = {"PYTHON_CODE_RUNNER"}
    PYTHON_COMPARISON_METHODS = {"PYTHON_TEST_CASES"}
    VISUAL_PAPER_METADATA_KEYS = {"visual_paper_required", "paper_asset_required", "requires_visual_paper"}
    EXPECTED_ANSWER_LEAK_KEYS = {
        "expected_answer",
        "expected_answer_text",
        "expected_answer_json",
        "reference_solution",
        "reference_solution_id",
        "generated_expected_answer",
    }

    def __init__(
        self,
        *,
        exam_repository: ExamRepository | None = None,
        exam_version_repository: ExamVersionRepository | None = None,
        delivery_profile_service: ExamVersionDeliveryProfileService | None = None,
    ) -> None:
        self._exam_repository = exam_repository or ExamRepository()
        self._exam_version_repository = exam_version_repository or ExamVersionRepository()
        self._delivery_profile_service = delivery_profile_service or ExamVersionDeliveryProfileService()

    @staticmethod
    def _metadata_dict(value: object) -> dict:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _coerce_positive_int(value: object | None) -> int | None:
        if value is None:
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed >= 0 else None

    @staticmethod
    def _coerce_positive_float(value: object | None) -> float | None:
        if value is None:
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed

    def validate_exam_version(
        self,
        *,
        exam_version_id: int,
        actor: dict,
        conn: object | None = None,
    ) -> dict:
        _ = actor

        version = self._exam_version_repository.get_exam_version_by_id(int(exam_version_id), conn=conn)
        if version is None:
            raise MasterDataNotFoundError(
                "Exam version not found",
                details={"exam_version_id": int(exam_version_id)},
            )

        exam = self._exam_repository.get_exam_by_id(int(version["exam_id"]), conn=conn)
        if exam is None:
            raise MasterDataNotFoundError(
                "Exam not found",
                details={"exam_id": int(version["exam_id"]), "exam_version_id": int(exam_version_id)},
            )

        missing_items: list[dict] = []

        def _add_missing(code: str, message: str, details: dict | None = None) -> None:
            missing_items.append(
                {
                    "code": code,
                    "message": message,
                    "details": details or {},
                }
            )

        if str(exam.get("exam_status") or "").upper() != "ACTIVE":
            _add_missing(
                "exam_not_active",
                "Exam must be ACTIVE before publishing a version",
                {"exam_id": int(exam["exam_id"]), "exam_status": exam.get("exam_status")},
            )

        if int(version.get("duration_seconds") or 0) <= 0:
            _add_missing(
                "invalid_duration",
                "duration_seconds must be greater than 0",
                {"duration_seconds": version.get("duration_seconds")},
            )

        total_score = version.get("total_score")
        if total_score is None or float(total_score) <= 0:
            _add_missing(
                "invalid_total_score",
                "total_score must be greater than 0",
                {"total_score": total_score},
            )

        randomization_mode = str(version.get("randomization_mode") or "").strip().upper()
        if randomization_mode not in self.RANDOMIZATION_MODES:
            _add_missing(
                "invalid_randomization_mode",
                "randomization_mode is invalid",
                {
                    "randomization_mode": version.get("randomization_mode"),
                    "allowed_values": sorted(self.RANDOMIZATION_MODES),
                },
            )

        delivery_profile = None
        if self._delivery_profile_service.is_supported(conn=conn):
            delivery_profile = self._delivery_profile_service.get_delivery_profile_for_exam_version(
                exam_version_id=int(exam_version_id),
                conn=conn,
            )

            if delivery_profile is None:
                _add_missing(
                    "delivery_profile_missing",
                    "Exam version delivery profile is required for publish",
                    {"exam_version_id": int(exam_version_id)},
                )
            else:
                modality = delivery_profile.get("exam_modality")
                if modality is None:
                    _add_missing(
                        "exam_modality_missing",
                        "Exam modality is not resolvable from delivery profile metadata",
                        {
                            "exam_version_id": int(exam_version_id),
                            "delivery_mode": delivery_profile.get("delivery_mode"),
                            "primary_answer_source": delivery_profile.get("primary_answer_source"),
                            "required_modalities": sorted(ExamVersionDeliveryProfileService.MODALITIES),
                        },
                    )

                requires_capture = bool(delivery_profile.get("requires_capture"))
                capture_profile_id = delivery_profile.get("default_capture_profile_id")
                grading_engine_id = delivery_profile.get("default_grading_engine_id")

                if modality in self.CAPTURE_REQUIRED_MODALITIES and not requires_capture:
                    _add_missing(
                        "capture_required_for_modality",
                        "Selected modality requires capture to be enabled",
                        {
                            "exam_modality": modality,
                            "requires_capture": requires_capture,
                        },
                    )

                if requires_capture and capture_profile_id is None:
                    _add_missing(
                        "capture_profile_missing",
                        "Capture profile is required when requires_capture=true",
                        {"exam_version_id": int(exam_version_id)},
                    )

                if capture_profile_id is not None:
                    capture_profile_active = self._delivery_profile_service.capture_profile_is_active(
                        capture_profile_id=int(capture_profile_id),
                        conn=conn,
                    )
                    if capture_profile_active is False:
                        _add_missing(
                            "capture_profile_inactive",
                            "Default capture profile is missing or inactive",
                            {"capture_profile_id": int(capture_profile_id)},
                        )

                if grading_engine_id is None:
                    _add_missing(
                        "grading_engine_missing",
                        "Default grading engine is required for publish",
                        {"exam_version_id": int(exam_version_id)},
                    )

                if grading_engine_id is not None:
                    grading_engine_active = self._delivery_profile_service.grading_engine_is_active(
                        grading_engine_id=int(grading_engine_id),
                        conn=conn,
                    )
                    if grading_engine_active is False:
                        _add_missing(
                            "grading_engine_inactive",
                            "Default grading engine is missing or inactive",
                            {"grading_engine_id": int(grading_engine_id)},
                        )

                if capture_profile_id is not None and grading_engine_id is not None:
                    supported_link = self._delivery_profile_service.capture_profile_supports_engine(
                        capture_profile_id=int(capture_profile_id),
                        grading_engine_id=int(grading_engine_id),
                        conn=conn,
                    )
                    if supported_link is False:
                        _add_missing(
                            "capture_engine_link_missing",
                            "Capture profile is not linked to the selected grading engine",
                            {
                                "capture_profile_id": int(capture_profile_id),
                                "grading_engine_id": int(grading_engine_id),
                            },
                        )

        delivery_metadata = self._metadata_dict(delivery_profile.get("metadata_json") if delivery_profile else {})
        delivery_mode = str(delivery_profile.get("delivery_mode") or "").strip().upper() if delivery_profile else ""
        primary_answer_source = (
            str(delivery_profile.get("primary_answer_source") or "").strip().upper() if delivery_profile else ""
        )
        delivery_content_type = str(
            delivery_metadata.get("delivery_content_type")
            or delivery_metadata.get("conceptual_delivery_type")
            or ""
        ).strip().upper()
        requires_visual_paper = False
        for key in self.VISUAL_PAPER_METADATA_KEYS:
            if key in delivery_metadata:
                requires_visual_paper = bool(delivery_metadata.get(key))
                break
        if delivery_content_type == "VISUAL_PAPER_BASED":
            requires_visual_paper = True
        elif delivery_content_type == "FILE_SUBMISSION_BASED":
            requires_visual_paper = False
        elif not requires_visual_paper:
            requires_visual_paper = delivery_mode == "FILE_BASED" and primary_answer_source == "FILE_ARTIFACT"

        profile_rows: list[dict] = []
        active_question_count = 0
        if self._exam_version_repository.question_grading_profile_table_exists(conn=conn):
            profile_rows = self._exam_version_repository.list_active_question_grading_profiles(
                exam_version_id=int(exam_version_id),
                conn=conn,
            )
            active_question_count = len(profile_rows)

        file_artifact_is_question_based = primary_answer_source == "FILE_ARTIFACT" and not requires_visual_paper
        question_based = (
            delivery_mode in {"FORM_BASED", "MIXED", "DATABASE_BASED", "EXTERNAL_SYSTEM_BASED"}
            or primary_answer_source in {"SEALED_FORM_ANSWER", "MIXED"}
            or file_artifact_is_question_based
            or bool(delivery_metadata.get("allow_form_answers"))
            or active_question_count > 0
        )

        if question_based and active_question_count == 0:
            _add_missing(
                "question_grading_profile_missing",
                "At least one active question is required for question-based exam versions",
                {"exam_version_id": int(exam_version_id)},
            )
        else:
            for row in profile_rows:
                metadata = self._metadata_dict(row.get("metadata_json"))
                response_mode = str(metadata.get("response_mode") or "").strip().upper()
                render_component = str(metadata.get("render_component") or "").strip().upper()
                if not response_mode or not render_component:
                    _add_missing(
                        "question_response_profile_missing",
                        "Question is missing response profile metadata",
                        {
                            "exam_version_id": int(exam_version_id),
                            "question_template_id": int(row["question_template_id"]),
                            "question_grading_profile_id": int(row["question_grading_profile_id"]),
                        },
                    )

                grading_engine_code = str(row.get("grading_engine_code") or "").strip().upper()
                answer_language = str(row.get("answer_language") or "").strip().upper()
                comparison_method = str(row.get("comparison_method") or "").strip().upper()
                if not grading_engine_code or not comparison_method:
                    _add_missing(
                        "question_grading_profile_missing",
                        "Question is missing grading profile metadata",
                        {
                            "exam_version_id": int(exam_version_id),
                            "question_template_id": int(row["question_template_id"]),
                            "question_grading_profile_id": int(row["question_grading_profile_id"]),
                        },
                    )

                max_score = self._coerce_positive_float(row.get("max_score"))
                if max_score is None or max_score <= 0:
                    _add_missing(
                        "question_max_score_invalid",
                        "Question max_score must be greater than 0",
                        {
                            "exam_version_id": int(exam_version_id),
                            "question_template_id": int(row["question_template_id"]),
                            "question_grading_profile_id": int(row["question_grading_profile_id"]),
                            "max_score": row.get("max_score"),
                        },
                    )

                for forbidden_key in self.EXPECTED_ANSWER_LEAK_KEYS:
                    if forbidden_key in metadata:
                        _add_missing(
                            "student_runtime_expected_answer_leak_risk",
                            "Question metadata contains forbidden expected-answer fields for student runtime",
                            {
                                "exam_version_id": int(exam_version_id),
                                "question_template_id": int(row["question_template_id"]),
                                "question_grading_profile_id": int(row["question_grading_profile_id"]),
                                "field": forbidden_key,
                            },
                        )
                        break

                authoring_question_type = str(metadata.get("authoring_question_type") or "").strip().upper()
                requires_expected_answer = (
                    authoring_question_type in {"TEXTBOX_SQL", "MCQ_SINGLE"}
                    or grading_engine_code in self.AUTO_GRADED_ENGINES
                )
                requires_python_test_case = (
                    authoring_question_type == "PYTHON_FUNCTION"
                    or answer_language == "PYTHON"
                    or grading_engine_code in self.PYTHON_AUTO_GRADED_ENGINES
                    or comparison_method in self.PYTHON_COMPARISON_METHODS
                )
                if requires_expected_answer:
                    has_expected_answer = self._exam_version_repository.question_has_active_expected_answer(
                        question_template_id=int(row["question_template_id"]),
                        conn=conn,
                    )
                    if not has_expected_answer:
                        _add_missing(
                            "question_expected_answer_missing",
                            "Auto-graded question is missing expected answer",
                            {
                                "exam_version_id": int(exam_version_id),
                                "question_template_id": int(row["question_template_id"]),
                                "question_grading_profile_id": int(row["question_grading_profile_id"]),
                                "grading_engine_code": grading_engine_code,
                            },
                        )

                if requires_python_test_case:
                    has_python_test_case = self._exam_version_repository.question_has_active_python_test_case(
                        question_template_id=int(row["question_template_id"]),
                        conn=conn,
                    )
                    if not has_python_test_case:
                        _add_missing(
                            "question_python_test_case_missing",
                            "Python auto-graded question is missing an active python_test_case contract",
                            {
                                "exam_version_id": int(exam_version_id),
                                "question_template_id": int(row["question_template_id"]),
                                "question_grading_profile_id": int(row["question_grading_profile_id"]),
                                "grading_engine_code": grading_engine_code,
                                "comparison_method": comparison_method,
                            },
                        )

        declared_question_count = self._coerce_positive_int(
            delivery_metadata.get("question_count")
            if "question_count" in delivery_metadata
            else delivery_metadata.get("declared_question_count", delivery_metadata.get("authoring_question_count"))
        )
        version_status = str(version.get("status") or "").strip().upper()
        if declared_question_count is not None and version_status != "DRAFT" and active_question_count != declared_question_count:
            _add_missing(
                "question_count_mismatch",
                "Declared question_count does not match active saved questions",
                {
                    "exam_version_id": int(exam_version_id),
                    "declared_question_count": int(declared_question_count),
                    "active_question_count": int(active_question_count),
                    "version_status": version_status,
                },
            )

        if requires_visual_paper:
            has_active_paper = self._exam_version_repository.has_active_visual_paper_asset(
                exam_version_id=int(exam_version_id),
                conn=conn,
            )
            if not has_active_paper:
                _add_missing(
                    "paper_asset_missing",
                    "Visual-paper-based exam version requires an active paper asset",
                    {"exam_version_id": int(exam_version_id)},
                )

        if self._exam_version_repository.has_other_published_version(
            exam_id=int(exam["exam_id"]),
            excluded_exam_version_id=int(exam_version_id),
            conn=conn,
        ):
            _add_missing(
                "published_version_conflict",
                "Another published version already exists for this exam",
                {"exam_id": int(exam["exam_id"])},
            )

        return {
            "exam_id": int(exam["exam_id"]),
            "exam_version_id": int(exam_version_id),
            "exam_status": exam.get("exam_status"),
            "version_status": version.get("status"),
            "exam_modality": delivery_profile.get("exam_modality") if delivery_profile else None,
            "is_valid": len(missing_items) == 0,
            "missing_items": missing_items,
        }


def build_exam_version_publish_validation_service() -> ExamVersionPublishValidationService:
    """FastAPI dependency factory for exam version publish validation service."""

    return ExamVersionPublishValidationService()
