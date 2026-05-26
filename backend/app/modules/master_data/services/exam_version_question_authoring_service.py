"""Service layer for exam-version scoped question authoring."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from decimal import Decimal

from app.infrastructure.database.unit_of_work import database_unit_of_work
from app.modules.assessment.repositories.assessment_repository import AssessmentRepository
from app.modules.master_data.common.errors import MasterDataNotFoundError
from app.modules.master_data.common.errors import MasterDataValidationError
from app.modules.master_data.repositories.grading_engine_repository import GradingEngineRepository
from app.modules.master_data.repositories.question_grading_profile_repository import QuestionGradingProfileRepository
from app.modules.master_data.services.exam_version_delivery_profile_service import ExamVersionDeliveryProfileService


class ExamVersionQuestionAuthoringService:
    """Coordinates question template + grading profile + expected answer authoring per exam version."""

    SUPPORTED_AUTHORING_TYPES = {"TEXTAREA", "TEXTBOX_SQL", "FILE_UPLOAD", "MCQ_SINGLE", "PYTHON_FUNCTION"}
    AUTO_GRADED_ENGINES = {"MCQ_AUTO_GRADER", "SQL_RESULT_COMPARATOR", "TEXT_RULE", "TEXTBOX_SQL"}
    PYTHON_RUNTIME_VERSION = "PYTHON_3_11"
    PYTHON_ENTRYPOINT_MODE = "FUNCTION_SOLVE"
    PYTHON_ENTRYPOINT_FUNCTION = "solve"

    def __init__(
        self,
        *,
        assessment_repository: AssessmentRepository | None = None,
        question_grading_profile_repository: QuestionGradingProfileRepository | None = None,
        grading_engine_repository: GradingEngineRepository | None = None,
        delivery_profile_service: ExamVersionDeliveryProfileService | None = None,
        transaction_scope: Callable[[], object] | None = None,
    ) -> None:
        self._assessment_repository = assessment_repository or AssessmentRepository()
        self._question_grading_profile_repository = question_grading_profile_repository or QuestionGradingProfileRepository()
        self._grading_engine_repository = grading_engine_repository or GradingEngineRepository()
        self._delivery_profile_service = delivery_profile_service or ExamVersionDeliveryProfileService()

        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif (
            assessment_repository is not None
            or question_grading_profile_repository is not None
            or grading_engine_repository is not None
            or delivery_profile_service is not None
        ):
            self._transaction_scope = self._null_transaction_scope
        else:
            self._transaction_scope = database_unit_of_work

    @staticmethod
    @contextmanager
    def _null_transaction_scope():
        yield None

    @staticmethod
    def _build_template_code(*, exam_version_id: int, question_no: int) -> str:
        return f"EV{int(exam_version_id)}-Q{int(question_no)}"

    def _next_available_template_code(self, *, exam_version_id: int, question_no: int, conn: object | None) -> str:
        base = self._build_template_code(exam_version_id=exam_version_id, question_no=question_no)
        if self._assessment_repository.get_question_by_template_code(base, conn=conn) is None:
            return base
        for suffix in range(2, 1000):
            candidate = f"{base}-{suffix}"
            if self._assessment_repository.get_question_by_template_code(candidate, conn=conn) is None:
                return candidate
        raise MasterDataValidationError(
            "Unable to allocate unique template_code for question",
            details={"exam_version_id": int(exam_version_id), "question_no": int(question_no)},
        )

    @staticmethod
    def _map_db_question_type(question_type: str) -> str:
        normalized = str(question_type).strip().upper()
        if normalized == "FILE_UPLOAD":
            return "FILE_UPLOAD"
        if normalized == "TEXTBOX_SQL":
            return "SQL_QUERY"
        if normalized == "PYTHON_FUNCTION":
            return "PYTHON_FUNCTION"
        return "MANUAL_TEXT"

    @staticmethod
    def _safe_float(value: object | None) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_status(value: str | None, *, default: str = "ACTIVE") -> str:
        normalized = str(value or default).strip().upper()
        if normalized not in {"DRAFT", "ACTIVE", "RETIRED", "VOIDED"}:
            raise MasterDataValidationError("Invalid status", details={"status": normalized})
        return normalized

    def _normalize_command(self, *, command: dict) -> dict:
        normalized = dict(command)
        authoring_type = str(normalized.get("question_type") or "").strip().upper()
        if authoring_type not in self.SUPPORTED_AUTHORING_TYPES:
            raise MasterDataValidationError(
                "question_type is invalid",
                details={"question_type": authoring_type, "allowed_values": sorted(self.SUPPORTED_AUTHORING_TYPES)},
            )

        question_no = int(normalized.get("question_no") or 0)
        if question_no <= 0:
            raise MasterDataValidationError("question_no must be greater than 0")

        question_title = str(normalized.get("question_title") or "").strip()
        prompt_text = str(normalized.get("prompt_text") or "").strip()
        if not question_title:
            raise MasterDataValidationError("question_title is required")
        if not prompt_text:
            raise MasterDataValidationError("prompt_text is required")

        max_score = normalized.get("max_score")
        if max_score is None:
            raise MasterDataValidationError("max_score is required")
        try:
            max_score_decimal = Decimal(str(max_score))
        except Exception as exc:  # pragma: no cover - defensive conversion.
            raise MasterDataValidationError("max_score is invalid") from exc
        if max_score_decimal <= 0:
            raise MasterDataValidationError("max_score must be greater than 0")

        default_response_mode = {
            "TEXTAREA": "LONG_TEXT",
            "TEXTBOX_SQL": "SQL_TEXT",
            "FILE_UPLOAD": "FILE_UPLOAD",
            "MCQ_SINGLE": "MCQ_SINGLE",
            "PYTHON_FUNCTION": "CODE_TEXT",
        }[authoring_type]
        default_render = {
            "TEXTAREA": "TEXTAREA",
            "TEXTBOX_SQL": "SQL_EDITOR",
            "FILE_UPLOAD": "FILE_UPLOAD",
            "MCQ_SINGLE": "RADIO_GROUP",
            "PYTHON_FUNCTION": "CODE_EDITOR",
        }[authoring_type]
        default_input_source = {
            "TEXTAREA": "SEALED_TEXT_ANSWER",
            "TEXTBOX_SQL": "SEALED_TEXT_ANSWER",
            "FILE_UPLOAD": "SEALED_FILE_REF",
            "MCQ_SINGLE": "SEALED_JSON_ANSWER",
            "PYTHON_FUNCTION": "SEALED_TEXT_ANSWER",
        }[authoring_type]
        default_engine = {
            "TEXTAREA": "MANUAL_RUBRIC",
            "TEXTBOX_SQL": "SQL_RESULT_COMPARATOR",
            "FILE_UPLOAD": "MANUAL_RUBRIC",
            "MCQ_SINGLE": "MCQ_AUTO_GRADER",
            "PYTHON_FUNCTION": "PYTHON_CODE_RUNNER",
        }[authoring_type]
        default_comparison = {
            "TEXTAREA": "MANUAL_RUBRIC",
            "TEXTBOX_SQL": "EXACT_RESULT_SET",
            "FILE_UPLOAD": "MANUAL_RUBRIC",
            "MCQ_SINGLE": "EXACT_RESULT_SET",
            "PYTHON_FUNCTION": "PYTHON_TEST_CASES",
        }[authoring_type]
        default_answer_language = {
            "TEXTAREA": "TEXT",
            "TEXTBOX_SQL": "SQL",
            "FILE_UPLOAD": "NONE",
            "MCQ_SINGLE": "JSON",
            "PYTHON_FUNCTION": "PYTHON",
        }[authoring_type]

        response_mode = str(normalized.get("response_mode") or default_response_mode).strip().upper()
        render_component = str(normalized.get("render_component") or default_render).strip().upper()
        grading_engine_code = str(normalized.get("grading_engine_code") or default_engine).strip().upper()
        comparison_method = self._normalize_comparison_method(normalized.get("comparison_method") or default_comparison)
        answer_language = str(normalized.get("answer_language") or default_answer_language).strip().upper()

        timeout_seconds = normalized.get("timeout_seconds")
        if timeout_seconds is None and authoring_type == "PYTHON_FUNCTION":
            timeout_seconds = 5
        if timeout_seconds is not None:
            try:
                timeout_seconds = int(timeout_seconds)
            except (TypeError, ValueError) as exc:
                raise MasterDataValidationError("timeout_seconds is invalid") from exc
            if timeout_seconds <= 0:
                raise MasterDataValidationError("timeout_seconds must be greater than 0")

        python_runtime_contract: dict | None = None
        if authoring_type == "PYTHON_FUNCTION":
            if grading_engine_code != "PYTHON_CODE_RUNNER":
                raise MasterDataValidationError(
                    "PYTHON_FUNCTION questions must use PYTHON_CODE_RUNNER",
                    details={"grading_engine_code": grading_engine_code},
                )
            if comparison_method != "PYTHON_TEST_CASES":
                raise MasterDataValidationError(
                    "PYTHON_FUNCTION questions must use PYTHON_TEST_CASES",
                    details={"comparison_method": comparison_method},
                )

            runtime_version = str(normalized.get("runtime_version") or self.PYTHON_RUNTIME_VERSION).strip().upper()
            entrypoint_mode = str(normalized.get("entrypoint_mode") or self.PYTHON_ENTRYPOINT_MODE).strip().upper()
            entrypoint_function = str(normalized.get("entrypoint_function") or self.PYTHON_ENTRYPOINT_FUNCTION).strip()
            memory_limit_mb = int(normalized.get("memory_limit_mb") or 128)
            output_limit_bytes = int(normalized.get("output_limit_bytes") or 65536)
            network_enabled = bool(normalized.get("network_enabled", False))
            filesystem_policy = str(
                normalized.get("filesystem_policy") or "EPHEMERAL_NO_HOST_ACCESS"
            ).strip().upper()
            package_policy = str(normalized.get("package_policy") or "STDLIB_ONLY").strip().upper()
            visibility_policy = str(
                normalized.get("visibility_policy") or "STUDENT_PUBLIC_ONLY"
            ).strip().upper()

            if runtime_version != self.PYTHON_RUNTIME_VERSION:
                raise MasterDataValidationError(
                    "runtime_version is invalid for MVP Python grading",
                    details={"runtime_version": runtime_version, "allowed_values": [self.PYTHON_RUNTIME_VERSION]},
                )
            if entrypoint_mode != self.PYTHON_ENTRYPOINT_MODE:
                raise MasterDataValidationError(
                    "entrypoint_mode is invalid for MVP Python grading",
                    details={"entrypoint_mode": entrypoint_mode, "allowed_values": [self.PYTHON_ENTRYPOINT_MODE]},
                )
            if not entrypoint_function:
                raise MasterDataValidationError("entrypoint_function is required for PYTHON_FUNCTION")
            if memory_limit_mb <= 0:
                raise MasterDataValidationError("memory_limit_mb must be greater than 0")
            if output_limit_bytes <= 0:
                raise MasterDataValidationError("output_limit_bytes must be greater than 0")
            if network_enabled:
                raise MasterDataValidationError("network_enabled must be false for MVP Python grading")
            if package_policy != "STDLIB_ONLY":
                raise MasterDataValidationError(
                    "package_policy is invalid for MVP Python grading",
                    details={"package_policy": package_policy, "allowed_values": ["STDLIB_ONLY"]},
                )

            python_runtime_contract = {
                "runtime_version": runtime_version,
                "entrypoint_mode": entrypoint_mode,
                "entrypoint_function": entrypoint_function,
                "memory_limit_mb": memory_limit_mb,
                "output_limit_bytes": output_limit_bytes,
                "network_enabled": False,
                "filesystem_policy": filesystem_policy,
                "package_policy": package_policy,
                "visibility_policy": visibility_policy,
            }

        expected_answer_text = normalized.get("expected_answer_text")
        if isinstance(expected_answer_text, str):
            expected_answer_text = expected_answer_text.strip() or None
        elif expected_answer_text is not None:
            expected_answer_text = str(expected_answer_text).strip() or None

        expected_answer_json = normalized.get("expected_answer_json")
        if expected_answer_json is not None and not isinstance(expected_answer_json, dict):
            raise MasterDataValidationError("expected_answer_json must be an object")

        mcq_options = normalized.get("mcq_options")
        if mcq_options is not None:
            if not isinstance(mcq_options, list):
                raise MasterDataValidationError("mcq_options must be an array of strings")
            normalized_options = [str(item).strip() for item in mcq_options if str(item).strip()]
            mcq_options = normalized_options

        return {
            "question_no": question_no,
            "question_title": question_title,
            "prompt_text": prompt_text,
            "question_type": authoring_type,
            "db_question_type": self._map_db_question_type(authoring_type),
            "response_mode": response_mode,
            "render_component": render_component,
            "input_source": default_input_source,
            "answer_language": answer_language,
            "max_score": max_score_decimal,
            "grading_engine_code": grading_engine_code,
            "comparison_method": comparison_method,
            "timeout_seconds": timeout_seconds,
            "expected_answer_text": expected_answer_text,
            "expected_answer_json": expected_answer_json,
            "status": self._normalize_status(normalized.get("status")),
            "required": bool(normalized.get("required", True)),
            "mcq_options": mcq_options or [],
            "python_runtime_contract": python_runtime_contract,
        }

    @staticmethod
    def _normalize_comparison_method(value: object) -> str:
        normalized = str(value or "").strip().upper()
        aliases = {
            "RESULT_SET_MATCH": "EXACT_RESULT_SET",
            "EXACT_MATCH": "EXACT_RESULT_SET",
            "SQL_RESULT_COMPARATOR": "EXACT_RESULT_SET",
        }
        return aliases.get(normalized, normalized)

    def _resolve_grading_engine_id(self, *, grading_engine_code: str, conn: object | None) -> int:
        engine = self._grading_engine_repository.get_grading_engine_by_code(grading_engine_code, conn=conn)
        if engine is None:
            raise MasterDataValidationError(
                "grading_engine_code does not exist",
                details={"grading_engine_code": grading_engine_code},
            )
        engine_id = int(engine["grading_engine_id"])
        if self._delivery_profile_service.grading_engine_is_active(grading_engine_id=engine_id, conn=conn) is not True:
            raise MasterDataValidationError(
                "grading_engine_code must reference an ACTIVE grading engine",
                details={"grading_engine_code": grading_engine_code},
            )
        return engine_id

    def _requires_expected_answer(self, *, authoring_type: str, grading_engine_code: str) -> bool:
        return authoring_type in {"TEXTBOX_SQL", "MCQ_SINGLE"} or grading_engine_code in self.AUTO_GRADED_ENGINES

    def _assert_question_no_unique(
        self,
        *,
        exam_version_id: int,
        question_no: int,
        ignore_question_template_id: int | None = None,
        conn: object | None,
    ) -> None:
        rows, _ = self._question_grading_profile_repository.list_profiles(
            exam_version_id=int(exam_version_id),
            question_template_id=None,
            status=None,
            input_source=None,
            offset=0,
            limit=500,
            conn=conn,
        )
        for row in rows:
            if str(row.get("status") or "").strip().upper() == "RETIRED":
                continue
            question_template_id = int(row["question_template_id"])
            if ignore_question_template_id is not None and question_template_id == int(ignore_question_template_id):
                continue
            profile = self._question_grading_profile_repository.get_profile_by_id(
                int(row["question_grading_profile_id"]),
                conn=conn,
            )
            metadata = profile.get("metadata_json") if isinstance(profile and profile.get("metadata_json"), dict) else {}
            existing_question_no = int(metadata.get("question_no") or 0)
            if existing_question_no == int(question_no):
                raise MasterDataValidationError(
                    "question_no already exists in exam version",
                    details={
                        "exam_version_id": int(exam_version_id),
                        "question_no": int(question_no),
                        "question_template_id": question_template_id,
                    },
                )

    def _assert_expected_answer_if_required(self, *, payload: dict) -> None:
        if not self._requires_expected_answer(
            authoring_type=str(payload["question_type"]),
            grading_engine_code=str(payload["grading_engine_code"]),
        ):
            return
        has_text = bool(payload.get("expected_answer_text"))
        has_json = isinstance(payload.get("expected_answer_json"), dict) and bool(payload.get("expected_answer_json"))
        if not (has_text or has_json):
            raise MasterDataValidationError(
                "expected_answer is required for auto-graded question",
                details={"question_type": payload["question_type"], "grading_engine_code": payload["grading_engine_code"]},
            )

    @staticmethod
    def _solution_type_for_question_type(question_type: str, *, has_text: bool) -> str:
        if question_type == "TEXTBOX_SQL":
            return "SQL_REFERENCE_QUERY" if has_text else "SQL_EXPECTED_RESULT_STATIC"
        if question_type == "MCQ_SINGLE":
            return "EXTERNAL_GRADER_CONFIG"
        return "MANUAL_RUBRIC"

    @staticmethod
    def _expected_answer_json_payload(payload: dict) -> dict | None:
        expected_answer_json = payload.get("expected_answer_json")
        if payload["question_type"] != "MCQ_SINGLE":
            return expected_answer_json

        mcq_payload: dict[str, object] = {}
        if isinstance(expected_answer_json, dict):
            mcq_payload.update(expected_answer_json)
        if payload.get("expected_answer_text"):
            mcq_payload["expected_option"] = payload["expected_answer_text"]
        if payload.get("mcq_options"):
            mcq_payload["options"] = payload["mcq_options"]
        return mcq_payload or None

    def _upsert_expected_answer(self, *, question_template_id: int, payload: dict, actor_user_id: int, conn: object | None) -> None:
        has_text = bool(payload.get("expected_answer_text"))
        has_json = isinstance(payload.get("expected_answer_json"), dict) and bool(payload.get("expected_answer_json"))
        if not (has_text or has_json):
            return
        self._assessment_repository.create_expected_answer(
            question_id=int(question_template_id),
            payload={
                "solution_type": self._solution_type_for_question_type(
                    str(payload["question_type"]),
                    has_text=has_text,
                ),
                "solution_payload": payload.get("expected_answer_text"),
                "solution_payload_json": self._expected_answer_json_payload(payload),
                "status": "ACTIVE",
            },
            actor_user_id=int(actor_user_id),
            conn=conn,
        )

    def _build_profile_metadata(self, *, payload: dict) -> dict:
        metadata = {
            "question_no": int(payload["question_no"]),
            "response_mode": payload["response_mode"],
            "render_component": payload["render_component"],
            "ui_mode": payload["render_component"],
            "required": bool(payload["required"]),
            "authoring_question_type": payload["question_type"],
            "mcq_options": payload["mcq_options"],
        }
        if payload.get("python_runtime_contract") is not None:
            metadata["python_runtime_contract"] = dict(payload["python_runtime_contract"])
        return metadata

    def _build_item(
        self,
        *,
        template: dict,
        profile_summary: dict,
        profile_full: dict | None,
        has_expected_answer: bool,
    ) -> dict:
        metadata = profile_full.get("metadata_json") if isinstance(profile_full and profile_full.get("metadata_json"), dict) else {}
        return {
            "question_template_id": int(template["question_template_id"]),
            "question_grading_profile_id": int(profile_summary["question_grading_profile_id"]),
            "question_no": int(metadata.get("question_no") or 0),
            "question_title": template.get("title"),
            "prompt_text": template.get("template_text"),
            "question_type": metadata.get("authoring_question_type") or template.get("question_type"),
            "response_mode": metadata.get("response_mode"),
            "render_component": metadata.get("render_component"),
            "input_source": profile_summary.get("input_source"),
            "grading_engine_code": profile_summary.get("grading_engine_code"),
            "comparison_method": profile_summary.get("comparison_method"),
            "max_score": self._safe_float(profile_summary.get("max_score")) or self._safe_float(template.get("default_score")),
            "status": profile_summary.get("status"),
            "required": bool(metadata.get("required", True)),
            "mcq_options": metadata.get("mcq_options") if isinstance(metadata.get("mcq_options"), list) else [],
            "has_expected_answer": bool(has_expected_answer),
        }

    def _build_readiness_summary(self, *, items: list[dict]) -> dict:
        missing_items: list[dict] = []
        if not items:
            missing_items.append({"code": "question_missing", "message": "Exam version has no authored questions"})
            return {"ready": False, "missing_items": missing_items}

        for item in items:
            question_template_id = int(item["question_template_id"])
            if not item.get("response_mode") or not item.get("render_component"):
                missing_items.append(
                    {
                        "code": "question_response_profile_missing",
                        "message": "Question is missing response profile metadata",
                        "question_template_id": question_template_id,
                    }
                )
            if not item.get("grading_engine_code") or not item.get("comparison_method"):
                missing_items.append(
                    {
                        "code": "question_grading_profile_missing",
                        "message": "Question is missing grading profile",
                        "question_template_id": question_template_id,
                    }
                )
            requires_expected = self._requires_expected_answer(
                authoring_type=str(item.get("question_type") or ""),
                grading_engine_code=str(item.get("grading_engine_code") or ""),
            )
            if requires_expected and not bool(item.get("has_expected_answer")):
                missing_items.append(
                    {
                        "code": "question_expected_answer_missing",
                        "message": "Auto-graded question is missing expected answer",
                        "question_template_id": question_template_id,
                    }
                )
        return {"ready": len(missing_items) == 0, "missing_items": missing_items}

    def list_exam_version_questions(self, *, exam_version_id: int, actor: dict) -> dict:
        _ = actor
        if not self._question_grading_profile_repository.exam_version_exists(int(exam_version_id)):
            raise MasterDataNotFoundError("Exam version not found", details={"exam_version_id": int(exam_version_id)})

        rows, _ = self._question_grading_profile_repository.list_profiles(
            exam_version_id=int(exam_version_id),
            question_template_id=None,
            status=None,
            input_source=None,
            offset=0,
            limit=200,
        )
        items: list[dict] = []
        for row in rows:
            if str(row.get("status") or "").strip().upper() == "RETIRED":
                continue
            question_template_id = int(row["question_template_id"])
            template = self._assessment_repository.get_question_template_by_id(question_template_id)
            if template is None:
                continue
            profile_full = self._question_grading_profile_repository.get_profile_by_id(int(row["question_grading_profile_id"]))
            has_expected = self._assessment_repository.question_has_active_expected_answer(question_template_id)
            items.append(
                self._build_item(
                    template=template,
                    profile_summary=row,
                    profile_full=profile_full,
                    has_expected_answer=has_expected,
                )
            )

        items.sort(key=lambda item: (int(item.get("question_no") or 0), int(item["question_template_id"])))
        return {"items": items, "readiness_summary": self._build_readiness_summary(items=items)}

    def create_exam_version_question(self, *, exam_version_id: int, command: dict, actor: dict) -> dict:
        actor_user_id = int(actor.get("user_id") or 0)
        if actor_user_id <= 0:
            raise MasterDataValidationError("actor user_id is required")

        payload = self._normalize_command(command=command)
        self._assert_expected_answer_if_required(payload=payload)

        with self._transaction_scope() as conn:
            self._delivery_profile_service.ensure_exam_version_editable(exam_version_id=int(exam_version_id), conn=conn)
            self._assert_question_no_unique(
                exam_version_id=int(exam_version_id),
                question_no=int(payload["question_no"]),
                ignore_question_template_id=None,
                conn=conn,
            )
            engine_id = self._resolve_grading_engine_id(grading_engine_code=payload["grading_engine_code"], conn=conn)
            template = self._assessment_repository.create_question(
                payload={
                    "template_code": self._next_available_template_code(
                        exam_version_id=int(exam_version_id),
                        question_no=int(payload["question_no"]),
                        conn=conn,
                    ),
                    "question_type": payload["db_question_type"],
                    "title": payload["question_title"],
                    "template_text": payload["prompt_text"],
                    "default_score": payload["max_score"],
                    "generator_type": "STATIC",
                    "generator_version": "AUTHORING_MVP",
                    "status": payload["status"],
                },
                created_by=actor_user_id,
                conn=conn,
            )
            profile = self._question_grading_profile_repository.create_profile(
                question_template_id=int(template["question_template_id"]),
                exam_version_id=int(exam_version_id),
                input_source=payload["input_source"],
                answer_language=payload["answer_language"],
                requires_capture=False,
                required_capture_type=None,
                capture_profile_id=None,
                grading_engine_id=int(engine_id),
                comparison_method=payload["comparison_method"],
                timeout_seconds=payload["timeout_seconds"],
                max_score=payload["max_score"],
                status=payload["status"],
                metadata_json=self._build_profile_metadata(payload=payload),
                conn=conn,
            )
            self._upsert_expected_answer(
                question_template_id=int(template["question_template_id"]),
                payload=payload,
                actor_user_id=actor_user_id,
                conn=conn,
            )
            summary = self._question_grading_profile_repository.get_profile_summary_by_id(
                int(profile["question_grading_profile_id"]),
                conn=conn,
            )
            if summary is None:
                raise MasterDataNotFoundError(
                    "Question grading profile not found",
                    details={"question_grading_profile_id": int(profile["question_grading_profile_id"])},
                )
            has_expected = self._assessment_repository.question_has_active_expected_answer(
                int(template["question_template_id"]),
                conn=conn,
            )
            return self._build_item(
                template=template,
                profile_summary=summary,
                profile_full=profile,
                has_expected_answer=has_expected,
            )

    def update_exam_version_question(
        self,
        *,
        exam_version_id: int,
        question_template_id: int,
        command: dict,
        actor: dict,
    ) -> dict:
        actor_user_id = int(actor.get("user_id") or 0)
        if actor_user_id <= 0:
            raise MasterDataValidationError("actor user_id is required")

        payload = self._normalize_command(command=command)
        self._assert_expected_answer_if_required(payload=payload)

        with self._transaction_scope() as conn:
            self._delivery_profile_service.ensure_exam_version_editable(exam_version_id=int(exam_version_id), conn=conn)
            self._assert_question_no_unique(
                exam_version_id=int(exam_version_id),
                question_no=int(payload["question_no"]),
                ignore_question_template_id=int(question_template_id),
                conn=conn,
            )
            template = self._assessment_repository.get_question_template_by_id(int(question_template_id), conn=conn)
            if template is None:
                raise MasterDataNotFoundError(
                    "Question template not found",
                    details={"question_template_id": int(question_template_id)},
                )

            updated_template = self._assessment_repository.patch_question(
                question_id=int(question_template_id),
                payload={
                    "title": payload["question_title"],
                    "template_text": payload["prompt_text"],
                    "default_score": payload["max_score"],
                    "status": payload["status"],
                },
                conn=conn,
            )
            if updated_template is None:
                raise MasterDataNotFoundError(
                    "Question template not found",
                    details={"question_template_id": int(question_template_id)},
                )

            engine_id = self._resolve_grading_engine_id(grading_engine_code=payload["grading_engine_code"], conn=conn)
            existing = self._question_grading_profile_repository.get_existing_profile_for_question(
                question_template_id=int(question_template_id),
                exam_version_id=int(exam_version_id),
                conn=conn,
            )
            if existing is None:
                profile = self._question_grading_profile_repository.create_profile(
                    question_template_id=int(question_template_id),
                    exam_version_id=int(exam_version_id),
                    input_source=payload["input_source"],
                    answer_language=payload["answer_language"],
                    requires_capture=False,
                    required_capture_type=None,
                    capture_profile_id=None,
                    grading_engine_id=int(engine_id),
                    comparison_method=payload["comparison_method"],
                    timeout_seconds=payload["timeout_seconds"],
                    max_score=payload["max_score"],
                    status=payload["status"],
                    metadata_json=self._build_profile_metadata(payload=payload),
                    conn=conn,
                )
            else:
                profile = self._question_grading_profile_repository.update_profile(
                    question_grading_profile_id=int(existing["question_grading_profile_id"]),
                    payload={
                        "input_source": payload["input_source"],
                        "answer_language": payload["answer_language"],
                        "requires_capture": False,
                        "required_capture_type": None,
                        "capture_profile_id": None,
                        "grading_engine_id": int(engine_id),
                        "comparison_method": payload["comparison_method"],
                        "timeout_seconds": payload["timeout_seconds"],
                        "max_score": payload["max_score"],
                        "status": payload["status"],
                        "metadata_json": self._build_profile_metadata(payload=payload),
                    },
                    conn=conn,
                )
                if profile is None:
                    raise MasterDataNotFoundError(
                        "Question grading profile not found",
                        details={"question_grading_profile_id": int(existing["question_grading_profile_id"])},
                    )

            self._upsert_expected_answer(
                question_template_id=int(question_template_id),
                payload=payload,
                actor_user_id=actor_user_id,
                conn=conn,
            )
            summary = self._question_grading_profile_repository.get_profile_summary_by_id(
                int(profile["question_grading_profile_id"]),
                conn=conn,
            )
            if summary is None:
                raise MasterDataNotFoundError(
                    "Question grading profile not found",
                    details={"question_grading_profile_id": int(profile["question_grading_profile_id"])},
                )
            has_expected = self._assessment_repository.question_has_active_expected_answer(
                int(question_template_id),
                conn=conn,
            )
            return self._build_item(
                template=updated_template,
                profile_summary=summary,
                profile_full=profile,
                has_expected_answer=has_expected,
            )


def build_exam_version_question_authoring_service() -> ExamVersionQuestionAuthoringService:
    """FastAPI dependency factory for exam-version question authoring service."""

    return ExamVersionQuestionAuthoringService()
