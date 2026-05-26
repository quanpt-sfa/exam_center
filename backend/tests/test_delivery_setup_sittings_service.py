"""Unit tests for delivery setup sitting workflows."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.errors import ApiError
from app.modules.delivery.repositories.delivery_repository import DeliveryRepository
from app.modules.delivery.services.delivery_service import DeliveryService


class _InMemorySetupRepository:
    def __init__(self) -> None:
        self.exam_versions: dict[int, dict] = {
            101: {
                "exam_version_id": 101,
                "exam_id": 11,
                "version_no": 1,
                "version_label": "Version 1",
                "exam_version_status": "PUBLISHED",
                "shuffle_questions": False,
                "shuffle_options": False,
                "randomization_mode": "FIXED",
                "exam_code": "ACC101",
                "exam_name": "Kế toán 101",
            },
            102: {
                "exam_version_id": 102,
                "exam_id": 11,
                "version_no": 2,
                "version_label": "Version 2",
                "exam_version_status": "DRAFT",
                "shuffle_questions": False,
                "shuffle_options": False,
                "randomization_mode": "FIXED",
                "exam_code": "ACC101",
                "exam_name": "Kế toán 101",
            },
            103: {
                "exam_version_id": 103,
                "exam_id": 12,
                "version_no": 1,
                "version_label": "Lab Version",
                "exam_version_status": "PUBLISHED",
                "shuffle_questions": False,
                "shuffle_options": False,
                "randomization_mode": "FIXED",
                "exam_code": "LAB101",
                "exam_name": "Lab 101",
            },
            104: {
                "exam_version_id": 104,
                "exam_id": 13,
                "version_no": 1,
                "version_label": "Visual Paper Version",
                "exam_version_status": "PUBLISHED",
                "shuffle_questions": False,
                "shuffle_options": False,
                "randomization_mode": "FIXED",
                "exam_code": "ACC101",
                "exam_name": "Kế toán 101",
            },
        }
        self.next_id = 1
        self.sittings: dict[int, dict] = {}
        self.students: dict[str, dict] = {
            "SV001": {"student_id": 501, "student_code": "SV001"},
            "SV002": {"student_id": 502, "student_code": "SV002"},
        }
        self.assignments: list[dict] = []
        self.sitting_rooms: dict[int, list[dict]] = {}
        self.station_assignments: dict[int, list[dict]] = {}
        self.proctor_assignments: dict[int, list[dict]] = {}
        self.delivery_profiles: dict[int, dict] = {
            101: {
                "delivery_mode": "FORM_BASED",
                "primary_answer_source": "SEALED_FORM_ANSWER",
                "requires_capture": False,
                "database_work_mode": "NONE",
                "delivery_profile_status": "ACTIVE",
                "delivery_profile_metadata_json": {},
            },
            102: {
                "delivery_mode": "FORM_BASED",
                "primary_answer_source": "SEALED_FORM_ANSWER",
                "requires_capture": False,
                "database_work_mode": "NONE",
                "delivery_profile_status": "ACTIVE",
                "delivery_profile_metadata_json": {},
            },
            103: {
                "delivery_mode": "DATABASE_BASED",
                "primary_answer_source": "STUDENT_DATABASE",
                "requires_capture": True,
                "database_work_mode": "STUDENT_DEVICE_LOCAL",
                "delivery_profile_status": "ACTIVE",
                "delivery_profile_metadata_json": {},
            },
            104: {
                "delivery_mode": "FILE_BASED",
                "primary_answer_source": "FILE_ARTIFACT",
                "requires_capture": False,
                "database_work_mode": "NONE",
                "delivery_profile_status": "ACTIVE",
                "delivery_profile_metadata_json": {
                    "delivery_content_type": "VISUAL_PAPER_BASED",
                    "visual_paper_required": True,
                },
            },
        }
        self.question_profiles_by_version: dict[int, list[dict]] = {
            101: [
                {
                    "question_grading_profile_id": 8001,
                    "question_template_id": 7001,
                    "input_source": "SEALED_TEXT_ANSWER",
                    "requires_capture": False,
                    "required_capture_type": None,
                    "capture_profile_id": None,
                    "grading_engine_id": 91,
                    "comparison_method": "MANUAL_RUBRIC",
                    "status": "ACTIVE",
                    "metadata_json": {"question_no": 1},
                    "question_template_status": "ACTIVE",
                    "capture_profile_status": None,
                    "grading_engine_status": "ACTIVE",
                    "grading_engine_code": "MANUAL_RUBRIC",
                }
            ],
            103: [
                {
                    "question_grading_profile_id": 8002,
                    "question_template_id": 7002,
                    "input_source": "STUDENT_DATABASE_CAPTURE",
                    "requires_capture": True,
                    "required_capture_type": "POSTGRES_DATABASE_SNAPSHOT",
                    "capture_profile_id": 12,
                    "grading_engine_id": 92,
                    "comparison_method": "CUSTOM",
                    "status": "ACTIVE",
                    "metadata_json": {"question_no": 1},
                    "question_template_status": "ACTIVE",
                    "capture_profile_status": "ACTIVE",
                    "grading_engine_status": "ACTIVE",
                    "grading_engine_code": "SQL_RESULT_COMPARATOR",
                }
            ],
            104: [
                {
                    "question_grading_profile_id": 8003,
                    "question_template_id": 7003,
                    "input_source": "MANUAL",
                    "requires_capture": False,
                    "required_capture_type": None,
                    "capture_profile_id": None,
                    "grading_engine_id": 91,
                    "comparison_method": "MANUAL_RUBRIC",
                    "status": "ACTIVE",
                    "metadata_json": {"question_no": 1},
                    "question_template_status": "ACTIVE",
                    "capture_profile_status": None,
                    "grading_engine_status": "ACTIVE",
                    "grading_engine_code": "MANUAL_RUBRIC",
                }
            ],
        }
        self.paper_assets_by_version: dict[int, list[dict]] = {
            104: [
                {
                    "paper_asset_id": 9001,
                    "exam_version_id": 104,
                    "asset_kind": "PDF_SOURCE",
                    "render_status": "UPLOADED",
                    "is_active": True,
                }
            ]
        }
        self.active_session_counts: dict[int, int] = {}
        self.session_or_submission_counts: dict[int, dict] = {}
        self.session_ids_by_assignment: dict[int, int] = {}
        self.instance_ids_by_assignment: dict[int, int] = {}
        self.generated_questions_by_instance: dict[int, int] = {}
        self.next_session_id = 100
        self.next_instance_id = 200

    def list_setup_sittings(self) -> list[dict]:
        return list(self.sittings.values())

    def get_exam_version_detail(self, exam_version_id: int) -> dict | None:
        row = self.exam_versions.get(int(exam_version_id))
        return dict(row) if row else None

    def create_setup_sitting(self, **kwargs) -> dict:
        exam_sitting_id = self.next_id
        self.next_id += 1
        version = self.exam_versions[int(kwargs["exam_version_id"])]
        row = {
            "exam_sitting_id": exam_sitting_id,
            "exam_version_id": int(kwargs["exam_version_id"]),
            "sitting_code": str(kwargs["sitting_code"]).strip(),
            "sitting_name": str(kwargs["sitting_name"]).strip(),
            "scheduled_start_at": kwargs["scheduled_start_at"],
            "scheduled_end_at": kwargs["scheduled_end_at"],
            "timezone": None,
            "sitting_status": str(kwargs["sitting_status"]).strip().upper(),
            "created_by": int(kwargs["created_by"]),
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
            "exam_id": int(version["exam_id"]),
            "exam_code": version["exam_code"],
            "exam_name": version["exam_name"],
            "version_no": int(version["version_no"]),
            "version_label": version["version_label"],
            "exam_version_status": version["exam_version_status"],
        }
        self.sittings[exam_sitting_id] = row
        return dict(row)

    def get_setup_sitting_by_id(self, exam_sitting_id: int) -> dict | None:
        row = self.sittings.get(int(exam_sitting_id))
        return dict(row) if row else None

    def get_exam_sitting_by_id(self, exam_sitting_id: int) -> dict | None:
        return self.get_setup_sitting_by_id(exam_sitting_id)

    def get_exam_sitting_readiness_context(self, exam_sitting_id: int) -> dict | None:
        row = self.sittings.get(int(exam_sitting_id))
        if row is None:
            return None
        version = self.exam_versions.get(int(row["exam_version_id"]))
        profile = self.delivery_profiles.get(int(row["exam_version_id"]), {})
        return {
            **dict(row),
            "exam_version_status": version.get("exam_version_status") if version else None,
            "shuffle_questions": bool(version.get("shuffle_questions")) if version else False,
            "shuffle_options": bool(version.get("shuffle_options")) if version else False,
            "randomization_mode": version.get("randomization_mode") if version else None,
            **profile,
        }

    def list_exam_sitting_readiness_assignments(self, exam_sitting_id: int) -> list[dict]:
        return [
            dict(row)
            for row in self.assignments
            if int(row["exam_sitting_id"]) == int(exam_sitting_id)
            and str(row["assignment_status"]).upper() in {"ASSIGNED", "CHECKED_IN"}
        ]

    def list_sitting_rooms(self, exam_sitting_id: int) -> list[dict]:
        return [dict(row) for row in self.sitting_rooms.get(int(exam_sitting_id), [])]

    def list_exam_sitting_readiness_station_assignments(self, exam_sitting_id: int) -> list[dict]:
        return [dict(row) for row in self.station_assignments.get(int(exam_sitting_id), [])]

    def list_exam_sitting_readiness_proctors(self, exam_sitting_id: int) -> list[dict]:
        return [dict(row) for row in self.proctor_assignments.get(int(exam_sitting_id), [])]

    def list_exam_version_readiness_question_profiles(self, exam_version_id: int) -> list[dict]:
        return [dict(row) for row in self.question_profiles_by_version.get(int(exam_version_id), [])]

    def list_exam_version_active_paper_assets(self, exam_version_id: int) -> list[dict]:
        return [dict(row) for row in self.paper_assets_by_version.get(int(exam_version_id), [])]

    def count_active_sessions_for_sitting(self, exam_sitting_id: int) -> int:
        return int(self.active_session_counts.get(int(exam_sitting_id), 0))

    def update_setup_sitting(self, *, exam_sitting_id: int, payload: dict) -> dict | None:
        row = self.sittings.get(int(exam_sitting_id))
        if row is None:
            return None
        for key, value in payload.items():
            row[key] = value
        if "exam_version_id" in payload:
            version = self.exam_versions[int(payload["exam_version_id"])]
            row["exam_id"] = int(version["exam_id"])
            row["exam_code"] = version["exam_code"]
            row["exam_name"] = version["exam_name"]
            row["version_no"] = int(version["version_no"])
            row["version_label"] = version["version_label"]
            row["exam_version_status"] = version["exam_version_status"]
        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)

    def update_exam_sitting(self, *, exam_sitting_id: int, payload: dict) -> dict | None:
        return self.update_setup_sitting(exam_sitting_id=exam_sitting_id, payload=payload)

    def count_sessions_or_submissions_for_sitting(self, exam_sitting_id: int) -> dict:
        return dict(self.session_or_submission_counts.get(int(exam_sitting_id), {"session_count": 0, "submission_count": 0}))

    def get_exam_sitting_by_code(self, sitting_code: str) -> dict | None:
        for row in self.sittings.values():
            if str(row["sitting_code"]).lower() == str(sitting_code).strip().lower():
                return dict(row)
        return None

    def get_student_by_code(self, student_code: str) -> dict | None:
        row = self.students.get(str(student_code).strip().upper())
        return dict(row) if row else None

    def student_exists(self, student_id: int) -> bool:
        return any(int(row["student_id"]) == int(student_id) for row in self.students.values())

    def create_exam_assignment(self, *, exam_sitting_id: int, student_id: int, assignment_status: str, assigned_by: int | None, note: str | None) -> dict:
        for row in self.assignments:
            if int(row["exam_sitting_id"]) == int(exam_sitting_id) and int(row["student_id"]) == int(student_id):
                from psycopg.errors import UniqueViolation

                raise UniqueViolation("duplicate")
        row = {
            "exam_assignment_id": len(self.assignments) + 1,
            "exam_sitting_id": int(exam_sitting_id),
            "student_id": int(student_id),
            "assignment_status": str(assignment_status).strip().upper(),
            "assigned_by": assigned_by,
            "note": note,
        }
        self.assignments.append(row)
        return dict(row)

    def get_exam_assignment_by_sitting_student(self, *, exam_sitting_id: int, student_id: int) -> dict | None:
        for row in self.assignments:
            if int(row["exam_sitting_id"]) == int(exam_sitting_id) and int(row["student_id"]) == int(student_id):
                return dict(row)
        return None

    def update_exam_assignment(self, *, exam_assignment_id: int, payload: dict) -> dict | None:
        for row in self.assignments:
            if int(row["exam_assignment_id"]) == int(exam_assignment_id):
                row.update(payload)
                if row.get("assignment_status") is not None:
                    row["assignment_status"] = str(row["assignment_status"]).strip().upper()
                return dict(row)
        return None

    def prepare_exam_sitting_runtime(self, *, exam_sitting_id: int, actor_user_id: int | None) -> dict:
        assignments = self.list_exam_sitting_readiness_assignments(int(exam_sitting_id))
        question_profiles = self.list_exam_version_readiness_question_profiles(
            int(self.sittings[int(exam_sitting_id)]["exam_version_id"])
        )
        created_session_count = 0
        reused_session_count = 0
        created_instance_count = 0
        reused_instance_count = 0
        created_generated_question_count = 0

        for assignment in assignments:
            assignment_id = int(assignment["exam_assignment_id"])
            session_id = self.session_ids_by_assignment.get(assignment_id)
            if session_id is None:
                self.next_session_id += 1
                session_id = self.next_session_id
                self.session_ids_by_assignment[assignment_id] = session_id
                created_session_count += 1
            else:
                reused_session_count += 1

            instance_id = self.instance_ids_by_assignment.get(assignment_id)
            if instance_id is None:
                self.next_instance_id += 1
                instance_id = self.next_instance_id
                self.instance_ids_by_assignment[assignment_id] = instance_id
                created_instance_count += 1
            else:
                reused_instance_count += 1

            if self.generated_questions_by_instance.get(instance_id, 0) == 0:
                self.generated_questions_by_instance[instance_id] = len(question_profiles)
                created_generated_question_count += len(question_profiles)

        result = {
            "prepared": bool(assignments and question_profiles),
            "exam_sitting_id": int(exam_sitting_id),
            "exam_version_id": int(self.sittings[int(exam_sitting_id)]["exam_version_id"]),
            "assignment_count": len(assignments),
            "question_count": len(question_profiles),
            "created_session_count": created_session_count,
            "reused_session_count": reused_session_count,
            "created_instance_count": created_instance_count,
            "reused_instance_count": reused_instance_count,
            "created_generated_question_count": created_generated_question_count,
            "actor_user_id": actor_user_id,
        }
        return dict(result)


def test_delivery_repository_exposes_readiness_methods() -> None:
    repo = DeliveryRepository()

    assert callable(getattr(repo, "get_exam_sitting_readiness_context", None))
    assert callable(getattr(repo, "list_exam_sitting_readiness_assignments", None))
    assert callable(getattr(repo, "list_exam_sitting_readiness_station_assignments", None))
    assert callable(getattr(repo, "list_exam_sitting_readiness_proctors", None))
    assert callable(getattr(repo, "list_exam_version_readiness_question_profiles", None))
    assert callable(getattr(repo, "list_exam_version_active_paper_assets", None))
    assert callable(getattr(repo, "get_active_session_by_exam_assignment", None))


def test_delivery_repository_create_setup_sitting_accepts_full_signature() -> None:
    """Regression: repo method must accept all kwargs that the service passes.

    This does NOT call the DB — it verifies the method's declared parameters
    match what DeliveryService.create_setup_sitting sends, so a signature
    mismatch is caught before a live environment is needed.
    """
    import inspect

    repo = DeliveryRepository()
    sig = inspect.signature(repo.create_setup_sitting)
    params = set(sig.parameters.keys())

    required = {
        "sitting_code",
        "sitting_name",
        "exam_version_id",
        "scheduled_start_at",
        "scheduled_end_at",
        "sitting_status",
        "created_by",
    }
    missing = required - params
    assert not missing, f"create_setup_sitting is missing params: {missing}"

    # All required params must be keyword-only (the method uses * separator).
    for name in required:
        p = sig.parameters[name]
        assert p.kind == inspect.Parameter.KEYWORD_ONLY, (
            f"Parameter '{name}' should be keyword-only"
        )


def _admin_user() -> dict:
    return {"user_id": 1, "roles": ["ADMIN"]}


def test_create_sitting_with_one_exam_version_id() -> None:
    repository = _InMemorySetupRepository()
    service = DeliveryService(repository=repository)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=2)

    result = service.create_setup_sitting(
        sitting_code="ACC101-2026-MID-AM",
        sitting_name="Ca sáng ACC101",
        exam_version_id=101,
        scheduled_start_at=start,
        scheduled_end_at=end,
        status="DRAFT",
        current_user=_admin_user(),
    )

    assert result["exam_sitting_id"] == 1
    assert result["exam_version_id"] == 101
    assert result["exam_version_label"] == "Version 1"


def test_create_sitting_rejects_invalid_time_range() -> None:
    repository = _InMemorySetupRepository()
    service = DeliveryService(repository=repository)
    start = datetime.now(timezone.utc) + timedelta(days=1)

    with pytest.raises(ApiError) as exc_info:
        service.create_setup_sitting(
            sitting_code="ACC101-2026-MID-AM",
            sitting_name="Ca sáng ACC101",
            exam_version_id=101,
            scheduled_start_at=start,
            scheduled_end_at=start,
            status="DRAFT",
            current_user=_admin_user(),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "validation_error"


def test_create_sitting_rejects_non_existing_exam_version_id() -> None:
    repository = _InMemorySetupRepository()
    service = DeliveryService(repository=repository)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=2)

    with pytest.raises(ApiError) as exc_info:
        service.create_setup_sitting(
            sitting_code="ACC101-2026-MID-AM",
            sitting_name="Ca sáng ACC101",
            exam_version_id=9999,
            scheduled_start_at=start,
            scheduled_end_at=end,
            status="DRAFT",
            current_user=_admin_user(),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "exam_version_not_found"


def test_list_sittings_includes_exam_version_label_and_exam_name() -> None:
    repository = _InMemorySetupRepository()
    service = DeliveryService(repository=repository)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=2)
    service.create_setup_sitting(
        sitting_code="ACC101-2026-MID-AM",
        sitting_name="Ca sáng ACC101",
        exam_version_id=101,
        scheduled_start_at=start,
        scheduled_end_at=end,
        status="DRAFT",
        current_user=_admin_user(),
    )

    listed = service.list_setup_sittings(current_user=_admin_user())
    assert len(listed["items"]) == 1
    assert listed["items"][0]["exam_version_label"] == "Version 1"
    assert listed["items"][0]["exam_name"] == "Kế toán 101"


def test_assign_exam_version_to_sitting_updates_draft_sitting() -> None:
    repository = _InMemorySetupRepository()
    service = DeliveryService(repository=repository)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    created = service.create_setup_sitting(
        sitting_code="ACC101-2026-MID-AM",
        sitting_name="Ca sáng ACC101",
        exam_version_id=101,
        scheduled_start_at=start,
        scheduled_end_at=start + timedelta(hours=2),
        status="DRAFT",
        current_user=_admin_user(),
    )

    result = service.assign_exam_version_to_sitting(
        exam_sitting_id=int(created["exam_sitting_id"]),
        exam_version_id=102,
        current_user=_admin_user(),
    )

    assert result["exam_version_id"] == 102
    assert result["exam_version_label"] == "Version 2"


def test_assign_exam_version_to_sitting_rejects_invalid_sitting() -> None:
    service = DeliveryService(repository=_InMemorySetupRepository())

    with pytest.raises(ApiError) as exc_info:
        service.assign_exam_version_to_sitting(exam_sitting_id=999, exam_version_id=101, current_user=_admin_user())

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "exam_sitting_not_found"


def test_assign_exam_version_to_sitting_rejects_invalid_exam_version() -> None:
    repository = _InMemorySetupRepository()
    service = DeliveryService(repository=repository)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    created = service.create_setup_sitting(
        sitting_code="ACC101-2026-MID-AM",
        sitting_name="Ca sáng ACC101",
        exam_version_id=101,
        scheduled_start_at=start,
        scheduled_end_at=start + timedelta(hours=2),
        status="DRAFT",
        current_user=_admin_user(),
    )

    with pytest.raises(ApiError) as exc_info:
        service.assign_exam_version_to_sitting(
            exam_sitting_id=int(created["exam_sitting_id"]),
            exam_version_id=999,
            current_user=_admin_user(),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "exam_version_not_found"


def test_assign_exam_version_to_sitting_rejects_locked_sitting() -> None:
    repository = _InMemorySetupRepository()
    service = DeliveryService(repository=repository)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    created = service.create_setup_sitting(
        sitting_code="ACC101-2026-MID-AM",
        sitting_name="Ca sáng ACC101",
        exam_version_id=101,
        scheduled_start_at=start,
        scheduled_end_at=start + timedelta(hours=2),
        status="READY",
        current_user=_admin_user(),
    )

    with pytest.raises(ApiError) as exc_info:
        service.assign_exam_version_to_sitting(
            exam_sitting_id=int(created["exam_sitting_id"]),
            exam_version_id=102,
            current_user=_admin_user(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "exam_sitting_locked"


def test_assign_exam_version_to_sitting_rejects_existing_sessions_or_submissions() -> None:
    repository = _InMemorySetupRepository()
    service = DeliveryService(repository=repository)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    created = service.create_setup_sitting(
        sitting_code="ACC101-2026-MID-AM",
        sitting_name="Ca sáng ACC101",
        exam_version_id=101,
        scheduled_start_at=start,
        scheduled_end_at=start + timedelta(hours=2),
        status="DRAFT",
        current_user=_admin_user(),
    )
    repository.session_or_submission_counts[int(created["exam_sitting_id"])] = {
        "session_count": 1,
        "submission_count": 0,
    }

    with pytest.raises(ApiError) as exc_info:
        service.assign_exam_version_to_sitting(
            exam_sitting_id=int(created["exam_sitting_id"]),
            exam_version_id=102,
            current_user=_admin_user(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "exam_sitting_locked"


def test_import_exam_assignments_by_student_code_and_sitting_code() -> None:
    repository = _InMemorySetupRepository()
    service = DeliveryService(repository=repository)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    service.create_setup_sitting(
        sitting_code="SQL-CA-01",
        sitting_name="Ca SQL 01",
        exam_version_id=101,
        scheduled_start_at=start,
        scheduled_end_at=start + timedelta(hours=2),
        status="DRAFT",
        current_user=_admin_user(),
    )

    result = service.import_exam_assignments_by_code(
        items=[
            {"sitting_code": "SQL-CA-01", "student_code": "SV001"},
            {"sitting_code": "SQL-CA-01", "student_code": "SV999"},
        ],
        assignment_status="ASSIGNED",
        current_user=_admin_user(),
    )

    assert result["created_count"] == 1
    assert result["created"][0]["student_id"] == 501
    assert result["error_count"] == 1
    assert result["errors"][0]["code"] == "student_not_found"


def test_create_exam_assignment_reactivates_cancelled_student_assignment() -> None:
    repository = _InMemorySetupRepository()
    service = DeliveryService(repository=repository)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    sitting = service.create_setup_sitting(
        sitting_code="SQL-CA-01",
        sitting_name="Ca SQL 01",
        exam_version_id=101,
        scheduled_start_at=start,
        scheduled_end_at=start + timedelta(hours=2),
        status="DRAFT",
        current_user=_admin_user(),
    )
    cancelled = repository.create_exam_assignment(
        exam_sitting_id=int(sitting["exam_sitting_id"]),
        student_id=501,
        assignment_status="CANCELLED",
        assigned_by=1,
        note="hủy nhầm",
    )

    result = service.create_exam_assignment(
        exam_sitting_id=int(sitting["exam_sitting_id"]),
        command={"student_id": 501, "assignment_status": "ASSIGNED", "note": "đưa vào lại"},
        current_user=_admin_user(),
    )

    assert result["exam_assignment_id"] == cancelled["exam_assignment_id"]
    assert result["assignment_status"] == "ASSIGNED"
    assert result["note"] == "đưa vào lại"


def test_import_exam_assignments_reactivates_cancelled_student_assignment() -> None:
    repository = _InMemorySetupRepository()
    service = DeliveryService(repository=repository)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    sitting = service.create_setup_sitting(
        sitting_code="SQL-CA-01",
        sitting_name="Ca SQL 01",
        exam_version_id=101,
        scheduled_start_at=start,
        scheduled_end_at=start + timedelta(hours=2),
        status="DRAFT",
        current_user=_admin_user(),
    )
    cancelled = repository.create_exam_assignment(
        exam_sitting_id=int(sitting["exam_sitting_id"]),
        student_id=501,
        assignment_status="CANCELLED",
        assigned_by=1,
        note=None,
    )

    result = service.import_exam_assignments_by_code(
        items=[{"sitting_code": "SQL-CA-01", "student_code": "SV001"}],
        assignment_status="ASSIGNED",
        current_user=_admin_user(),
    )

    assert result["created_count"] == 1
    assert result["error_count"] == 0
    assert result["created"][0]["exam_assignment_id"] == cancelled["exam_assignment_id"]
    assert result["created"][0]["assignment_status"] == "ASSIGNED"


def test_prepare_exam_sitting_runtime_creates_student_sessions_after_ready() -> None:
    repository = _InMemorySetupRepository()
    service = DeliveryService(repository=repository)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    created = service.create_setup_sitting(
        sitting_code="SQL-CA-01",
        sitting_name="Ca SQL 01",
        exam_version_id=101,
        scheduled_start_at=start,
        scheduled_end_at=start + timedelta(hours=2),
        status="READY",
        current_user=_admin_user(),
    )
    repository.create_exam_assignment(
        exam_sitting_id=int(created["exam_sitting_id"]),
        student_id=501,
        assignment_status="ASSIGNED",
        assigned_by=1,
        note=None,
    )

    result = service.prepare_exam_sitting_runtime(
        exam_sitting_id=int(created["exam_sitting_id"]),
        current_user=_admin_user(),
    )

    assert result["prepared"] is True
    assert result["assignment_count"] == 1
    assert result["created_session_count"] == 1


def test_readiness_returns_blocker_when_exam_version_not_published() -> None:
    repository = _InMemorySetupRepository()
    service = DeliveryService(repository=repository)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    sitting = service.create_setup_sitting(
        sitting_code="ACC101-DRAFT-VERSION",
        sitting_name="Draft version sitting",
        exam_version_id=102,
        scheduled_start_at=start,
        scheduled_end_at=start + timedelta(hours=2),
        status="READY",
        current_user=_admin_user(),
    )

    readiness = service.get_exam_sitting_readiness(
        exam_sitting_id=int(sitting["exam_sitting_id"]),
        current_user=_admin_user(),
    )

    assert readiness["ready"] is False
    assert "exam_version_not_published" in {item["code"] for item in readiness["blockers"]}


def test_readiness_returns_blocker_when_no_assignments() -> None:
    repository = _InMemorySetupRepository()
    service = DeliveryService(repository=repository)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    sitting = service.create_setup_sitting(
        sitting_code="ACC101-NO-ASG",
        sitting_name="No assignment sitting",
        exam_version_id=101,
        scheduled_start_at=start,
        scheduled_end_at=start + timedelta(hours=2),
        status="READY",
        current_user=_admin_user(),
    )

    readiness = service.get_exam_sitting_readiness(
        exam_sitting_id=int(sitting["exam_sitting_id"]),
        current_user=_admin_user(),
    )

    assert readiness["ready"] is False
    assert "assignment_missing" in {item["code"] for item in readiness["blockers"]}


def test_readiness_returns_blocker_when_station_assignment_missing_for_station_based_delivery() -> None:
    repository = _InMemorySetupRepository()
    service = DeliveryService(repository=repository)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    sitting = service.create_setup_sitting(
        sitting_code="LAB101-STATION",
        sitting_name="Lab station sitting",
        exam_version_id=103,
        scheduled_start_at=start,
        scheduled_end_at=start + timedelta(hours=2),
        status="READY",
        current_user=_admin_user(),
    )
    repository.create_exam_assignment(
        exam_sitting_id=int(sitting["exam_sitting_id"]),
        student_id=501,
        assignment_status="ASSIGNED",
        assigned_by=1,
        note=None,
    )
    repository.sitting_rooms[int(sitting["exam_sitting_id"])] = [
        {
            "exam_sitting_room_id": 3001,
            "exam_sitting_id": int(sitting["exam_sitting_id"]),
            "room_id": 21,
            "room_status": "READY",
        }
    ]
    repository.proctor_assignments[int(sitting["exam_sitting_id"])] = [
        {
            "proctor_assignment_id": 4001,
            "exam_sitting_room_id": 3001,
            "proctor_user_id": 77,
            "status": "ASSIGNED",
        }
    ]

    readiness = service.get_exam_sitting_readiness(
        exam_sitting_id=int(sitting["exam_sitting_id"]),
        current_user=_admin_user(),
    )

    assert readiness["ready"] is False
    assert "station_assignment_missing" in {item["code"] for item in readiness["blockers"]}


def test_readiness_returns_blocker_when_visual_paper_requires_page_image() -> None:
    repository = _InMemorySetupRepository()
    service = DeliveryService(repository=repository)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    sitting = service.create_setup_sitting(
        sitting_code="VISUAL-PDF-ONLY",
        sitting_name="Visual paper missing page image",
        exam_version_id=104,
        scheduled_start_at=start,
        scheduled_end_at=start + timedelta(hours=2),
        status="READY",
        current_user=_admin_user(),
    )
    repository.create_exam_assignment(
        exam_sitting_id=int(sitting["exam_sitting_id"]),
        student_id=501,
        assignment_status="ASSIGNED",
        assigned_by=1,
        note=None,
    )

    readiness = service.get_exam_sitting_readiness(
        exam_sitting_id=int(sitting["exam_sitting_id"]),
        current_user=_admin_user(),
    )

    assert readiness["ready"] is False
    assert "page_image_asset_missing" in {item["code"] for item in readiness["blockers"]}


def test_readiness_clears_page_image_blocker_when_image_page_set_present() -> None:
    """Regression: IMAGE_PAGE_SET must satisfy the page-image requirement.

    Previously the check filtered for asset_kind == 'PAGE_IMAGE', which the DB
    CHECK constraint forbids entirely.  IMAGE_PAGE and IMAGE_PAGE_SET are the
    correct student-viewable kinds.
    """
    repository = _InMemorySetupRepository()
    # Replace the PDF-only asset with an IMAGE_PAGE_SET
    repository.paper_assets_by_version[104] = [
        {
            "paper_asset_id": 9001,
            "exam_version_id": 104,
            "asset_kind": "IMAGE_PAGE_SET",
            "render_status": "RENDERED",
            "is_active": True,
        }
    ]
    service = DeliveryService(repository=repository)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    sitting = service.create_setup_sitting(
        sitting_code="VISUAL-IMAGE-OK",
        sitting_name="Visual paper with image page set",
        exam_version_id=104,
        scheduled_start_at=start,
        scheduled_end_at=start + timedelta(hours=2),
        status="READY",
        current_user=_admin_user(),
    )
    repository.create_exam_assignment(
        exam_sitting_id=int(sitting["exam_sitting_id"]),
        student_id=501,
        assignment_status="ASSIGNED",
        assigned_by=1,
        note=None,
    )

    readiness = service.get_exam_sitting_readiness(
        exam_sitting_id=int(sitting["exam_sitting_id"]),
        current_user=_admin_user(),
    )

    blocker_codes = {item["code"] for item in readiness["blockers"]}
    assert "page_image_asset_missing" not in blocker_codes


def test_prepare_rejects_incomplete_setup_with_structured_blockers() -> None:
    repository = _InMemorySetupRepository()
    service = DeliveryService(repository=repository)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    created = service.create_setup_sitting(
        sitting_code="SQL-INCOMPLETE",
        sitting_name="Incomplete ready sitting",
        exam_version_id=101,
        scheduled_start_at=start,
        scheduled_end_at=start + timedelta(hours=2),
        status="READY",
        current_user=_admin_user(),
    )

    with pytest.raises(ApiError) as exc_info:
        service.prepare_exam_sitting_runtime(
            exam_sitting_id=int(created["exam_sitting_id"]),
            current_user=_admin_user(),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "exam_sitting_not_deliverable"
    assert "assignment_missing" in {item["code"] for item in exc_info.value.details["blockers"]}


def test_prepare_is_idempotent_when_setup_is_complete() -> None:
    repository = _InMemorySetupRepository()
    service = DeliveryService(repository=repository)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    created = service.create_setup_sitting(
        sitting_code="SQL-IDEMPOTENT",
        sitting_name="Idempotent sitting",
        exam_version_id=101,
        scheduled_start_at=start,
        scheduled_end_at=start + timedelta(hours=2),
        status="READY",
        current_user=_admin_user(),
    )
    repository.create_exam_assignment(
        exam_sitting_id=int(created["exam_sitting_id"]),
        student_id=501,
        assignment_status="ASSIGNED",
        assigned_by=1,
        note=None,
    )

    first = service.prepare_exam_sitting_runtime(
        exam_sitting_id=int(created["exam_sitting_id"]),
        current_user=_admin_user(),
    )
    second = service.prepare_exam_sitting_runtime(
        exam_sitting_id=int(created["exam_sitting_id"]),
        current_user=_admin_user(),
    )

    assert first["prepared"] is True
    assert first["created_session_count"] == 1
    assert first["created_instance_count"] == 1
    assert first["created_generated_question_count"] == 1
    assert second["prepared"] is True
    assert second["created_session_count"] == 0
    assert second["reused_session_count"] == 1
    assert second["created_instance_count"] == 0
    assert second["reused_instance_count"] == 1
    assert second["created_generated_question_count"] == 0


def test_prepare_exam_sitting_runtime_rejects_draft_sitting() -> None:
    repository = _InMemorySetupRepository()
    service = DeliveryService(repository=repository)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    created = service.create_setup_sitting(
        sitting_code="SQL-CA-01",
        sitting_name="Ca SQL 01",
        exam_version_id=101,
        scheduled_start_at=start,
        scheduled_end_at=start + timedelta(hours=2),
        status="DRAFT",
        current_user=_admin_user(),
    )

    with pytest.raises(ApiError) as exc_info:
        service.prepare_exam_sitting_runtime(
            exam_sitting_id=int(created["exam_sitting_id"]),
            current_user=_admin_user(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "exam_sitting_not_ready"

