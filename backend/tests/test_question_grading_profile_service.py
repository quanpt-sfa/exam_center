"""Service-level contract tests for question grading profile input_source semantics."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone

import pytest

from app.modules.master_data.common.errors import MasterDataValidationError
from app.modules.master_data.services.question_grading_profile_service import QuestionGradingProfileService


class _FakeQuestionGradingProfileRepository:
    def __init__(self) -> None:
        self.rows: dict[int, dict] = {}
        self.next_id = 1
        self.valid_question_templates: set[int] = {101, 102, 103, 104, 105}
        self.valid_exam_versions: set[int] = {2001, 2002, 2003, 2004, 2005}

    def list_profiles(
        self,
        *,
        exam_version_id: int | None,
        question_template_id: int | None,
        status: str | None,
        input_source: str | None,
        offset: int,
        limit: int,
        conn=None,
    ) -> tuple[list[dict], int]:
        _ = (offset, limit, conn)
        items = list(self.rows.values())
        if exam_version_id is not None:
            items = [row for row in items if int(row.get("exam_version_id")) == int(exam_version_id)]
        if question_template_id is not None:
            items = [row for row in items if int(row.get("question_template_id")) == int(question_template_id)]
        if status is not None:
            items = [row for row in items if str(row.get("status") or "").upper() == str(status).upper()]
        if input_source is not None:
            items = [row for row in items if str(row.get("input_source") or "").upper() == str(input_source).upper()]
        items.sort(key=lambda row: int(row["question_grading_profile_id"]), reverse=True)
        return [dict(row) for row in items], len(items)

    def question_template_exists(self, question_template_id: int, conn=None) -> bool:
        _ = conn
        return int(question_template_id) in self.valid_question_templates

    def exam_version_exists(self, exam_version_id: int, conn=None) -> bool:
        _ = conn
        return int(exam_version_id) in self.valid_exam_versions

    def get_existing_profile_for_question(self, *, question_template_id: int, exam_version_id: int | None, conn=None) -> dict | None:
        _ = conn
        for row in self.rows.values():
            if int(row["question_template_id"]) != int(question_template_id):
                continue
            if row.get("exam_version_id") != exam_version_id:
                continue
            return {
                "question_grading_profile_id": int(row["question_grading_profile_id"]),
                "question_template_id": int(row["question_template_id"]),
                "exam_version_id": row.get("exam_version_id"),
            }
        return None

    def create_profile(self, **kwargs) -> dict:
        _ = kwargs.pop("conn", None)
        row = {
            "question_grading_profile_id": self.next_id,
            "question_template_id": int(kwargs["question_template_id"]),
            "exam_version_id": kwargs.get("exam_version_id"),
            "input_source": kwargs["input_source"],
            "answer_language": kwargs["answer_language"],
            "requires_capture": kwargs["requires_capture"],
            "required_capture_type": kwargs.get("required_capture_type"),
            "capture_profile_id": kwargs.get("capture_profile_id"),
            "grading_engine_id": kwargs["grading_engine_id"],
            "grading_engine_code": {
                777: "MANUAL_RUBRIC",
                778: "SQL_RESULT_COMPARATOR",
            }.get(int(kwargs["grading_engine_id"]), "ENGINE"),
            "capture_profile_code": {901: "CAPTURE-901", 902: "CAPTURE-902", 903: "CAPTURE-903"}.get(kwargs.get("capture_profile_id")),
            "comparison_method": kwargs["comparison_method"],
            "timeout_seconds": kwargs.get("timeout_seconds"),
            "max_score": kwargs.get("max_score"),
            "status": kwargs["status"],
            "metadata_json": kwargs.get("metadata_json") or {},
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
        }
        self.rows[self.next_id] = row
        self.next_id += 1
        return dict(row)

    def update_profile(self, *, question_grading_profile_id: int, payload: dict, conn=None) -> dict | None:
        _ = conn
        row = self.rows.get(int(question_grading_profile_id))
        if row is None:
            return None
        row.update(payload)
        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)

    def get_profile_summary_by_id(self, question_grading_profile_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.rows.get(int(question_grading_profile_id))
        if row is None:
            return None
        return {
            "question_grading_profile_id": row.get("question_grading_profile_id"),
            "question_template_id": row.get("question_template_id"),
            "exam_version_id": row.get("exam_version_id"),
            "input_source": row.get("input_source"),
            "answer_language": row.get("answer_language"),
            "requires_capture": row.get("requires_capture"),
            "required_capture_type": row.get("required_capture_type"),
            "capture_profile_code": row.get("capture_profile_code"),
            "grading_engine_code": row.get("grading_engine_code"),
            "comparison_method": row.get("comparison_method"),
            "timeout_seconds": row.get("timeout_seconds"),
            "max_score": row.get("max_score"),
            "status": row.get("status"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    def get_profile_by_id(self, question_grading_profile_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.rows.get(int(question_grading_profile_id))
        return dict(row) if row else None


class _FakeGradingEngineRepository:
    def get_grading_engine_by_code(self, grading_engine_code: str, conn=None) -> dict | None:
        _ = conn
        normalized = str(grading_engine_code).strip().upper()
        if normalized == "MANUAL_RUBRIC":
            return {"grading_engine_id": 777, "engine_code": "MANUAL_RUBRIC"}
        if normalized == "SQL_RESULT_COMPARATOR":
            return {"grading_engine_id": 778, "engine_code": "SQL_RESULT_COMPARATOR"}
        return None


class _FakeExamVersionDeliveryProfileService:
    def __init__(self) -> None:
        self.exam_modality_by_version: dict[int, dict] = {}

    def ensure_exam_version_editable(self, *, exam_version_id: int, conn=None) -> None:
        _ = (exam_version_id, conn)

    def grading_engine_is_active(self, *, grading_engine_id: int, conn=None) -> bool | None:
        _ = conn
        return int(grading_engine_id) in {777, 778}

    def capture_profile_is_active(self, *, capture_profile_id: int, conn=None) -> bool | None:
        _ = conn
        return int(capture_profile_id) in {901, 902, 903}

    def capture_profile_supports_engine(self, *, capture_profile_id: int, grading_engine_id: int, conn=None) -> bool | None:
        _ = conn
        return (int(capture_profile_id), int(grading_engine_id)) in {
            (901, 777),
            (901, 778),
            (902, 777),
            (903, 777),
        }

    def get_delivery_profile_for_exam_version(self, *, exam_version_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.exam_modality_by_version.get(int(exam_version_id))
        return dict(row) if row else None


def _build_service() -> QuestionGradingProfileService:
    return QuestionGradingProfileService(
        question_grading_profile_repository=_FakeQuestionGradingProfileRepository(),
        grading_engine_repository=_FakeGradingEngineRepository(),
        exam_version_delivery_profile_service=_FakeExamVersionDeliveryProfileService(),
    )


def test_create_question_grading_profile_accepts_sealed_file_ref_as_non_capture() -> None:
    service = _build_service()

    payload = service.create_question_grading_profile(
        command={
            "question_template_id": 101,
            "exam_version_id": 2001,
            "input_source": "SEALED_FILE_REF",
            "answer_language": "NONE",
            "requires_capture": False,
            "required_capture_type": None,
            "capture_profile_id": None,
            "grading_engine_code": "MANUAL_RUBRIC",
            "comparison_method": "MANUAL_RUBRIC",
            "status": "ACTIVE",
            "metadata_json": {"answer_format": "FILE_REF"},
        },
        actor={"user_id": 1},
    )

    assert payload["input_source"] == "SEALED_FILE_REF"
    assert payload["requires_capture"] is False
    assert payload["required_capture_type"] is None
    assert payload["capture_profile_code"] is None
    assert payload["grading_engine_code"] == "MANUAL_RUBRIC"
    assert payload["comparison_method"] == "MANUAL_RUBRIC"


def test_create_question_grading_profile_rejects_capture_fields_for_sealed_file_ref() -> None:
    service = _build_service()

    with pytest.raises(MasterDataValidationError, match="capture_profile_id must be null when requires_capture is false"):
        service.create_question_grading_profile(
            command={
                "question_template_id": 102,
                "exam_version_id": 2001,
                "input_source": "SEALED_FILE_REF",
                "answer_language": "NONE",
                "requires_capture": False,
                "required_capture_type": None,
                "capture_profile_id": 901,
                "grading_engine_code": "MANUAL_RUBRIC",
                "comparison_method": "MANUAL_RUBRIC",
                "status": "ACTIVE",
            },
            actor={"user_id": 1},
        )

    with pytest.raises(MasterDataValidationError, match="required_capture_type must be null when requires_capture is false"):
        service.create_question_grading_profile(
            command={
                "question_template_id": 102,
                "exam_version_id": 2001,
                "input_source": "SEALED_FILE_REF",
                "answer_language": "NONE",
                "requires_capture": False,
                "required_capture_type": "FILE_UPLOAD",
                "capture_profile_id": None,
                "grading_engine_code": "MANUAL_RUBRIC",
                "comparison_method": "MANUAL_RUBRIC",
                "status": "ACTIVE",
            },
            actor={"user_id": 1},
        )


def test_capture_input_sources_do_not_include_sealed_file_ref() -> None:
    assert "SEALED_FILE_REF" not in QuestionGradingProfileService.CAPTURE_INPUT_SOURCES
    assert "FILE_ARTIFACT_CAPTURE" in QuestionGradingProfileService.CAPTURE_INPUT_SOURCES


def test_file_artifact_capture_still_requires_capture_context() -> None:
    service = _build_service()

    with pytest.raises(MasterDataValidationError, match="capture_profile_id is required when requires_capture is true"):
        service.create_question_grading_profile(
            command={
                "question_template_id": 103,
                "exam_version_id": 2001,
                "input_source": "FILE_ARTIFACT_CAPTURE",
                "answer_language": "NONE",
                "requires_capture": False,
                "required_capture_type": "FILE_UPLOAD",
                "capture_profile_id": None,
                "grading_engine_code": "MANUAL_RUBRIC",
                "comparison_method": "FILE_ARTIFACT_MATCH",
                "status": "ACTIVE",
            },
            actor={"user_id": 1},
        )

    payload = service.create_question_grading_profile(
        command={
            "question_template_id": 103,
            "exam_version_id": 2001,
            "input_source": "FILE_ARTIFACT_CAPTURE",
            "answer_language": "NONE",
            "requires_capture": True,
            "required_capture_type": "FILE_UPLOAD",
            "capture_profile_id": 901,
            "grading_engine_code": "MANUAL_RUBRIC",
            "comparison_method": "FILE_ARTIFACT_MATCH",
            "status": "ACTIVE",
        },
        actor={"user_id": 1},
    )

    assert payload["requires_capture"] is True
    assert payload["required_capture_type"] == "FILE_UPLOAD"
    assert payload["capture_profile_code"] == "CAPTURE-901"


def test_legacy_non_capture_text_and_json_sources_still_work() -> None:
    service = _build_service()

    text_payload = service.create_question_grading_profile(
        command={
            "question_template_id": 104,
            "exam_version_id": 2002,
            "input_source": "SEALED_TEXT_ANSWER",
            "answer_language": "SQL",
            "requires_capture": False,
            "required_capture_type": None,
            "capture_profile_id": None,
            "grading_engine_code": "SQL_RESULT_COMPARATOR",
            "comparison_method": "EXACT_RESULT_SET",
            "status": "ACTIVE",
        },
        actor={"user_id": 1},
    )
    json_payload = service.create_question_grading_profile(
        command={
            "question_template_id": 105,
            "exam_version_id": 2003,
            "input_source": "SEALED_JSON_ANSWER",
            "answer_language": "JSON",
            "requires_capture": False,
            "required_capture_type": None,
            "capture_profile_id": None,
            "grading_engine_code": "MANUAL_RUBRIC",
            "comparison_method": "TEXT_RULE",
            "status": "ACTIVE",
        },
        actor={"user_id": 1},
    )

    assert text_payload["input_source"] == "SEALED_TEXT_ANSWER"
    assert text_payload["requires_capture"] is False
    assert json_payload["input_source"] == "SEALED_JSON_ANSWER"
    assert json_payload["requires_capture"] is False


def test_delivery_capture_modalities_still_require_capture_enabled_profiles() -> None:
    delivery_service = _FakeExamVersionDeliveryProfileService()
    delivery_service.exam_modality_by_version[2004] = {
        "exam_modality": "STUDENT_DATABASE",
        "requires_capture": True,
    }
    service = QuestionGradingProfileService(
        question_grading_profile_repository=_FakeQuestionGradingProfileRepository(),
        grading_engine_repository=_FakeGradingEngineRepository(),
        exam_version_delivery_profile_service=delivery_service,
    )

    with pytest.raises(MasterDataValidationError, match="Exam modality requires capture-enabled question grading profile"):
        service.create_question_grading_profile(
            command={
                "question_template_id": 101,
                "exam_version_id": 2004,
                "input_source": "SEALED_FILE_REF",
                "answer_language": "NONE",
                "requires_capture": False,
                "required_capture_type": None,
                "capture_profile_id": None,
                "grading_engine_code": "MANUAL_RUBRIC",
                "comparison_method": "MANUAL_RUBRIC",
                "status": "ACTIVE",
            },
            actor={"user_id": 1},
        )