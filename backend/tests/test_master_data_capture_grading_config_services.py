"""Service-level tests for MD-6 capture/grading configuration workflows."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone

import pytest

from app.modules.master_data.common.errors import MasterDataConflictError
from app.modules.master_data.common.errors import MasterDataNotFoundError
from app.modules.master_data.common.errors import MasterDataValidationError
from app.modules.master_data.services.capture_extractor_query_service import CaptureExtractorQueryService
from app.modules.master_data.services.capture_profile_service import CaptureProfileService
from app.modules.master_data.services.grading_engine_service import GradingEngineService
from app.modules.master_data.services.question_grading_profile_service import QuestionGradingProfileService


class InMemoryCaptureProfileRepository:
    def __init__(self) -> None:
        self.rows: dict[int, dict] = {}
        self.next_id = 1

    def get_capture_profile_by_code(self, capture_profile_code: str, conn=None) -> dict | None:
        _ = conn
        code = capture_profile_code.strip().upper()
        for row in self.rows.values():
            if row["profile_code"] == code:
                return dict(row)
        return None

    def create_capture_profile(self, **kwargs) -> dict:
        _ = kwargs.pop("conn", None)
        row = {
            "capture_profile_id": self.next_id,
            "profile_code": kwargs["capture_profile_code"],
            "profile_name": kwargs["profile_name"],
            "source_type": kwargs["source_type"],
            "source_location_mode": kwargs["source_location_mode"],
            "default_capture_timing": kwargs["default_capture_timing"],
            "requires_agent": kwargs["requires_agent"],
            "status": kwargs["status"],
            "metadata_json": kwargs.get("metadata_json") or {},
            "supported_engine_codes": [],
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
        }
        self.rows[self.next_id] = row
        self.next_id += 1
        return dict(row)

    def get_capture_profile_summary_by_id(self, capture_profile_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.rows.get(int(capture_profile_id))
        return dict(row) if row else None

    def get_capture_profile_by_id(self, capture_profile_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.rows.get(int(capture_profile_id))
        return dict(row) if row else None

    def count_active_question_profile_dependencies(self, capture_profile_id: int, conn=None) -> int:
        _ = capture_profile_id
        _ = conn
        return 0

    def count_active_delivery_profile_dependencies(self, capture_profile_id: int, conn=None) -> int:
        _ = capture_profile_id
        _ = conn
        return 0


class InMemoryExtractorQueryRepository:
    def __init__(self) -> None:
        self.rows: dict[int, dict] = {}
        self.next_id = 1

    def get_query_by_code(self, capture_profile_id: int, query_code: str, conn=None) -> dict | None:
        _ = conn
        code = query_code.strip().upper()
        for row in self.rows.values():
            if int(row["capture_profile_id"]) == int(capture_profile_id) and row["query_code"] == code:
                return dict(row)
        return None

    def create_query(self, **kwargs) -> dict:
        _ = kwargs.pop("conn", None)
        row = {
            "capture_extractor_query_id": self.next_id,
            "capture_profile_id": int(kwargs["capture_profile_id"]),
            "query_code": kwargs["query_code"],
            "query_name": kwargs["query_name"],
            "extractor_kind": kwargs["extractor_kind"],
            "query_text": kwargs.get("query_text"),
            "output_dataset_name": kwargs["output_dataset_name"],
            "is_required": kwargs["is_required"],
            "execution_order": kwargs["execution_order"],
            "timeout_seconds": kwargs.get("timeout_seconds"),
            "normalizer_code": kwargs.get("normalizer_code"),
            "status": kwargs["status"],
            "metadata_json": kwargs.get("metadata_json") or {},
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
        }
        self.rows[self.next_id] = row
        self.next_id += 1
        return dict(row)


class InMemoryGradingEngineRepository:
    def __init__(self) -> None:
        self.rows: dict[int, dict] = {}
        self.next_id = 1

    def get_grading_engine_by_code(self, grading_engine_code: str, conn=None) -> dict | None:
        _ = conn
        code = grading_engine_code.strip().upper()
        for row in self.rows.values():
            if row["engine_code"] == code:
                return dict(row)
        return None

    def create_grading_engine(self, **kwargs) -> dict:
        _ = kwargs.pop("conn", None)
        row = {
            "grading_engine_id": self.next_id,
            "engine_code": kwargs["grading_engine_code"],
            "engine_name": kwargs["engine_name"],
            "engine_category": kwargs["engine_category"],
            "runtime_kind": kwargs["runtime_kind"],
            "description": kwargs.get("description"),
            "is_active": kwargs["is_active"],
            "metadata_json": kwargs.get("metadata_json") or {},
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
        }
        self.rows[self.next_id] = row
        self.next_id += 1
        return dict(row)

    def get_grading_engine_summary_by_id(self, grading_engine_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.rows.get(int(grading_engine_id))
        return dict(row) if row else None


class InMemoryQuestionGradingProfileRepository:
    def __init__(self) -> None:
        self.rows: dict[int, dict] = {}
        self.next_id = 1
        self.valid_question_templates: set[int] = {1001}
        self.valid_exam_versions: set[int] = {2001}

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
            return {"question_grading_profile_id": row["question_grading_profile_id"]}
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
            "grading_engine_code": "SQL_RESULT_COMPARATOR",
            "capture_profile_code": "SQLSERVER_SERVER_HOSTED_PROFILE" if kwargs.get("capture_profile_id") else None,
            "comparison_method": kwargs["comparison_method"],
            "timeout_seconds": kwargs.get("timeout_seconds"),
            "max_score": kwargs.get("max_score"),
            "status": kwargs["status"],
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
        }
        self.rows[self.next_id] = row
        self.next_id += 1
        return dict(row)

    def get_profile_summary_by_id(self, question_grading_profile_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.rows.get(int(question_grading_profile_id))
        return dict(row) if row else None

    def get_profile_by_id(self, question_grading_profile_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.rows.get(int(question_grading_profile_id))
        return dict(row) if row else None


class InMemoryManualRubricEngineRepository:
    def __init__(self) -> None:
        self.by_code = {"MANUAL_RUBRIC": {"grading_engine_id": 777, "engine_code": "MANUAL_RUBRIC"}}

    def get_grading_engine_by_code(self, grading_engine_code: str, conn=None) -> dict | None:
        _ = conn
        return self.by_code.get(str(grading_engine_code).strip().upper())


class StubDeliveryProfileService:
    def __init__(self) -> None:
        self.active_engines: dict[int, bool] = {501: True}
        self.active_capture_profiles: dict[int, bool] = {301: True}
        self.capture_support: set[tuple[int, int]] = {(301, 501)}

    def grading_engine_is_active(self, *, grading_engine_id: int, conn=None) -> bool | None:
        _ = conn
        return self.active_engines.get(int(grading_engine_id), False)

    def capture_profile_is_active(self, *, capture_profile_id: int, conn=None) -> bool | None:
        _ = conn
        return self.active_capture_profiles.get(int(capture_profile_id), False)

    def capture_profile_supports_engine(self, *, capture_profile_id: int, grading_engine_id: int, conn=None) -> bool | None:
        _ = conn
        return (int(capture_profile_id), int(grading_engine_id)) in self.capture_support

    def get_delivery_profile_for_exam_version(self, *, exam_version_id: int, conn=None) -> dict | None:
        _ = exam_version_id
        _ = conn
        return None

    def ensure_exam_version_editable(self, *, exam_version_id: int, conn=None) -> None:
        _ = exam_version_id
        _ = conn


def test_create_capture_profile_success() -> None:
    repo = InMemoryCaptureProfileRepository()
    service = CaptureProfileService(capture_profile_repository=repo)

    result = service.create_capture_profile(
        command={
            "capture_profile_code": "sql_profile_alpha",
            "profile_name": "SQL Profile Alpha",
            "source_type": "SQLSERVER_DATABASE",
            "source_location_mode": "SERVER_HOSTED",
            "default_capture_timing": "AFTER_SEAL",
            "requires_agent": False,
            "status": "ACTIVE",
            "metadata_json": {"connection_ref": "secret-ref"},
        },
        actor={"user_id": 1},
    )

    assert result["capture_profile_id"] == 1
    assert result["profile_code"] == "SQL_PROFILE_ALPHA"


def test_duplicate_capture_profile_code_rejected() -> None:
    repo = InMemoryCaptureProfileRepository()
    service = CaptureProfileService(capture_profile_repository=repo)

    command = {
        "capture_profile_code": "SQL_PROFILE_ALPHA",
        "profile_name": "SQL Profile Alpha",
        "source_type": "SQLSERVER_DATABASE",
        "source_location_mode": "SERVER_HOSTED",
        "default_capture_timing": "AFTER_SEAL",
        "requires_agent": False,
        "status": "ACTIVE",
    }

    service.create_capture_profile(command=command, actor={"user_id": 1})

    with pytest.raises(MasterDataConflictError):
        service.create_capture_profile(command=command, actor={"user_id": 1})


def test_create_extractor_query_success() -> None:
    profile_repo = InMemoryCaptureProfileRepository()
    profile_repo.create_capture_profile(
        capture_profile_code="SQL_PROFILE_ALPHA",
        profile_name="SQL Profile Alpha",
        source_type="SQLSERVER_DATABASE",
        source_location_mode="SERVER_HOSTED",
        default_capture_timing="AFTER_SEAL",
        requires_agent=False,
        description=None,
        status="ACTIVE",
        metadata_json={},
    )

    query_repo = InMemoryExtractorQueryRepository()
    service = CaptureExtractorQueryService(
        query_repository=query_repo,
        capture_profile_repository=profile_repo,
    )

    result = service.create_capture_extractor_query(
        capture_profile_id=1,
        command={
            "query_code": "Q1",
            "query_name": "Fetch sales",
            "extractor_kind": "SQL_QUERY",
            "query_text": "SELECT * FROM sales",
            "output_dataset_name": "sales_dataset",
            "execution_order": 1,
            "config_only": True,
        },
        actor={"user_id": 1},
    )

    assert result["capture_extractor_query_id"] == 1
    assert result["query_code"] == "Q1"


def test_extractor_query_invalid_capture_profile_rejected() -> None:
    service = CaptureExtractorQueryService(
        query_repository=InMemoryExtractorQueryRepository(),
        capture_profile_repository=InMemoryCaptureProfileRepository(),
    )

    with pytest.raises(MasterDataNotFoundError):
        service.create_capture_extractor_query(
            capture_profile_id=999,
            command={
                "query_code": "Q1",
                "query_name": "Fetch sales",
                "extractor_kind": "SQL_QUERY",
                "output_dataset_name": "sales_dataset",
                "config_only": True,
            },
            actor={"user_id": 1},
        )


def test_create_grading_engine_success() -> None:
    repo = InMemoryGradingEngineRepository()
    service = GradingEngineService(grading_engine_repository=repo)

    result = service.create_grading_engine(
        command={
            "grading_engine_code": "SQL_RESULT_COMPARATOR_X",
            "engine_name": "SQL Comparator X",
            "engine_category": "CODE_EXECUTION",
            "runtime_kind": "INTERNAL_WORKER",
            "is_active": True,
        },
        actor={"user_id": 1},
    )

    assert result["grading_engine_id"] == 1
    assert result["engine_code"] == "SQL_RESULT_COMPARATOR_X"


def test_duplicate_grading_engine_code_rejected() -> None:
    repo = InMemoryGradingEngineRepository()
    service = GradingEngineService(grading_engine_repository=repo)

    command = {
        "grading_engine_code": "SQL_RESULT_COMPARATOR_X",
        "engine_name": "SQL Comparator X",
        "engine_category": "CODE_EXECUTION",
        "runtime_kind": "INTERNAL_WORKER",
        "is_active": True,
    }

    service.create_grading_engine(command=command, actor={"user_id": 1})

    with pytest.raises(MasterDataConflictError):
        service.create_grading_engine(command=command, actor={"user_id": 1})


def test_create_question_grading_profile_success() -> None:
    repo = InMemoryQuestionGradingProfileRepository()
    delivery_service = StubDeliveryProfileService()
    service = QuestionGradingProfileService(
        question_grading_profile_repository=repo,
        exam_version_delivery_profile_service=delivery_service,
    )

    result = service.create_question_grading_profile(
        command={
            "question_template_id": 1001,
            "input_source": "SEALED_TEXT_ANSWER",
            "answer_language": "SQL",
            "requires_capture": False,
            "grading_engine_id": 501,
            "comparison_method": "EXACT_RESULT_SET",
            "status": "ACTIVE",
        },
        actor={"user_id": 1},
    )

    assert result["question_grading_profile_id"] == 1
    assert result["grading_engine_code"] == "SQL_RESULT_COMPARATOR"


def test_question_grading_profile_invalid_grading_engine_rejected() -> None:
    repo = InMemoryQuestionGradingProfileRepository()
    delivery_service = StubDeliveryProfileService()
    delivery_service.active_engines = {}

    service = QuestionGradingProfileService(
        question_grading_profile_repository=repo,
        exam_version_delivery_profile_service=delivery_service,
    )

    with pytest.raises(MasterDataValidationError):
        service.create_question_grading_profile(
            command={
                "question_template_id": 1001,
                "input_source": "SEALED_TEXT_ANSWER",
                "answer_language": "SQL",
                "requires_capture": False,
                "grading_engine_id": 999,
                "comparison_method": "EXACT_RESULT_SET",
                "status": "ACTIVE",
            },
            actor={"user_id": 1},
        )


def test_question_grading_profile_resolves_manual_rubric_engine_code() -> None:
    repo = InMemoryQuestionGradingProfileRepository()
    delivery_service = StubDeliveryProfileService()
    delivery_service.active_engines[777] = True
    service = QuestionGradingProfileService(
        question_grading_profile_repository=repo,
        grading_engine_repository=InMemoryManualRubricEngineRepository(),
        exam_version_delivery_profile_service=delivery_service,
    )

    result = service.create_question_grading_profile(
        command={
            "question_template_id": 1001,
            "exam_version_id": 2001,
            "input_source": "MANUAL",
            "answer_language": "NONE",
            "requires_capture": False,
            "grading_engine_code": "MANUAL_RUBRIC",
            "comparison_method": "MANUAL_RUBRIC",
            "status": "ACTIVE",
            "metadata_json": {"manual_review_policy": "ALWAYS"},
        },
        actor={"user_id": 1},
    )

    assert result["question_grading_profile_id"] == 1


def test_sensitive_fields_masked_not_returned() -> None:
    profile_repo = InMemoryCaptureProfileRepository()
    profile_repo.create_capture_profile(
        capture_profile_code="SQL_PROFILE_ALPHA",
        profile_name="SQL Profile Alpha",
        source_type="SQLSERVER_DATABASE",
        source_location_mode="SERVER_HOSTED",
        default_capture_timing="AFTER_SEAL",
        requires_agent=False,
        description=None,
        status="ACTIVE",
        metadata_json={"connection_ref": "secret-ref"},
    )

    query_repo = InMemoryExtractorQueryRepository()
    service = CaptureExtractorQueryService(
        query_repository=query_repo,
        capture_profile_repository=profile_repo,
    )

    result = service.create_capture_extractor_query(
        capture_profile_id=1,
        command={
            "query_code": "QMASK",
            "query_name": "Mask test",
            "extractor_kind": "SQL_QUERY",
            "query_text": "SELECT password_hash FROM users",
            "output_dataset_name": "masked",
            "config_only": True,
        },
        actor={"user_id": 1},
    )

    assert "query_text" not in result
    assert "metadata_json" not in result
    assert result["has_query_text"] is True
