"""Service-level tests for MD-7 master-data import foundation."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from datetime import timezone

import pytest

from app.modules.master_data.common.errors import MasterDataValidationError
from app.modules.master_data.services.import_preview_service import ImportPreviewService
from app.modules.master_data.services.import_template_service import ImportTemplateService
from app.modules.master_data.services.import_validation_service import ImportValidationService
from app.modules.master_data.services.master_data_import_service import MasterDataImportService


class InMemoryImportFoundationRepository:
    TEMPLATE_MAP = {
        "STUDENTS": ("STUDENT_V1", "Student Import Template V1", "STUDENT"),
        "INSTRUCTORS": ("INSTRUCTOR_V1", "Instructor Import Template V1", "INSTRUCTOR"),
        "COURSES": ("COURSE_V1", "Course Import Template V1", "COURSE"),
        "CLASS_SECTIONS": ("CLASS_SECTION_V1", "Class Section Import Template V1", "CLASS_SECTION"),
        "ENROLLMENTS": ("ENROLLMENT_V1", "Enrollment Import Template V1", "ENROLLMENT"),
        "ROOMS": ("ROOM_V1", "Room Import Template V1", "ROOM"),
        "STATIONS": ("STATION_V1", "Station Import Template V1", "STATION"),
        "DEVICES": ("DEVICE_V1", "Device Import Template V1", "DEVICE"),
    }

    def __init__(self) -> None:
        self.templates: dict[str, dict] = {}
        self.jobs: dict[int, dict] = {}
        self.rows: dict[int, dict] = {}
        self.row_errors: dict[int, dict] = {}
        self.audit_events: list[dict] = []
        self.commits: list[dict] = []
        self.next_template_id = 1
        self.next_job_id = 1
        self.next_row_id = 1
        self.next_row_error_id = 1

    def ensure_template_for_import_type(self, *, import_type: str, conn=None) -> dict:
        _ = conn
        code, name, entity = self.TEMPLATE_MAP[import_type]
        template = self.templates.get(code)
        if template is None:
            template = {
                "import_template_id": self.next_template_id,
                "template_code": code,
                "template_name": name,
                "schema_version": "V1",
                "entity_code": entity,
                "is_active": True,
            }
            self.templates[code] = template
            self.next_template_id += 1
        return dict(template)

    def create_job(self, *, import_template_id: int, template_code: str, actor_user_id: int | None, actor_agent: str | None, conn=None) -> dict:
        _ = conn
        job = {
            "import_job_id": self.next_job_id,
            "import_template_id": int(import_template_id),
            "template_code": template_code,
            "job_status": "CREATED",
            "validation_status": "PENDING",
            "commit_status": "NOT_COMMITTED",
            "actor_user_id": actor_user_id,
            "actor_agent": actor_agent,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        self.jobs[self.next_job_id] = job
        self.next_job_id += 1
        return dict(job)

    def get_job_by_id(self, import_job_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.jobs.get(int(import_job_id))
        return dict(row) if row else None

    def update_job_state(self, *, import_job_id: int, job_status: str | None = None, validation_status: str | None = None, commit_status: str | None = None, conn=None) -> None:
        _ = conn
        job = self.jobs[int(import_job_id)]
        if job_status is not None:
            job["job_status"] = job_status
        if validation_status is not None:
            job["validation_status"] = validation_status
        if commit_status is not None:
            job["commit_status"] = commit_status
        job["updated_at"] = datetime.now(timezone.utc)

    def insert_staging_row(self, *, import_job_id: int, row_number: int, raw_row_json: dict, conn=None) -> dict:
        _ = conn
        row = {
            "import_row_staging_id": self.next_row_id,
            "import_job_id": int(import_job_id),
            "row_number": int(row_number),
            "raw_row_json": dict(raw_row_json),
            "normalized_row_json": None,
            "validation_status": "PENDING",
            "commit_status": "NOT_COMMITTED",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        self.rows[self.next_row_id] = row
        self.next_row_id += 1
        return dict(row)

    def list_staging_rows(self, *, import_job_id: int, offset: int, limit: int, conn=None) -> tuple[list[dict], int]:
        _ = conn
        rows = [row for row in self.rows.values() if int(row["import_job_id"]) == int(import_job_id)]
        rows.sort(key=lambda item: int(item["row_number"]))
        total = len(rows)
        sliced = rows[offset : offset + limit]
        return [dict(item) for item in sliced], total

    def list_all_staging_rows(self, *, import_job_id: int, conn=None) -> list[dict]:
        rows, _ = self.list_staging_rows(import_job_id=import_job_id, offset=0, limit=100000, conn=conn)
        return rows

    def list_valid_rows(self, *, import_job_id: int, conn=None) -> list[dict]:
        _ = conn
        rows = [
            dict(row)
            for row in self.rows.values()
            if int(row["import_job_id"]) == int(import_job_id) and str(row["validation_status"]) == "VALID"
        ]
        rows.sort(key=lambda item: int(item["row_number"]))
        return rows

    def clear_row_errors(self, *, import_job_id: int, conn=None) -> None:
        _ = conn
        for row_error_id in list(self.row_errors.keys()):
            if int(self.row_errors[row_error_id]["import_job_id"]) == int(import_job_id):
                del self.row_errors[row_error_id]

    def reset_rows_for_revalidation(self, *, import_job_id: int, conn=None) -> None:
        _ = conn
        for row in self.rows.values():
            if int(row["import_job_id"]) != int(import_job_id):
                continue
            row["normalized_row_json"] = None
            row["validation_status"] = "PENDING"
            row["commit_status"] = "NOT_COMMITTED"

    def update_row_validation(self, *, import_row_id: int, validation_status: str, normalized_row_json: dict | None, conn=None) -> None:
        _ = conn
        row = self.rows[int(import_row_id)]
        row["validation_status"] = validation_status
        row["normalized_row_json"] = dict(normalized_row_json) if normalized_row_json is not None else None

    def update_row_commit_status(self, *, import_row_id: int, commit_status: str, conn=None) -> None:
        _ = conn
        self.rows[int(import_row_id)]["commit_status"] = commit_status

    def add_row_error(self, *, import_job_id: int, import_row_id: int, error_code: str, error_message: str, error_details: dict | None, conn=None) -> dict:
        _ = conn
        row_error = {
            "import_row_error_id": self.next_row_error_id,
            "import_job_id": int(import_job_id),
            "import_row_staging_id": int(import_row_id),
            "error_code": error_code,
            "error_message": error_message,
            "error_details_json": dict(error_details or {}),
            "created_at": datetime.now(timezone.utc),
        }
        self.row_errors[self.next_row_error_id] = row_error
        self.next_row_error_id += 1
        return dict(row_error)

    def list_row_errors(self, *, import_job_id: int, conn=None) -> list[dict]:
        _ = conn
        rows = [
            dict(item)
            for item in self.row_errors.values()
            if int(item["import_job_id"]) == int(import_job_id)
        ]
        rows.sort(key=lambda item: (int(item["import_row_staging_id"]), int(item["import_row_error_id"])))
        return rows

    def get_row_status_counts(self, *, import_job_id: int, conn=None) -> dict:
        _ = conn
        rows = [row for row in self.rows.values() if int(row["import_job_id"]) == int(import_job_id)]
        return {
            "total_rows": len(rows),
            "valid_rows": sum(1 for row in rows if row["validation_status"] == "VALID"),
            "invalid_rows": sum(1 for row in rows if row["validation_status"] == "INVALID"),
            "pending_rows": sum(1 for row in rows if row["validation_status"] == "PENDING"),
            "committed_rows": sum(1 for row in rows if row["commit_status"] == "COMMITTED"),
            "failed_rows": sum(1 for row in rows if row["commit_status"] == "FAILED"),
        }

    def create_commit_record(self, *, import_job_id: int, commit_status: str, committed_by: int | None, summary_json: dict | None, conn=None) -> dict:
        _ = conn
        row = {
            "import_job_id": int(import_job_id),
            "commit_status": commit_status,
            "committed_by": committed_by,
            "summary_json": dict(summary_json or {}),
        }
        self.commits.append(row)
        return dict(row)

    def add_audit_event(self, *, import_job_id: int, event_type: str, event_payload_json: dict | None, actor_user_id: int | None, actor_agent: str | None, conn=None) -> dict:
        _ = conn
        row = {
            "import_job_id": int(import_job_id),
            "event_type": event_type,
            "event_payload_json": dict(event_payload_json or {}),
            "actor_user_id": actor_user_id,
            "actor_agent": actor_agent,
        }
        self.audit_events.append(row)
        return dict(row)

    def record_md7_status(self, *, import_job_id: int, status: str, actor_user_id: int | None, actor_agent: str | None, details: dict | None = None, conn=None) -> None:
        _ = conn
        self.audit_events.append(
            {
                "import_job_id": int(import_job_id),
                "event_type": "MD7_STATUS",
                "event_payload_json": {"status": status, "details": dict(details or {})},
                "actor_user_id": actor_user_id,
                "actor_agent": actor_agent,
            }
        )

    def get_latest_md7_status(self, *, import_job_id: int, conn=None) -> str | None:
        _ = conn
        for item in reversed(self.audit_events):
            if int(item["import_job_id"]) != int(import_job_id):
                continue
            if item["event_type"] != "MD7_STATUS":
                continue
            return str(item["event_payload_json"].get("status") or "").upper() or None
        return None


class SpyCommitService:
    def __init__(self, fail_student_codes: set[str] | None = None) -> None:
        self.fail_student_codes = {item.strip().upper() for item in (fail_student_codes or set())}
        self.calls: list[dict] = []

    def commit_row(self, *, import_type: str, normalized_row: dict, actor: dict) -> dict:
        self.calls.append(
            {
                "import_type": import_type,
                "normalized_row": dict(normalized_row),
                "actor": dict(actor),
            }
        )

        student_code = str(normalized_row.get("student_code") or "").strip().upper()
        if student_code in self.fail_student_codes:
            raise MasterDataValidationError(
                "Domain validation rejected row",
                details={"student_code": student_code},
            )

        return {"entity": "student", "result": {"student_code": student_code or "N/A"}}


class _FakeCursor:
    def __init__(self, conn: "_FakeConnection") -> None:
        self._conn = conn

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        _ = exc_type
        _ = exc
        _ = tb

    def execute(self, sql: str) -> None:
        self._conn.sql_log.append(sql)
        normalized = sql.strip().upper()
        if normalized.startswith("ROLLBACK TO SAVEPOINT"):
            self._conn.aborted = False


class _FakeConnection:
    def __init__(self) -> None:
        self.aborted = False
        self.sql_log: list[str] = []

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self)


@contextmanager
def _fake_transaction_scope():
    yield None


def _build_service(
    *,
    repository: InMemoryImportFoundationRepository,
    commit_service: SpyCommitService | None = None,
) -> MasterDataImportService:
    preview_service = ImportPreviewService(repository=repository)
    return MasterDataImportService(
        repository=repository,
        validation_service=ImportValidationService(),
        preview_service=preview_service,
        commit_service=commit_service or SpyCommitService(),
        transaction_scope=_fake_transaction_scope,
    )


def test_create_import_job() -> None:
    repo = InMemoryImportFoundationRepository()
    service = _build_service(repository=repo)

    result = service.create_import_job(
        command={
            "import_type": "STUDENTS",
            "rows": [{"student_code": "S001", "full_name": "Student A"}],
        },
        actor={"user_id": 1, "username": "import.bot"},
    )

    assert result["import_job_id"] == 1
    assert result["import_type"] == "STUDENTS"
    assert result["status"] == "QUEUED"
    assert result["counts"]["total_rows"] == 1
    assert repo.jobs[1]["job_status"] == "QUEUED"
    assert any(
        event["event_type"] == "MD8_REQUEST"
        and event["event_payload_json"]["operation"] == "VALIDATE"
        and event["event_payload_json"]["auto_commit"] is True
        for event in repo.audit_events
    )


def test_create_import_job_rejects_replacement_character_before_staging() -> None:
    repo = InMemoryImportFoundationRepository()
    service = _build_service(repository=repo)

    with pytest.raises(MasterDataValidationError) as exc:
        service.create_import_job(
            command={
                "import_type": "INSTRUCTORS",
                "rows": [{"instructor_code": "GV001", "full_name": "N�ng Ng?c D?"}],
            },
            actor={"user_id": 1, "username": "import.bot"},
        )

    assert "CSV UTF-8" in str(exc.value)
    assert repo.rows == {}


def test_import_templates_match_validation_contract() -> None:
    service = ImportTemplateService()

    result = service.list_import_templates(actor={"user_id": 1})
    by_type = {item["import_type"]: item for item in result["items"]}

    assert set(by_type) == ImportValidationService.SUPPORTED_IMPORT_TYPES
    assert by_type["STUDENTS"]["label"] == "Sinh viên"
    assert by_type["STUDENTS"]["sample_row"]["student_status"] == "ACTIVE"
    assert "student_code" in by_type["STUDENTS"]["sample_row"]
    assert by_type["INSTRUCTORS"]["sample_row"]["full_name"] == "Nông Ngọc Duy"
    assert by_type["COURSES"]["label"] == "Môn học"
    assert by_type["CLASS_SECTIONS"]["label"] == "Lớp học phần"
    instructor_columns = [column["name"] for column in by_type["INSTRUCTORS"]["columns"]]
    assert "department_code" in instructor_columns
    assert "department_id" in instructor_columns
    course_columns = [column["name"] for column in by_type["COURSES"]["columns"]]
    assert "department_code" in course_columns
    assert "department_id" in course_columns
    class_section_columns = [column["name"] for column in by_type["CLASS_SECTIONS"]["columns"]]
    assert "course_code" in class_section_columns
    assert "course_id" in class_section_columns
    assert "term_code" in class_section_columns
    assert "term_id" in class_section_columns
    assert any(column["name"] == "station_code" for column in by_type["STATIONS"]["columns"])


def test_validate_student_rows_with_one_valid_and_one_invalid() -> None:
    repo = InMemoryImportFoundationRepository()
    service = _build_service(repository=repo)

    job = service.create_import_job(
        command={
            "import_type": "STUDENTS",
            "rows": [
                {"student_code": "S001", "full_name": "Student A"},
                {"student_code": "", "full_name": "Missing code"},
            ],
        },
        actor={"user_id": 1, "username": "import.bot"},
    )

    validated = service.validate_import_job(import_job_id=job["import_job_id"], actor={"user_id": 1})

    assert validated["status"] == "VALIDATION_FAILED"
    assert validated["counts"]["valid_rows"] == 1
    assert validated["counts"]["invalid_rows"] == 1


def test_instructor_row_with_invalid_text_encoding_fails_validation_and_is_not_committed() -> None:
    repo = InMemoryImportFoundationRepository()
    commit_service = SpyCommitService()
    service = _build_service(repository=repo, commit_service=commit_service)

    with pytest.raises(MasterDataValidationError):
        service.create_import_job(
            command={
                "import_type": "INSTRUCTORS",
                "rows": [{"instructor_code": "GV001", "full_name": "N�ng Ng?c D?"}],
            },
            actor={"user_id": 1, "username": "import.bot"},
        )

    assert commit_service.calls == []


def test_validate_station_rows() -> None:
    repo = InMemoryImportFoundationRepository()
    service = _build_service(repository=repo)

    job = service.create_import_job(
        command={
            "import_type": "STATIONS",
            "rows": [{"room_id": "10", "station_code": "a101-01", "seat_no": "01"}],
        },
        actor={"user_id": 1, "username": "import.bot"},
    )

    validated = service.validate_import_job(import_job_id=job["import_job_id"], actor={"user_id": 1})
    rows_preview = service.list_import_rows(
        import_job_id=job["import_job_id"],
        pagination={"page": 1, "page_size": 20},
        actor={"user_id": 1},
    )

    assert validated["status"] == "VALIDATED"
    assert rows_preview["items"][0]["normalized_row"]["room_id"] == 10
    assert rows_preview["items"][0]["normalized_row"]["station_code"] == "A101-01"


def test_row_errors_stored_after_validation() -> None:
    repo = InMemoryImportFoundationRepository()
    service = _build_service(repository=repo)

    job = service.create_import_job(
        command={
            "import_type": "STUDENTS",
            "rows": [{"student_code": "", "full_name": "Missing code"}],
        },
        actor={"user_id": 1, "username": "import.bot"},
    )

    service.validate_import_job(import_job_id=job["import_job_id"], actor={"user_id": 1})
    rows_preview = service.list_import_rows(
        import_job_id=job["import_job_id"],
        pagination={"page": 1, "page_size": 20},
        actor={"user_id": 1},
    )

    assert len(rows_preview["items"]) == 1
    assert rows_preview["items"][0]["errors"]
    assert rows_preview["items"][0]["errors"][0]["code"] == "required"


def test_commit_valid_rows() -> None:
    repo = InMemoryImportFoundationRepository()
    commit_service = SpyCommitService()
    service = _build_service(repository=repo, commit_service=commit_service)

    job = service.create_import_job(
        command={
            "import_type": "STUDENTS",
            "rows": [{"student_code": "S001", "full_name": "Student A"}],
        },
        actor={"user_id": 1, "username": "import.bot"},
    )
    service.validate_import_job(import_job_id=job["import_job_id"], actor={"user_id": 1})

    committed = service.commit_import_job(
        import_job_id=job["import_job_id"],
        command={"idempotency_key": "k-1"},
        actor={"user_id": 1, "username": "import.bot"},
    )

    assert committed["status"] == "COMMITTED"
    assert committed["committed_rows"] == 1
    assert committed["failed_rows"] == 0
    assert len(commit_service.calls) == 1


def test_commit_invalid_job_rejected() -> None:
    repo = InMemoryImportFoundationRepository()
    service = _build_service(repository=repo)

    job = service.create_import_job(
        command={
            "import_type": "STUDENTS",
            "rows": [{"student_code": "", "full_name": "Missing code"}],
        },
        actor={"user_id": 1, "username": "import.bot"},
    )
    service.validate_import_job(import_job_id=job["import_job_id"], actor={"user_id": 1})

    with pytest.raises(MasterDataValidationError):
        service.commit_import_job(
            import_job_id=job["import_job_id"],
            command={"idempotency_key": "k-2"},
            actor={"user_id": 1, "username": "import.bot"},
        )


def test_commit_uses_master_data_service_validation() -> None:
    repo = InMemoryImportFoundationRepository()
    commit_service = SpyCommitService(fail_student_codes={"FAILME"})
    service = _build_service(repository=repo, commit_service=commit_service)

    job = service.create_import_job(
        command={
            "import_type": "STUDENTS",
            "rows": [
                {"student_code": "S001", "full_name": "Student A"},
                {"student_code": "FAILME", "full_name": "Student B"},
            ],
        },
        actor={"user_id": 1, "username": "import.bot"},
    )
    service.validate_import_job(import_job_id=job["import_job_id"], actor={"user_id": 1})

    committed = service.commit_import_job(
        import_job_id=job["import_job_id"],
        command={"idempotency_key": "k-3"},
        actor={"user_id": 1, "username": "import.bot"},
    )

    assert committed["status"] == "COMMIT_FAILED"
    assert committed["committed_rows"] == 1
    assert committed["failed_rows"] == 1
    assert len(commit_service.calls) == 2


def test_instructor_unknown_department_code_creates_row_error_and_keeps_other_rows() -> None:
    repo = InMemoryImportFoundationRepository()

    class _InstructorCommitService:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def commit_row(self, *, import_type: str, normalized_row: dict, actor: dict) -> dict:
            self.calls.append({"import_type": import_type, "normalized_row": dict(normalized_row), "actor": dict(actor)})
            if str(normalized_row.get("instructor_code")) == "GV_BAD":
                class _UnknownDepartmentError(Exception):
                    code = "unknown_department_code"
                    message = "Department code not found: SFA"
                    details = {"department_code": "SFA"}

                raise _UnknownDepartmentError("Department code not found: SFA")
            return {"entity": "instructor", "result": {"ok": True}}

    service = _build_service(repository=repo, commit_service=_InstructorCommitService())  # type: ignore[arg-type]
    job = service.create_import_job(
        command={
            "import_type": "INSTRUCTORS",
            "rows": [
                {"instructor_code": "GV_OK", "full_name": "Giang Vien A", "department_code": "SFA"},
                {"instructor_code": "GV_BAD", "full_name": "Giang Vien B", "department_code": "SFA"},
            ],
        },
        actor={"user_id": 1, "username": "import.bot"},
    )
    service.validate_import_job(import_job_id=job["import_job_id"], actor={"user_id": 1})
    result = service.commit_import_job(
        import_job_id=job["import_job_id"],
        command={"idempotency_key": "k-ins-1"},
        actor={"user_id": 1, "username": "import.bot"},
    )

    assert result["status"] == "COMMIT_FAILED"
    assert result["committed_rows"] == 1
    assert result["failed_rows"] == 1

    errors = repo.list_row_errors(import_job_id=job["import_job_id"])
    assert len(errors) == 1
    assert errors[0]["error_code"] == "unknown_department_code"
    assert "Department code not found: SFA" in errors[0]["error_message"]
    assert "invalid literal for int()" not in errors[0]["error_message"]


def test_commit_row_database_error_rolls_back_to_savepoint_and_continues() -> None:
    repo = InMemoryImportFoundationRepository()
    fake_conn = _FakeConnection()

    class _AbortAwareRepository(InMemoryImportFoundationRepository):
        def update_row_commit_status(self, *, import_row_id: int, commit_status: str, conn=None) -> None:
            if isinstance(conn, _FakeConnection) and conn.aborted:
                raise RuntimeError("current transaction is aborted, commands ignored until end of transaction block")
            super().update_row_commit_status(import_row_id=import_row_id, commit_status=commit_status, conn=conn)

        def add_row_error(self, *, import_job_id: int, import_row_id: int, error_code: str, error_message: str, error_details: dict | None, conn=None) -> dict:
            if isinstance(conn, _FakeConnection) and conn.aborted:
                raise RuntimeError("current transaction is aborted, commands ignored until end of transaction block")
            return super().add_row_error(
                import_job_id=import_job_id,
                import_row_id=import_row_id,
                error_code=error_code,
                error_message=error_message,
                error_details=error_details,
                conn=conn,
            )

    class _DbFailingCommitService(SpyCommitService):
        def commit_row(self, *, import_type: str, normalized_row: dict, actor: dict) -> dict:
            code = str(normalized_row.get("student_code") or "").strip().upper()
            if code == "DUP":
                fake_conn.aborted = True
                raise RuntimeError("duplicate key value violates unique constraint")
            return super().commit_row(import_type=import_type, normalized_row=normalized_row, actor=actor)

    @contextmanager
    def _fake_conn_scope():
        yield fake_conn

    abort_repo = _AbortAwareRepository()
    service = MasterDataImportService(
        repository=abort_repo,
        validation_service=ImportValidationService(),
        preview_service=ImportPreviewService(repository=abort_repo),
        commit_service=_DbFailingCommitService(),
        transaction_scope=_fake_conn_scope,
    )

    job = service.create_import_job(
        command={
            "import_type": "STUDENTS",
            "rows": [
                {"student_code": "OK1", "full_name": "Student A"},
                {"student_code": "DUP", "full_name": "Student B"},
                {"student_code": "OK2", "full_name": "Student C"},
            ],
        },
        actor={"user_id": 1, "username": "import.bot"},
    )
    service.validate_import_job(import_job_id=job["import_job_id"], actor={"user_id": 1})

    committed = service.commit_import_job(
        import_job_id=job["import_job_id"],
        command={"idempotency_key": "k-db"},
        actor={"user_id": 1, "username": "import.bot"},
    )

    assert committed["status"] == "COMMIT_FAILED"
    assert committed["committed_rows"] == 2
    assert committed["failed_rows"] == 1
    assert any("ROLLBACK TO SAVEPOINT md7_commit_row_" in sql for sql in fake_conn.sql_log)
    assert len(abort_repo.list_row_errors(import_job_id=job["import_job_id"])) == 1


def test_pagination_for_import_rows() -> None:
    repo = InMemoryImportFoundationRepository()
    service = _build_service(repository=repo)

    job = service.create_import_job(
        command={
            "import_type": "STUDENTS",
            "rows": [
                {"student_code": "S001", "full_name": "Student A"},
                {"student_code": "S002", "full_name": "Student B"},
                {"student_code": "S003", "full_name": "Student C"},
            ],
        },
        actor={"user_id": 1, "username": "import.bot"},
    )

    page_2 = service.list_import_rows(
        import_job_id=job["import_job_id"],
        pagination={"page": 2, "page_size": 1},
        actor={"user_id": 1},
    )

    assert page_2["pagination"]["page"] == 2
    assert page_2["pagination"]["page_size"] == 1
    assert page_2["pagination"]["total"] == 3
    assert len(page_2["items"]) == 1
    assert page_2["items"][0]["row_number"] == 2
