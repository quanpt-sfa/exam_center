"""Service-level tests for MD-5 assessment configuration workflows."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from datetime import timezone

import pytest

from app.modules.master_data.common.errors import MasterDataValidationError
from app.modules.master_data.services.exam_service import ExamService
from app.modules.master_data.services.exam_version_delivery_profile_service import (
    ExamVersionDeliveryProfileService,
)
from app.modules.master_data.services.exam_version_publish_validation_service import (
    ExamVersionPublishValidationService,
)
from app.modules.master_data.services.exam_version_service import ExamVersionService


class InMemoryAuditHook:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def record(self, event) -> None:
        self.events.append(
            {
                "entity": getattr(event, "entity", None),
                "action": getattr(event, "action", None),
                "entity_id": getattr(event, "entity_id", None),
            }
        )


class InMemoryExamRepository:
    def __init__(self) -> None:
        self.exams: dict[int, dict] = {}
        self.next_exam_id = 1
        self.valid_class_section_ids: set[int] = {1, 2}
        self.valid_assessment_types: dict[int, bool] = {1: True, 2: True, 3: False}

    def list_exams(
        self,
        *,
        query_text,
        status,
        class_section_id,
        assessment_type_id,
        offset,
        limit,
        conn=None,
    ):
        _ = conn
        rows = list(self.exams.values())

        if query_text:
            needle = str(query_text).strip().lower()
            rows = [
                row
                for row in rows
                if needle in str(row.get("exam_code", "")).lower()
                or needle in str(row.get("exam_name", "")).lower()
            ]

        if status:
            rows = [row for row in rows if str(row.get("exam_status", "")).upper() == str(status).upper()]

        if class_section_id is not None:
            rows = [row for row in rows if row.get("class_section_id") is not None and int(row.get("class_section_id")) == int(class_section_id)]

        if assessment_type_id is not None:
            rows = [row for row in rows if int(row.get("assessment_type_id")) == int(assessment_type_id)]

        rows.sort(key=lambda item: int(item["exam_id"]), reverse=True)
        total = len(rows)
        return rows[offset : offset + limit], total

    def get_exam_by_id(self, exam_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.exams.get(int(exam_id))
        return dict(row) if row else None

    def get_exam_by_code(self, exam_code: str, conn=None) -> dict | None:
        _ = conn
        code = exam_code.strip().upper()
        for row in self.exams.values():
            if str(row.get("exam_code", "")).upper() == code:
                return dict(row)
        return None

    def class_section_exists(self, class_section_id: int, conn=None) -> bool:
        _ = conn
        return int(class_section_id) in self.valid_class_section_ids

    def assessment_type_exists(self, assessment_type_id: int, *, require_active: bool, conn=None) -> bool:
        _ = conn
        if int(assessment_type_id) not in self.valid_assessment_types:
            return False
        if not require_active:
            return True
        return bool(self.valid_assessment_types[int(assessment_type_id)])

    def create_exam(
        self,
        *,
        class_section_id,
        assessment_type_id,
        exam_code,
        exam_name,
        description,
        exam_status,
        created_by,
        conn=None,
    ) -> dict:
        _ = conn
        exam_id = self.next_exam_id
        self.next_exam_id += 1

        row = {
            "exam_id": exam_id,
            "class_section_id": int(class_section_id) if class_section_id is not None else None,
            "assessment_type_id": int(assessment_type_id),
            "exam_code": str(exam_code).strip().upper(),
            "exam_name": str(exam_name).strip(),
            "description": description,
            "exam_status": str(exam_status).strip().upper(),
            "created_by": int(created_by),
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
            "class_code": f"CLS-{int(class_section_id):03d}" if class_section_id is not None else None,
            "class_name": f"Class {int(class_section_id)}" if class_section_id is not None else None,
            "assessment_type_code": f"TYPE-{int(assessment_type_id)}",
            "assessment_type_name": f"Type {int(assessment_type_id)}",
            "assessment_type_active": self.valid_assessment_types.get(int(assessment_type_id), False),
        }
        self.exams[exam_id] = row
        return dict(row)

    def update_exam(self, *, exam_id: int, payload: dict, conn=None) -> dict | None:
        _ = conn
        row = self.exams.get(int(exam_id))
        if row is None:
            return None

        for key, value in payload.items():
            if key in {"exam_code", "exam_status"} and value is not None:
                value = str(value).strip().upper()
            if key == "exam_name" and value is not None:
                value = str(value).strip()
            row[key] = value

        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)

    def archive_exam(self, *, exam_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.exams.get(int(exam_id))
        if row is None:
            return None

        row["exam_status"] = "ARCHIVED"
        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)


class InMemoryExamVersionRepository:
    def __init__(self) -> None:
        self.versions: dict[int, dict] = {}
        self.next_exam_version_id = 1
        self.question_grading_profile_supported = True
        self.exam_versions_with_grading_profiles: set[int] = set()
        self.version_question_profiles: dict[int, list[dict]] = {}
        self.question_expected_answers: set[int] = set()
        self.paper_asset_table_supported = True
        self.active_paper_assets_by_version: dict[int, bool] = {}
        self.worker_write_calls = 0

    def list_exam_versions(self, *, exam_id, status, offset, limit, conn=None):
        _ = conn
        rows = [row for row in self.versions.values() if int(row.get("exam_id")) == int(exam_id)]
        if status:
            rows = [row for row in rows if str(row.get("status", "")).upper() == str(status).upper()]
        rows.sort(key=lambda item: int(item["version_no"]), reverse=True)
        total = len(rows)
        return rows[offset : offset + limit], total

    def get_exam_version_by_id(self, exam_version_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.versions.get(int(exam_version_id))
        return dict(row) if row else None

    def get_exam_version_by_exam_and_version_no(self, *, exam_id: int, version_no: int, conn=None) -> dict | None:
        _ = conn
        for row in self.versions.values():
            if int(row.get("exam_id")) == int(exam_id) and int(row.get("version_no")) == int(version_no):
                return dict(row)
        return None

    def get_next_version_no(self, exam_id: int, conn=None) -> int:
        _ = conn
        max_no = 0
        for row in self.versions.values():
            if int(row.get("exam_id")) != int(exam_id):
                continue
            max_no = max(max_no, int(row.get("version_no", 0)))
        return max_no + 1

    def create_exam_version(
        self,
        *,
        exam_id,
        version_no,
        version_label,
        duration_seconds,
        total_score,
        shuffle_questions,
        shuffle_options,
        randomization_mode,
        status,
        conn=None,
    ) -> dict:
        _ = conn
        exam_version_id = self.next_exam_version_id
        self.next_exam_version_id += 1

        row = {
            "exam_version_id": exam_version_id,
            "exam_id": int(exam_id),
            "exam_code": f"EX-{int(exam_id):03d}",
            "exam_name": f"Exam {int(exam_id)}",
            "exam_status": "ACTIVE",
            "version_no": int(version_no),
            "version_label": version_label,
            "duration_seconds": int(duration_seconds),
            "total_score": total_score,
            "shuffle_questions": bool(shuffle_questions),
            "shuffle_options": bool(shuffle_options),
            "randomization_mode": str(randomization_mode).strip().upper(),
            "status": str(status).strip().upper(),
            "published_at": None,
            "published_by": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
        }
        self.versions[exam_version_id] = row
        return dict(row)

    def update_exam_version(self, *, exam_version_id: int, payload: dict, conn=None) -> dict | None:
        _ = conn
        row = self.versions.get(int(exam_version_id))
        if row is None:
            return None

        for key, value in payload.items():
            if key in {"randomization_mode", "status"} and value is not None:
                value = str(value).strip().upper()
            if key == "version_label" and value is not None:
                value = str(value).strip()
            row[key] = value

        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)

    def publish_exam_version(self, *, exam_version_id: int, published_by: int, conn=None) -> dict | None:
        _ = conn
        row = self.versions.get(int(exam_version_id))
        if row is None:
            return None

        row["status"] = "PUBLISHED"
        row["published_by"] = int(published_by)
        row["published_at"] = datetime.now(timezone.utc)
        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)

    def retire_exam_version(self, *, exam_version_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.versions.get(int(exam_version_id))
        if row is None:
            return None

        row["status"] = "RETIRED"
        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)

    def has_other_published_version(self, *, exam_id: int, excluded_exam_version_id: int, conn=None) -> bool:
        _ = conn
        for row in self.versions.values():
            if int(row.get("exam_id")) != int(exam_id):
                continue
            if int(row.get("exam_version_id")) == int(excluded_exam_version_id):
                continue
            if str(row.get("status", "")).upper() == "PUBLISHED":
                return True
        return False

    def question_grading_profile_table_exists(self, conn=None) -> bool:
        _ = conn
        return bool(self.question_grading_profile_supported)

    def has_active_question_grading_profile(self, *, exam_version_id: int, conn=None) -> bool:
        _ = conn
        version_id = int(exam_version_id)
        return version_id in self.exam_versions_with_grading_profiles or bool(self.version_question_profiles.get(version_id))

    def list_active_question_grading_profiles(self, *, exam_version_id: int, conn=None) -> list[dict]:
        _ = conn
        return [dict(item) for item in self.version_question_profiles.get(int(exam_version_id), [])]

    def question_has_active_expected_answer(self, *, question_template_id: int, conn=None) -> bool:
        _ = conn
        return int(question_template_id) in self.question_expected_answers

    def paper_asset_table_exists(self, conn=None) -> bool:
        _ = conn
        return bool(self.paper_asset_table_supported)

    def has_active_visual_paper_asset(self, *, exam_version_id: int, conn=None) -> bool:
        _ = conn
        return bool(self.active_paper_assets_by_version.get(int(exam_version_id), False))

    # Sentinel write methods to assert publish-readiness remains read-only.
    def create_generated_exam_instance(self, *args, **kwargs) -> None:  # pragma: no cover - sentinel
        _ = (args, kwargs)
        self.worker_write_calls += 1

    def create_grading_job(self, *args, **kwargs) -> None:  # pragma: no cover - sentinel
        _ = (args, kwargs)
        self.worker_write_calls += 1


class InMemoryDeliveryProfileRepository:
    def __init__(self) -> None:
        self.supported = True
        self.delivery_profiles: dict[int, dict] = {}
        self.capture_profiles: dict[int, bool] = {}
        self.grading_engines: dict[int, bool] = {}
        self.grading_engine_rows_by_code: dict[str, dict] = {}
        self.capture_engine_links: set[tuple[int, int]] = set()
        self.exam_version_statuses: dict[int, str] = {}
        self.started_sitting_counts: dict[int, int] = {}
        self.next_profile_id = 1

    def table_exists(self, conn=None) -> bool:
        _ = conn
        return bool(self.supported)

    def capture_profile_table_exists(self, conn=None) -> bool:
        _ = conn
        return True

    def grading_engine_table_exists(self, conn=None) -> bool:
        _ = conn
        return True

    def capture_profile_engine_link_table_exists(self, conn=None) -> bool:
        _ = conn
        return True

    def get_delivery_profile_by_exam_version_id(self, exam_version_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.delivery_profiles.get(int(exam_version_id))
        return dict(row) if row else None

    def get_exam_version_status(self, exam_version_id: int, conn=None) -> str | None:
        _ = conn
        return self.exam_version_statuses.get(int(exam_version_id))

    def count_started_sittings_for_exam_version(self, exam_version_id: int, conn=None) -> int:
        _ = conn
        return int(self.started_sitting_counts.get(int(exam_version_id), 0))

    def create_delivery_profile(self, **kwargs) -> dict:
        _ = kwargs.pop("conn", None)
        exam_version_id = int(kwargs["exam_version_id"])
        row = {
            "exam_version_delivery_profile_id": self.next_profile_id,
            "exam_version_id": exam_version_id,
            "delivery_mode": kwargs["delivery_mode"],
            "work_mode": kwargs["work_mode"],
            "primary_answer_source": kwargs["primary_answer_source"],
            "requires_capture": kwargs["requires_capture"],
            "capture_timing": kwargs["capture_timing"],
            "default_capture_profile_id": kwargs.get("default_capture_profile_id"),
            "default_grading_engine_id": kwargs.get("default_grading_engine_id"),
            "allow_mixed_question_sources": kwargs["allow_mixed_question_sources"],
            "form_autosave_enabled": kwargs["form_autosave_enabled"],
            "database_work_mode": kwargs["database_work_mode"],
            "status": kwargs["status"],
            "metadata_json": kwargs.get("metadata_json") or {},
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
        }
        self.next_profile_id += 1
        self.delivery_profiles[exam_version_id] = row
        return dict(row)

    def update_delivery_profile_by_exam_version_id(self, *, exam_version_id: int, payload: dict, conn=None) -> dict | None:
        _ = conn
        row = self.delivery_profiles.get(int(exam_version_id))
        if row is None:
            return None
        for key, value in payload.items():
            row[key] = value
        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)

    def capture_profile_is_active(self, capture_profile_id: int, conn=None) -> bool | None:
        _ = conn
        return self.capture_profiles.get(int(capture_profile_id), False)

    def grading_engine_is_active(self, grading_engine_id: int, conn=None) -> bool | None:
        _ = conn
        return self.grading_engines.get(int(grading_engine_id), False)

    def get_active_grading_engine_by_code(self, grading_engine_code: str, conn=None) -> dict | None:
        _ = conn
        row = self.grading_engine_rows_by_code.get(str(grading_engine_code).strip().upper())
        return dict(row) if row else None

    def capture_profile_supports_engine(self, *, capture_profile_id: int, grading_engine_id: int, conn=None) -> bool | None:
        _ = conn
        return (int(capture_profile_id), int(grading_engine_id)) in self.capture_engine_links


class SnapshotTransactionManager:
    def __init__(self, *targets: object) -> None:
        self.targets = targets
        self._depth = 0
        self._snapshots: list[dict] | None = None

    @contextmanager
    def scope(self):
        is_outer = self._depth == 0
        if is_outer:
            self._snapshots = [deepcopy(target.__dict__) for target in self.targets]

        self._depth += 1
        try:
            yield None
        except Exception:
            if is_outer and self._snapshots is not None:
                for target, snapshot in zip(self.targets, self._snapshots):
                    target.__dict__.clear()
                    target.__dict__.update(snapshot)
            raise
        finally:
            self._depth -= 1
            if is_outer:
                self._snapshots = None


def _admin_user() -> dict:
    return {
        "user_id": 1,
        "username": "admin",
        "roles": ["ADMIN"],
        "permissions": ["*", "master_data:write", "master_data:publish", "master_data:read"],
    }


def _build_services():
    exam_repo = InMemoryExamRepository()
    exam_version_repo = InMemoryExamVersionRepository()
    delivery_profile_repo = InMemoryDeliveryProfileRepository()

    audit = InMemoryAuditHook()
    tx = SnapshotTransactionManager(exam_repo, exam_version_repo, delivery_profile_repo, audit)

    delivery_profile_service = ExamVersionDeliveryProfileService(delivery_profile_repository=delivery_profile_repo)
    publish_validation_service = ExamVersionPublishValidationService(
        exam_repository=exam_repo,
        exam_version_repository=exam_version_repo,
        delivery_profile_service=delivery_profile_service,
    )

    exam_service = ExamService(
        exam_repository=exam_repo,
        audit_hook=audit,
        transaction_scope=tx.scope,
    )

    exam_version_service = ExamVersionService(
        exam_repository=exam_repo,
        exam_version_repository=exam_version_repo,
        publish_validation_service=publish_validation_service,
        audit_hook=audit,
        transaction_scope=tx.scope,
    )

    return exam_service, exam_version_service, exam_repo, exam_version_repo, delivery_profile_repo


def _create_active_exam(exam_service: ExamService) -> dict:
    return exam_service.create_exam(
        command={
            "class_section_id": 1,
            "assessment_type_id": 1,
            "exam_code": "EX-101",
            "exam_name": "Exam 101",
            "exam_status": "ACTIVE",
        },
        actor=_admin_user(),
    )


def _seed_publish_ready_form_based_version(
    *,
    exam_service: ExamService,
    exam_version_service: ExamVersionService,
    exam_version_repo: InMemoryExamVersionRepository,
    delivery_profile_repo: InMemoryDeliveryProfileRepository,
    question_type: str = "TEXTAREA",
    grading_engine_code: str = "MANUAL_RUBRIC",
    comparison_method: str = "MANUAL_RUBRIC",
    with_expected_answer: bool = False,
    version_status: str = "DRAFT",
    declared_question_count: int | None = 1,
) -> int:
    exam = _create_active_exam(exam_service)
    version = exam_version_service.create_exam_version(
        exam_id=int(exam["exam_id"]),
        command={
            "duration_seconds": 3600,
            "total_score": 100,
            "randomization_mode": "FIXED",
            "status": version_status,
        },
        actor=_admin_user(),
    )
    exam_version_id = int(version["exam_version_id"])
    exam_version_repo.exam_versions_with_grading_profiles.add(exam_version_id)
    exam_version_repo.version_question_profiles[exam_version_id] = [
        {
            "question_grading_profile_id": 9200,
            "question_template_id": 5200,
            "grading_engine_code": grading_engine_code,
            "comparison_method": comparison_method,
            "max_score": 10,
            "metadata_json": {
                "response_mode": "LONG_TEXT" if question_type == "TEXTAREA" else question_type,
                "render_component": "TEXTAREA" if question_type == "TEXTAREA" else "SQL_EDITOR",
                "authoring_question_type": question_type,
            },
        }
    ]
    if with_expected_answer:
        exam_version_repo.question_expected_answers.add(5200)
    metadata = {"modality_code": "TEXTBOX_SQL"}
    if declared_question_count is not None:
        metadata["question_count"] = declared_question_count
    delivery_profile_repo.delivery_profiles[exam_version_id] = {
        "exam_version_delivery_profile_id": 1,
        "exam_version_id": exam_version_id,
        "delivery_mode": "FORM_BASED",
        "work_mode": "INDIVIDUAL",
        "primary_answer_source": "SEALED_FORM_ANSWER",
        "requires_capture": False,
        "capture_timing": "NONE",
        "default_capture_profile_id": None,
        "default_grading_engine_id": 10,
        "allow_mixed_question_sources": False,
        "form_autosave_enabled": True,
        "database_work_mode": "NONE",
        "status": "ACTIVE",
        "metadata_json": metadata,
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
    }
    delivery_profile_repo.grading_engines[10] = True
    delivery_profile_repo.grading_engine_rows_by_code["MANUAL_RUBRIC"] = {
        "grading_engine_id": 10,
        "engine_code": "MANUAL_RUBRIC",
        "is_active": True,
    }
    return exam_version_id


def test_create_exam() -> None:
    exam_service, _exam_version_service, _exam_repo, _exam_version_repo, _delivery_profile_repo = _build_services()

    result = exam_service.create_exam(
        command={
            "class_section_id": 1,
            "assessment_type_id": 1,
            "exam_code": "EX-101",
            "exam_name": "Exam 101",
            "exam_status": "DRAFT",
        },
        actor=_admin_user(),
    )

    assert result["exam_id"] == 1
    assert result["exam_code"] == "EX-101"


def test_create_exam_invalid_class_section_rejected() -> None:
    exam_service, _exam_version_service, _exam_repo, _exam_version_repo, _delivery_profile_repo = _build_services()

    with pytest.raises(MasterDataValidationError):
        exam_service.create_exam(
            command={
                "class_section_id": 999,
                "assessment_type_id": 1,
                "exam_code": "EX-101",
                "exam_name": "Exam 101",
            },
            actor=_admin_user(),
        )


def test_create_exam_without_class_section() -> None:
    exam_service, _exam_version_service, _exam_repo, _exam_version_repo, _delivery_profile_repo = _build_services()

    # Omitted case
    result = exam_service.create_exam(
        command={
            "assessment_type_id": 1,
            "exam_code": "EX-101",
            "exam_name": "Exam 101",
            "exam_status": "DRAFT",
        },
        actor=_admin_user(),
    )
    assert result["exam_id"] == 1
    assert result["class_section_id"] is None

    # Explicit None case
    result2 = exam_service.create_exam(
        command={
            "class_section_id": None,
            "assessment_type_id": 1,
            "exam_code": "EX-102",
            "exam_name": "Exam 102",
            "exam_status": "DRAFT",
        },
        actor=_admin_user(),
    )
    assert result2["exam_id"] == 2
    assert result2["class_section_id"] is None


def test_update_exam_class_section() -> None:
    exam_service, _exam_version_service, _exam_repo, _exam_version_repo, _delivery_profile_repo = _build_services()

    # Create initial exam with class section 1
    exam = exam_service.create_exam(
        command={
            "class_section_id": 1,
            "assessment_type_id": 1,
            "exam_code": "EX-101",
            "exam_name": "Exam 101",
            "exam_status": "DRAFT",
        },
        actor=_admin_user(),
    )
    assert exam["class_section_id"] == 1

    # Update to None (explicitly unsetting class section)
    updated = exam_service.update_exam(
        exam_id=int(exam["exam_id"]),
        command={
            "class_section_id": None,
        },
        actor=_admin_user(),
    )
    assert updated["class_section_id"] is None

    # Update to 2 (valid class section)
    updated2 = exam_service.update_exam(
        exam_id=int(exam["exam_id"]),
        command={
            "class_section_id": 2,
        },
        actor=_admin_user(),
    )
    assert updated2["class_section_id"] == 2

    # Update to 999 (invalid class section - rejected)
    with pytest.raises(MasterDataValidationError):
        exam_service.update_exam(
            exam_id=int(exam["exam_id"]),
            command={
                "class_section_id": 999,
            },
            actor=_admin_user(),
        )



def test_create_exam_version() -> None:
    exam_service, exam_version_service, _exam_repo, _exam_version_repo, _delivery_profile_repo = _build_services()
    exam = _create_active_exam(exam_service)

    version = exam_version_service.create_exam_version(
        exam_id=int(exam["exam_id"]),
        command={
            "duration_seconds": 3600,
            "total_score": 100,
            "randomization_mode": "FIXED",
            "status": "DRAFT",
        },
        actor=_admin_user(),
    )

    assert version["exam_version_id"] == 1
    assert version["version_no"] == 1


def test_invalid_duration_rejected() -> None:
    exam_service, exam_version_service, _exam_repo, _exam_version_repo, _delivery_profile_repo = _build_services()
    exam = _create_active_exam(exam_service)

    with pytest.raises(MasterDataValidationError):
        exam_version_service.create_exam_version(
            exam_id=int(exam["exam_id"]),
            command={
                "duration_seconds": 0,
                "total_score": 100,
                "randomization_mode": "FIXED",
                "status": "DRAFT",
            },
            actor=_admin_user(),
        )


def test_invalid_status_transition_rejected() -> None:
    exam_service, _exam_version_service, _exam_repo, _exam_version_repo, _delivery_profile_repo = _build_services()

    exam = exam_service.create_exam(
        command={
            "class_section_id": 1,
            "assessment_type_id": 1,
            "exam_code": "EX-101",
            "exam_name": "Exam 101",
            "exam_status": "DRAFT",
        },
        actor=_admin_user(),
    )

    with pytest.raises(MasterDataValidationError):
        exam_service.update_exam(
            exam_id=int(exam["exam_id"]),
            command={"exam_status": "ACTIVE"},
            actor=_admin_user(),
        )


def test_validate_exam_version_returns_missing_items() -> None:
    exam_service, exam_version_service, _exam_repo, _exam_version_repo, _delivery_profile_repo = _build_services()
    exam = _create_active_exam(exam_service)

    version = exam_version_service.create_exam_version(
        exam_id=int(exam["exam_id"]),
        command={
            "duration_seconds": 3600,
            "total_score": 100,
            "randomization_mode": "FIXED",
            "status": "DRAFT",
        },
        actor=_admin_user(),
    )

    validation = exam_version_service.validate_exam_version_for_publish(
        exam_version_id=int(version["exam_version_id"]),
        actor=_admin_user(),
    )

    missing_codes = {item["code"] for item in validation["missing_items"]}
    assert validation["is_valid"] is False
    assert "delivery_profile_missing" in missing_codes


def test_validate_exam_version_fails_when_question_missing_response_profile_metadata() -> None:
    exam_service, exam_version_service, _exam_repo, exam_version_repo, delivery_profile_repo = _build_services()
    exam = _create_active_exam(exam_service)
    version = exam_version_service.create_exam_version(
        exam_id=int(exam["exam_id"]),
        command={
            "duration_seconds": 3600,
            "total_score": 100,
            "randomization_mode": "FIXED",
            "status": "DRAFT",
        },
        actor=_admin_user(),
    )
    exam_version_id = int(version["exam_version_id"])
    exam_version_repo.exam_versions_with_grading_profiles.add(exam_version_id)
    exam_version_repo.version_question_profiles[exam_version_id] = [
        {
            "question_grading_profile_id": 9001,
            "question_template_id": 5001,
            "grading_engine_code": "MANUAL_RUBRIC",
            "comparison_method": "MANUAL_RUBRIC",
            "metadata_json": {},
        }
    ]
    delivery_profile_repo.delivery_profiles[exam_version_id] = {
        "exam_version_delivery_profile_id": 1,
        "exam_version_id": exam_version_id,
        "delivery_mode": "FORM_BASED",
        "work_mode": "INDIVIDUAL",
        "primary_answer_source": "SEALED_FORM_ANSWER",
        "requires_capture": False,
        "capture_timing": "NONE",
        "default_capture_profile_id": None,
        "default_grading_engine_id": 10,
        "allow_mixed_question_sources": False,
        "form_autosave_enabled": True,
        "database_work_mode": "NONE",
        "status": "ACTIVE",
        "metadata_json": {"modality_code": "TEXTBOX_SQL"},
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
    }
    delivery_profile_repo.grading_engines[10] = True

    validation = exam_version_service.validate_exam_version_for_publish(
        exam_version_id=exam_version_id,
        actor=_admin_user(),
    )
    missing_codes = {item["code"] for item in validation["missing_items"]}
    assert "question_response_profile_missing" in missing_codes


def test_validate_exam_version_fails_when_auto_graded_question_has_no_expected_answer() -> None:
    exam_service, exam_version_service, _exam_repo, exam_version_repo, delivery_profile_repo = _build_services()
    exam = _create_active_exam(exam_service)
    version = exam_version_service.create_exam_version(
        exam_id=int(exam["exam_id"]),
        command={
            "duration_seconds": 3600,
            "total_score": 100,
            "randomization_mode": "FIXED",
            "status": "DRAFT",
        },
        actor=_admin_user(),
    )
    exam_version_id = int(version["exam_version_id"])
    exam_version_repo.exam_versions_with_grading_profiles.add(exam_version_id)
    exam_version_repo.version_question_profiles[exam_version_id] = [
        {
            "question_grading_profile_id": 9002,
            "question_template_id": 5002,
            "grading_engine_code": "SQL_RESULT_COMPARATOR",
            "comparison_method": "RESULT_SET_MATCH",
            "metadata_json": {
                "response_mode": "SQL_TEXT",
                "render_component": "SQL_EDITOR",
                "authoring_question_type": "TEXTBOX_SQL",
            },
        }
    ]
    delivery_profile_repo.delivery_profiles[exam_version_id] = {
        "exam_version_delivery_profile_id": 1,
        "exam_version_id": exam_version_id,
        "delivery_mode": "FORM_BASED",
        "work_mode": "INDIVIDUAL",
        "primary_answer_source": "SEALED_FORM_ANSWER",
        "requires_capture": False,
        "capture_timing": "NONE",
        "default_capture_profile_id": None,
        "default_grading_engine_id": 10,
        "allow_mixed_question_sources": False,
        "form_autosave_enabled": True,
        "database_work_mode": "NONE",
        "status": "ACTIVE",
        "metadata_json": {"modality_code": "TEXTBOX_SQL"},
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
    }
    delivery_profile_repo.grading_engines[10] = True

    validation = exam_version_service.validate_exam_version_for_publish(
        exam_version_id=exam_version_id,
        actor=_admin_user(),
    )
    missing_codes = {item["code"] for item in validation["missing_items"]}
    assert "question_expected_answer_missing" in missing_codes

    exam_version_repo.question_expected_answers.add(5002)
    validation_with_expected = exam_version_service.validate_exam_version_for_publish(
        exam_version_id=exam_version_id,
        actor=_admin_user(),
    )
    missing_codes_with_expected = {item["code"] for item in validation_with_expected["missing_items"]}
    assert "question_expected_answer_missing" not in missing_codes_with_expected


def test_publish_valid_version() -> None:
    exam_service, exam_version_service, _exam_repo, exam_version_repo, delivery_profile_repo = _build_services()
    exam_version_id = _seed_publish_ready_form_based_version(
        exam_service=exam_service,
        exam_version_service=exam_version_service,
        exam_version_repo=exam_version_repo,
        delivery_profile_repo=delivery_profile_repo,
        question_type="TEXTAREA",
        grading_engine_code="MANUAL_RUBRIC",
        comparison_method="MANUAL_RUBRIC",
        with_expected_answer=False,
    )

    published = exam_version_service.publish_exam_version(
        exam_version_id=exam_version_id,
        actor=_admin_user(),
    )

    assert published["exam_version"]["status"] == "PUBLISHED"
    assert published["validation"]["is_valid"] is True


def test_publish_invalid_version_rejected() -> None:
    exam_service, exam_version_service, _exam_repo, _exam_version_repo, _delivery_profile_repo = _build_services()
    exam = _create_active_exam(exam_service)

    version = exam_version_service.create_exam_version(
        exam_id=int(exam["exam_id"]),
        command={
            "duration_seconds": 3600,
            "total_score": 100,
            "randomization_mode": "FIXED",
            "status": "DRAFT",
        },
        actor=_admin_user(),
    )

    with pytest.raises(MasterDataValidationError):
        exam_version_service.publish_exam_version(
            exam_version_id=int(version["exam_version_id"]),
            actor=_admin_user(),
        )


def test_modifying_published_version_rejected() -> None:
    exam_service, exam_version_service, _exam_repo, exam_version_repo, delivery_profile_repo = _build_services()
    exam = _create_active_exam(exam_service)

    version = exam_version_service.create_exam_version(
        exam_id=int(exam["exam_id"]),
        command={
            "duration_seconds": 3600,
            "total_score": 100,
            "randomization_mode": "FIXED",
            "status": "DRAFT",
        },
        actor=_admin_user(),
    )

    exam_version_id = int(version["exam_version_id"])
    exam_version_repo.exam_versions_with_grading_profiles.add(exam_version_id)
    exam_version_repo.version_question_profiles[exam_version_id] = [
        {
            "question_grading_profile_id": 9101,
            "question_template_id": 5101,
            "grading_engine_code": "MANUAL_RUBRIC",
            "comparison_method": "MANUAL_RUBRIC",
            "max_score": 10,
            "metadata_json": {
                "response_mode": "LONG_TEXT",
                "render_component": "TEXTAREA",
                "authoring_question_type": "TEXTAREA",
            },
        }
    ]
    delivery_profile_repo.delivery_profiles[exam_version_id] = {
        "exam_version_delivery_profile_id": 1,
        "exam_version_id": exam_version_id,
        "delivery_mode": "FORM_BASED",
        "work_mode": "INDIVIDUAL",
        "primary_answer_source": "SEALED_FORM_ANSWER",
        "requires_capture": False,
        "capture_timing": "NONE",
        "default_capture_profile_id": None,
        "default_grading_engine_id": 10,
        "allow_mixed_question_sources": False,
        "form_autosave_enabled": True,
        "database_work_mode": "NONE",
        "status": "ACTIVE",
        "metadata_json": {"modality_code": "TEXTBOX_CODE"},
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
    }
    delivery_profile_repo.grading_engines[10] = True

    exam_version_service.publish_exam_version(exam_version_id=exam_version_id, actor=_admin_user())

    with pytest.raises(MasterDataValidationError):
        exam_version_service.update_exam_version(
            exam_version_id=exam_version_id,
            command={"duration_seconds": 1800},
            actor=_admin_user(),
        )


def test_validate_exam_version_fails_when_question_missing_grading_profile_metadata() -> None:
    exam_service, exam_version_service, _exam_repo, exam_version_repo, delivery_profile_repo = _build_services()
    exam_version_id = _seed_publish_ready_form_based_version(
        exam_service=exam_service,
        exam_version_service=exam_version_service,
        exam_version_repo=exam_version_repo,
        delivery_profile_repo=delivery_profile_repo,
    )
    exam_version_repo.version_question_profiles[exam_version_id][0]["grading_engine_code"] = None
    exam_version_repo.version_question_profiles[exam_version_id][0]["comparison_method"] = None

    validation = exam_version_service.validate_exam_version_for_publish(
        exam_version_id=exam_version_id,
        actor=_admin_user(),
    )
    missing_codes = {item["code"] for item in validation["missing_items"]}
    assert "question_grading_profile_missing" in missing_codes


def test_validate_exam_version_fails_when_auto_graded_question_has_invalid_max_score() -> None:
    exam_service, exam_version_service, _exam_repo, exam_version_repo, delivery_profile_repo = _build_services()
    exam_version_id = _seed_publish_ready_form_based_version(
        exam_service=exam_service,
        exam_version_service=exam_version_service,
        exam_version_repo=exam_version_repo,
        delivery_profile_repo=delivery_profile_repo,
        question_type="TEXTBOX_SQL",
        grading_engine_code="SQL_RESULT_COMPARATOR",
        comparison_method="RESULT_SET_MATCH",
        with_expected_answer=True,
    )
    exam_version_repo.version_question_profiles[exam_version_id][0]["max_score"] = 0
    validation = exam_version_service.validate_exam_version_for_publish(
        exam_version_id=exam_version_id,
        actor=_admin_user(),
    )
    missing_codes = {item["code"] for item in validation["missing_items"]}
    assert "question_max_score_invalid" in missing_codes


def test_validate_exam_version_fails_when_question_count_mismatch_for_non_draft() -> None:
    exam_service, exam_version_service, _exam_repo, exam_version_repo, delivery_profile_repo = _build_services()
    exam_version_id = _seed_publish_ready_form_based_version(
        exam_service=exam_service,
        exam_version_service=exam_version_service,
        exam_version_repo=exam_version_repo,
        delivery_profile_repo=delivery_profile_repo,
        version_status="UNDER_REVIEW",
        declared_question_count=2,
    )

    validation = exam_version_service.validate_exam_version_for_publish(
        exam_version_id=exam_version_id,
        actor=_admin_user(),
    )
    missing_codes = {item["code"] for item in validation["missing_items"]}
    assert "question_count_mismatch" in missing_codes


def test_validate_exam_version_allows_question_count_mismatch_for_draft() -> None:
    exam_service, exam_version_service, _exam_repo, exam_version_repo, delivery_profile_repo = _build_services()
    exam_version_id = _seed_publish_ready_form_based_version(
        exam_service=exam_service,
        exam_version_service=exam_version_service,
        exam_version_repo=exam_version_repo,
        delivery_profile_repo=delivery_profile_repo,
        version_status="DRAFT",
        declared_question_count=2,
    )

    validation = exam_version_service.validate_exam_version_for_publish(
        exam_version_id=exam_version_id,
        actor=_admin_user(),
    )
    missing_codes = {item["code"] for item in validation["missing_items"]}
    assert "question_count_mismatch" not in missing_codes


def test_validate_exam_version_does_not_require_paper_asset_for_question_based_form_mode() -> None:
    exam_service, exam_version_service, _exam_repo, exam_version_repo, delivery_profile_repo = _build_services()
    exam_version_id = _seed_publish_ready_form_based_version(
        exam_service=exam_service,
        exam_version_service=exam_version_service,
        exam_version_repo=exam_version_repo,
        delivery_profile_repo=delivery_profile_repo,
        question_type="TEXTAREA",
        grading_engine_code="MANUAL_RUBRIC",
        comparison_method="MANUAL_RUBRIC",
        with_expected_answer=False,
    )
    validation = exam_version_service.validate_exam_version_for_publish(
        exam_version_id=exam_version_id,
        actor=_admin_user(),
    )
    missing_codes = {item["code"] for item in validation["missing_items"]}
    assert "paper_asset_missing" not in missing_codes
    assert validation["is_valid"] is True


def test_validate_exam_version_requires_paper_asset_for_visual_paper_mode() -> None:
    exam_service, exam_version_service, _exam_repo, exam_version_repo, delivery_profile_repo = _build_services()
    exam = _create_active_exam(exam_service)
    version = exam_version_service.create_exam_version(
        exam_id=int(exam["exam_id"]),
        command={
            "duration_seconds": 3600,
            "total_score": 100,
            "randomization_mode": "FIXED",
            "status": "UNDER_REVIEW",
        },
        actor=_admin_user(),
    )
    exam_version_id = int(version["exam_version_id"])
    exam_version_repo.exam_versions_with_grading_profiles.add(exam_version_id)
    exam_version_repo.version_question_profiles[exam_version_id] = [
        {
            "question_grading_profile_id": 9901,
            "question_template_id": 5901,
            "grading_engine_code": "MANUAL_RUBRIC",
            "comparison_method": "MANUAL_RUBRIC",
            "max_score": 10,
            "metadata_json": {
                "response_mode": "FILE_UPLOAD",
                "render_component": "FILE_UPLOAD_BOX",
                "authoring_question_type": "FILE_UPLOAD",
            },
        }
    ]
    delivery_profile_repo.delivery_profiles[exam_version_id] = {
        "exam_version_delivery_profile_id": 1,
        "exam_version_id": exam_version_id,
        "delivery_mode": "FILE_BASED",
        "work_mode": "INDIVIDUAL",
        "primary_answer_source": "FILE_ARTIFACT",
        "requires_capture": False,
        "capture_timing": "NONE",
        "default_capture_profile_id": None,
        "default_grading_engine_id": 10,
        "allow_mixed_question_sources": False,
        "form_autosave_enabled": False,
        "database_work_mode": "NONE",
        "status": "ACTIVE",
        "metadata_json": {
            "delivery_content_type": "VISUAL_PAPER_BASED",
            "conceptual_delivery_type": "VISUAL_PAPER_BASED",
            "allow_form_answers": False,
            "visual_paper_required": True,
            "paper_asset_required": True,
            "requires_visual_paper": True,
        },
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
    }
    delivery_profile_repo.grading_engines[10] = True
    delivery_profile_repo.grading_engine_rows_by_code["MANUAL_RUBRIC"] = {
        "grading_engine_id": 10,
        "engine_code": "MANUAL_RUBRIC",
        "is_active": True,
    }

    validation = exam_version_service.validate_exam_version_for_publish(
        exam_version_id=exam_version_id,
        actor=_admin_user(),
    )
    missing_codes = {item["code"] for item in validation["missing_items"]}
    assert "paper_asset_missing" in missing_codes
    assert "exam_modality_missing" not in missing_codes

    exam_version_repo.active_paper_assets_by_version[exam_version_id] = True
    validation_with_paper = exam_version_service.validate_exam_version_for_publish(
        exam_version_id=exam_version_id,
        actor=_admin_user(),
    )
    missing_with_paper = {item["code"] for item in validation_with_paper["missing_items"]}
    assert "paper_asset_missing" not in missing_with_paper


def test_validate_exam_version_does_not_require_paper_asset_for_file_submission_type() -> None:
    exam_service, exam_version_service, _exam_repo, exam_version_repo, delivery_profile_repo = _build_services()
    exam_version_id = _seed_publish_ready_form_based_version(
        exam_service=exam_service,
        exam_version_service=exam_version_service,
        exam_version_repo=exam_version_repo,
        delivery_profile_repo=delivery_profile_repo,
        question_type="FILE_UPLOAD",
        grading_engine_code="MANUAL_RUBRIC",
        comparison_method="MANUAL_RUBRIC",
        with_expected_answer=False,
    )
    delivery_profile_repo.delivery_profiles[exam_version_id].update(
        {
            "delivery_mode": "FILE_BASED",
            "primary_answer_source": "FILE_ARTIFACT",
            "form_autosave_enabled": False,
            "metadata_json": {
                "delivery_content_type": "FILE_SUBMISSION_BASED",
                "conceptual_delivery_type": "FILE_SUBMISSION_BASED",
                "allow_form_answers": False,
                "visual_paper_required": False,
                "paper_asset_required": False,
                "requires_visual_paper": False,
                "modality_code": "TEXTBOX_SQL",
            },
        }
    )

    validation = exam_version_service.validate_exam_version_for_publish(
        exam_version_id=exam_version_id,
        actor=_admin_user(),
    )
    missing_codes = {item["code"] for item in validation["missing_items"]}
    assert "paper_asset_missing" not in missing_codes


def test_visual_paper_profile_resolves_exam_modality_from_delivery_content_type() -> None:
    service = ExamVersionDeliveryProfileService(delivery_profile_repository=InMemoryDeliveryProfileRepository())

    resolved = service.resolve_exam_modality(
        {
            "delivery_mode": "FILE_BASED",
            "primary_answer_source": "FILE_ARTIFACT",
            "metadata_json": {
                "delivery_content_type": "VISUAL_PAPER_BASED",
                "conceptual_delivery_type": "VISUAL_PAPER_BASED",
            },
        }
    )

    assert resolved == "VISUAL_PAPER_BASED"


def test_visual_paper_profile_with_active_paper_and_manual_rubric_engine_does_not_report_grading_engine_missing() -> None:
    exam_service, exam_version_service, _exam_repo, exam_version_repo, delivery_profile_repo = _build_services()
    exam = _create_active_exam(exam_service)
    version = exam_version_service.create_exam_version(
        exam_id=int(exam["exam_id"]),
        command={
            "duration_seconds": 3600,
            "total_score": 100,
            "randomization_mode": "FIXED",
            "status": "UNDER_REVIEW",
        },
        actor=_admin_user(),
    )
    exam_version_id = int(version["exam_version_id"])
    exam_version_repo.active_paper_assets_by_version[exam_version_id] = True
    delivery_profile_repo.delivery_profiles[exam_version_id] = {
        "exam_version_delivery_profile_id": 1,
        "exam_version_id": exam_version_id,
        "delivery_mode": "FILE_BASED",
        "work_mode": "INDIVIDUAL",
        "primary_answer_source": "FILE_ARTIFACT",
        "requires_capture": False,
        "capture_timing": "NONE",
        "default_capture_profile_id": None,
        "default_grading_engine_id": 10,
        "allow_mixed_question_sources": False,
        "form_autosave_enabled": False,
        "database_work_mode": "NONE",
        "status": "ACTIVE",
        "metadata_json": {
            "delivery_content_type": "VISUAL_PAPER_BASED",
            "conceptual_delivery_type": "VISUAL_PAPER_BASED",
            "visual_paper_required": True,
            "paper_asset_required": True,
            "requires_visual_paper": True,
        },
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
    }
    delivery_profile_repo.grading_engines[10] = True
    delivery_profile_repo.grading_engine_rows_by_code["MANUAL_RUBRIC"] = {
        "grading_engine_id": 10,
        "engine_code": "MANUAL_RUBRIC",
        "is_active": True,
    }

    validation = exam_version_service.validate_exam_version_for_publish(
        exam_version_id=exam_version_id,
        actor=_admin_user(),
    )

    missing_codes = {item["code"] for item in validation["missing_items"]}
    assert "grading_engine_missing" not in missing_codes
    assert validation["exam_modality"] == "VISUAL_PAPER_BASED"


def test_validate_exam_version_passes_for_complete_textbox_sql_with_expected_answer() -> None:
    exam_service, exam_version_service, _exam_repo, exam_version_repo, delivery_profile_repo = _build_services()
    exam_version_id = _seed_publish_ready_form_based_version(
        exam_service=exam_service,
        exam_version_service=exam_version_service,
        exam_version_repo=exam_version_repo,
        delivery_profile_repo=delivery_profile_repo,
        question_type="TEXTBOX_SQL",
        grading_engine_code="SQL_RESULT_COMPARATOR",
        comparison_method="RESULT_SET_MATCH",
        with_expected_answer=True,
    )
    validation = exam_version_service.validate_exam_version_for_publish(
        exam_version_id=exam_version_id,
        actor=_admin_user(),
    )
    assert validation["is_valid"] is True


def test_validate_exam_version_passes_for_complete_mcq_single_with_expected_answer() -> None:
    exam_service, exam_version_service, _exam_repo, exam_version_repo, delivery_profile_repo = _build_services()
    exam_version_id = _seed_publish_ready_form_based_version(
        exam_service=exam_service,
        exam_version_service=exam_version_service,
        exam_version_repo=exam_version_repo,
        delivery_profile_repo=delivery_profile_repo,
        question_type="MCQ_SINGLE",
        grading_engine_code="MCQ_AUTO_GRADER",
        comparison_method="EXACT_MATCH",
        with_expected_answer=True,
    )
    exam_version_repo.version_question_profiles[exam_version_id][0]["metadata_json"]["render_component"] = "RADIO_GROUP"
    validation = exam_version_service.validate_exam_version_for_publish(
        exam_version_id=exam_version_id,
        actor=_admin_user(),
    )
    assert validation["is_valid"] is True


def test_publish_readiness_is_read_only_and_does_not_invoke_worker_only_operations() -> None:
    exam_service, exam_version_service, _exam_repo, exam_version_repo, delivery_profile_repo = _build_services()
    exam_version_id = _seed_publish_ready_form_based_version(
        exam_service=exam_service,
        exam_version_service=exam_version_service,
        exam_version_repo=exam_version_repo,
        delivery_profile_repo=delivery_profile_repo,
    )
    _ = exam_version_service.validate_exam_version_for_publish(
        exam_version_id=exam_version_id,
        actor=_admin_user(),
    )
    assert exam_version_repo.worker_write_calls == 0


def test_upsert_delivery_profile_create_and_update() -> None:
    exam_service, _exam_version_service, _exam_repo, exam_version_repo, delivery_profile_repo = _build_services()
    exam = _create_active_exam(exam_service)
    version = exam_version_repo.create_exam_version(
        exam_id=int(exam["exam_id"]),
        version_no=1,
        version_label="Version 1",
        duration_seconds=3600,
        total_score=100,
        shuffle_questions=False,
        shuffle_options=False,
        randomization_mode="FIXED",
        status="DRAFT",
    )
    exam_version_id = int(version["exam_version_id"])
    delivery_profile_repo.exam_version_statuses[exam_version_id] = "DRAFT"

    service = ExamVersionDeliveryProfileService(delivery_profile_repository=delivery_profile_repo)

    created = service.upsert_delivery_profile_for_exam_version(
        exam_version_id=exam_version_id,
        command={
            "delivery_mode": "FILE_BASED",
            "work_mode": "INDIVIDUAL",
            "primary_answer_source": "FILE_ARTIFACT",
            "requires_capture": False,
            "capture_timing": "NONE",
            "default_capture_profile_id": None,
            "default_grading_engine_id": None,
            "allow_mixed_question_sources": False,
            "form_autosave_enabled": False,
            "database_work_mode": "NONE",
            "status": "ACTIVE",
            "metadata_json": {"allow_form_answers": False},
        },
        actor=_admin_user(),
    )
    assert created["delivery_mode"] == "FILE_BASED"
    assert created["primary_answer_source"] == "FILE_ARTIFACT"

    updated = service.upsert_delivery_profile_for_exam_version(
        exam_version_id=exam_version_id,
        command={
            "delivery_mode": "FILE_BASED",
            "work_mode": "INDIVIDUAL",
            "primary_answer_source": "FILE_ARTIFACT",
            "requires_capture": False,
            "capture_timing": "NONE",
            "default_capture_profile_id": None,
            "default_grading_engine_id": None,
            "allow_mixed_question_sources": True,
            "form_autosave_enabled": False,
            "database_work_mode": "NONE",
            "status": "ACTIVE",
            "metadata_json": {"allow_form_answers": False},
        },
        actor=_admin_user(),
    )
    assert updated["allow_mixed_question_sources"] is True


def test_upsert_delivery_profile_auto_assigns_manual_rubric_for_visual_paper_and_file_submission() -> None:
    delivery_profile_repo = InMemoryDeliveryProfileRepository()
    delivery_profile_repo.exam_version_statuses[100] = "DRAFT"
    delivery_profile_repo.grading_engine_rows_by_code["MANUAL_RUBRIC"] = {
        "grading_engine_id": 777,
        "engine_code": "MANUAL_RUBRIC",
        "is_active": True,
    }
    delivery_profile_repo.grading_engines[777] = True
    service = ExamVersionDeliveryProfileService(delivery_profile_repository=delivery_profile_repo)

    created_visual = service.upsert_delivery_profile_for_exam_version(
        exam_version_id=100,
        command={
            "delivery_mode": "FILE_BASED",
            "work_mode": "INDIVIDUAL",
            "primary_answer_source": "FILE_ARTIFACT",
            "requires_capture": False,
            "capture_timing": "NONE",
            "default_capture_profile_id": None,
            "default_grading_engine_id": None,
            "allow_mixed_question_sources": False,
            "form_autosave_enabled": False,
            "database_work_mode": "NONE",
            "status": "ACTIVE",
            "metadata_json": {
                "delivery_content_type": "VISUAL_PAPER_BASED",
                "conceptual_delivery_type": "VISUAL_PAPER_BASED",
                "visual_paper_required": True,
            },
        },
        actor=_admin_user(),
    )
    assert created_visual["default_grading_engine_id"] == 777
    assert created_visual["exam_modality"] == "VISUAL_PAPER_BASED"

    updated_file_submission = service.upsert_delivery_profile_for_exam_version(
        exam_version_id=100,
        command={
            "delivery_mode": "FILE_BASED",
            "work_mode": "INDIVIDUAL",
            "primary_answer_source": "FILE_ARTIFACT",
            "requires_capture": False,
            "capture_timing": "NONE",
            "default_capture_profile_id": None,
            "default_grading_engine_id": None,
            "allow_mixed_question_sources": False,
            "form_autosave_enabled": False,
            "database_work_mode": "NONE",
            "status": "ACTIVE",
            "metadata_json": {
                "delivery_content_type": "FILE_SUBMISSION_BASED",
                "conceptual_delivery_type": "FILE_SUBMISSION_BASED",
                "visual_paper_required": False,
                "paper_asset_required": False,
                "requires_visual_paper": False,
            },
        },
        actor=_admin_user(),
    )
    assert updated_file_submission["default_grading_engine_id"] == 777
    assert updated_file_submission["exam_modality"] == "FILE_SUBMISSION_BASED"


def test_upsert_delivery_profile_rejects_manual_file_profile_when_manual_rubric_engine_missing() -> None:
    delivery_profile_repo = InMemoryDeliveryProfileRepository()
    delivery_profile_repo.exam_version_statuses[100] = "DRAFT"
    service = ExamVersionDeliveryProfileService(delivery_profile_repository=delivery_profile_repo)

    with pytest.raises(MasterDataValidationError) as exc_info:
        service.upsert_delivery_profile_for_exam_version(
            exam_version_id=100,
            command={
                "delivery_mode": "FILE_BASED",
                "work_mode": "INDIVIDUAL",
                "primary_answer_source": "FILE_ARTIFACT",
                "requires_capture": False,
                "capture_timing": "NONE",
                "default_capture_profile_id": None,
                "default_grading_engine_id": None,
                "allow_mixed_question_sources": False,
                "form_autosave_enabled": False,
                "database_work_mode": "NONE",
                "status": "ACTIVE",
                "metadata_json": {
                    "delivery_content_type": "VISUAL_PAPER_BASED",
                    "conceptual_delivery_type": "VISUAL_PAPER_BASED",
                    "visual_paper_required": True,
                },
            },
            actor=_admin_user(),
        )

    assert exc_info.value.message == "manual_grading_engine_missing"


def test_upsert_delivery_profile_rejects_invalid_enum() -> None:
    delivery_profile_repo = InMemoryDeliveryProfileRepository()
    delivery_profile_repo.exam_version_statuses[100] = "DRAFT"
    service = ExamVersionDeliveryProfileService(delivery_profile_repository=delivery_profile_repo)

    with pytest.raises(MasterDataValidationError):
        service.upsert_delivery_profile_for_exam_version(
            exam_version_id=100,
            command={
                "delivery_mode": "INVALID_MODE",
                "work_mode": "INDIVIDUAL",
                "primary_answer_source": "FILE_ARTIFACT",
                "requires_capture": False,
                "capture_timing": "NONE",
                "default_capture_profile_id": None,
                "default_grading_engine_id": None,
                "allow_mixed_question_sources": False,
                "form_autosave_enabled": False,
                "database_work_mode": "NONE",
                "status": "ACTIVE",
            },
            actor=_admin_user(),
        )


def test_upsert_delivery_profile_rejects_non_editable_version() -> None:
    delivery_profile_repo = InMemoryDeliveryProfileRepository()
    delivery_profile_repo.exam_version_statuses[100] = "PUBLISHED"
    service = ExamVersionDeliveryProfileService(delivery_profile_repository=delivery_profile_repo)

    with pytest.raises(MasterDataValidationError):
        service.upsert_delivery_profile_for_exam_version(
            exam_version_id=100,
            command={
                "delivery_mode": "FILE_BASED",
                "work_mode": "INDIVIDUAL",
                "primary_answer_source": "FILE_ARTIFACT",
                "requires_capture": False,
                "capture_timing": "NONE",
                "default_capture_profile_id": None,
                "default_grading_engine_id": None,
                "allow_mixed_question_sources": False,
                "form_autosave_enabled": False,
                "database_work_mode": "NONE",
                "status": "ACTIVE",
            },
            actor=_admin_user(),
        )
