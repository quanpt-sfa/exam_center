"""Service-level tests for MD-2 identity/student/instructor workflows."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from app.modules.master_data.common.errors import MasterDataConflictError
from app.modules.master_data.common.errors import MasterDataNotFoundError
from app.modules.master_data.common.errors import MasterDataSensitiveAccessError
from app.modules.master_data.repositories.address_repository import AddressRepository
from app.modules.master_data.repositories.contact_repository import ContactRepository
from app.modules.master_data.services.instructor_service import InstructorService
from app.modules.master_data.services.person_service import PersonService
from app.modules.master_data.services.student_service import StudentService


class InMemoryPersonRepository:
    def __init__(self) -> None:
        self.people: dict[int, dict] = {}
        self.next_person_id = 1

    def create_person(
        self,
        *,
        full_name: str,
        date_of_birth,
        gender_code,
        national_id,
        person_status: str,
        conn=None,
    ) -> dict:
        _ = conn
        person_id = self.next_person_id
        self.next_person_id += 1
        row = {
            "person_id": person_id,
            "full_name": full_name,
            "date_of_birth": date_of_birth,
            "gender_code": gender_code,
            "national_id": national_id,
            "person_status": person_status,
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
        }
        self.people[person_id] = row
        return dict(row)

    def update_person(self, *, person_id: int, payload: dict, conn=None) -> dict | None:
        _ = conn
        row = self.people.get(person_id)
        if row is None:
            return None
        row.update(payload)
        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)


class InMemoryStudentRepository:
    def __init__(self, *, person_repository: InMemoryPersonRepository) -> None:
        self.person_repository = person_repository
        self.students: dict[int, dict] = {}
        self.next_student_id = 1
        self.fail_on_create = False

    def list_students(self, *, query_text, status, program_id, offset, limit, conn=None) -> tuple[list[dict], int]:
        _ = conn
        rows: list[dict] = []
        for row in self.students.values():
            person = self.person_repository.people[int(row["person_id"])]
            candidate = {
                "student_id": row["student_id"],
                "person_id": row["person_id"],
                "student_code": row["student_code"],
                "program_id": row.get("program_id"),
                "cohort": row.get("cohort"),
                "entry_year": row.get("entry_year"),
                "student_status": row.get("student_status"),
                "full_name": person.get("full_name"),
                "person_status": person.get("person_status"),
                "program_code": row.get("program_code"),
                "program_name": row.get("program_name"),
                "department_id": row.get("department_id"),
                "department_code": row.get("department_code"),
                "department_name": row.get("department_name"),
            }
            rows.append(candidate)

        if query_text:
            needle = str(query_text).strip().lower()
            rows = [
                row
                for row in rows
                if needle in str(row.get("student_code", "")).lower()
                or needle in str(row.get("full_name", "")).lower()
            ]

        if status:
            rows = [row for row in rows if str(row.get("student_status", "")).upper() == str(status).upper()]

        if program_id is not None:
            rows = [row for row in rows if row.get("program_id") == program_id]

        rows.sort(key=lambda item: int(item["student_id"]), reverse=True)
        total = len(rows)
        return rows[offset : offset + limit], total

    def get_student_by_id(self, student_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.students.get(student_id)
        if row is None:
            return None
        person = self.person_repository.people[int(row["person_id"])]
        return {
            **row,
            "full_name": person.get("full_name"),
            "date_of_birth": person.get("date_of_birth"),
            "gender_code": person.get("gender_code"),
            "national_id": person.get("national_id"),
            "person_status": person.get("person_status"),
            "person_created_at": person.get("created_at"),
            "person_updated_at": person.get("updated_at"),
            "student_created_at": row.get("created_at"),
            "student_updated_at": row.get("updated_at"),
            "program_code": row.get("program_code"),
            "program_name": row.get("program_name"),
            "department_id": row.get("department_id"),
            "department_code": row.get("department_code"),
            "department_name": row.get("department_name"),
        }

    def get_student_by_code(self, student_code: str, conn=None) -> dict | None:
        _ = conn
        code = student_code.strip().lower()
        for row in self.students.values():
            if str(row["student_code"]).lower() == code:
                return dict(row)
        return None

    def create_student(
        self,
        *,
        person_id: int,
        student_code: str,
        program_id,
        cohort,
        entry_year,
        student_status,
        conn=None,
    ) -> dict:
        _ = conn
        if self.fail_on_create:
            raise RuntimeError("simulated_student_profile_insert_failure")

        student_id = self.next_student_id
        self.next_student_id += 1
        row = {
            "student_id": student_id,
            "person_id": person_id,
            "student_code": student_code.strip(),
            "program_id": program_id,
            "cohort": cohort,
            "entry_year": entry_year,
            "student_status": str(student_status).upper(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
            "program_code": None,
            "program_name": None,
            "department_id": None,
            "department_code": None,
            "department_name": None,
        }
        self.students[student_id] = row
        return dict(row)

    def update_student(self, *, student_id: int, payload: dict, conn=None) -> dict | None:
        _ = conn
        row = self.students.get(student_id)
        if row is None:
            return None
        row.update(payload)
        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)

    def deactivate_student(self, *, student_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.students.get(student_id)
        if row is None:
            return None
        row["student_status"] = "SUSPENDED"
        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)


class InMemoryInstructorRepository:
    def __init__(self, *, person_repository: InMemoryPersonRepository) -> None:
        self.person_repository = person_repository
        self.instructors: dict[int, dict] = {}
        self.next_instructor_id = 1

    def list_instructors(self, *, query_text, status, department_id, offset, limit, conn=None) -> tuple[list[dict], int]:
        _ = conn
        rows: list[dict] = []
        for row in self.instructors.values():
            person = self.person_repository.people[int(row["person_id"])]
            rows.append(
                {
                    "instructor_id": row["instructor_id"],
                    "person_id": row["person_id"],
                    "instructor_code": row["instructor_code"],
                    "department_id": row.get("department_id"),
                    "instructor_status": row.get("instructor_status"),
                    "full_name": person.get("full_name"),
                    "person_status": person.get("person_status"),
                    "department_code": row.get("department_code"),
                    "department_name": row.get("department_name"),
                    "instructor_created_at": row.get("created_at"),
                    "instructor_updated_at": row.get("updated_at"),
                }
            )

        if query_text:
            needle = str(query_text).strip().lower()
            rows = [
                row
                for row in rows
                if needle in str(row.get("instructor_code", "")).lower()
                or needle in str(row.get("full_name", "")).lower()
            ]

        if status:
            rows = [row for row in rows if str(row.get("instructor_status", "")).upper() == str(status).upper()]

        if department_id is not None:
            rows = [row for row in rows if row.get("department_id") == department_id]

        rows.sort(key=lambda item: int(item["instructor_id"]), reverse=True)
        total = len(rows)
        return rows[offset : offset + limit], total

    def get_instructor_by_id(self, instructor_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.instructors.get(instructor_id)
        if row is None:
            return None
        person = self.person_repository.people[int(row["person_id"])]
        return {
            **row,
            "full_name": person.get("full_name"),
            "date_of_birth": person.get("date_of_birth"),
            "gender_code": person.get("gender_code"),
            "national_id": person.get("national_id"),
            "person_status": person.get("person_status"),
            "instructor_created_at": row.get("created_at"),
            "instructor_updated_at": row.get("updated_at"),
            "department_code": row.get("department_code"),
            "department_name": row.get("department_name"),
        }

    def get_instructor_by_code(self, instructor_code: str, conn=None) -> dict | None:
        _ = conn
        code = instructor_code.strip().lower()
        for row in self.instructors.values():
            if str(row["instructor_code"]).lower() == code:
                return dict(row)
        return None

    def create_instructor(self, *, person_id: int, instructor_code: str, department_id, instructor_status, conn=None) -> dict:
        _ = conn
        instructor_id = self.next_instructor_id
        self.next_instructor_id += 1
        row = {
            "instructor_id": instructor_id,
            "person_id": person_id,
            "instructor_code": instructor_code.strip(),
            "department_id": department_id,
            "instructor_status": str(instructor_status).upper(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
            "department_code": None,
            "department_name": None,
        }
        self.instructors[instructor_id] = row
        return dict(row)

    def update_instructor(self, *, instructor_id: int, payload: dict, conn=None) -> dict | None:
        _ = conn
        row = self.instructors.get(instructor_id)
        if row is None:
            return None
        row.update(payload)
        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)

    def deactivate_instructor(self, *, instructor_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.instructors.get(instructor_id)
        if row is None:
            return None
        row["instructor_status"] = "INACTIVE"
        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)


class InMemoryContactRepository(ContactRepository):
    def __init__(self) -> None:
        self.by_person: dict[int, dict[str, dict]] = {}

    def upsert_primary_contact(
        self,
        *,
        person_id: int,
        contact_type: str,
        contact_value: str,
        label,
        is_verified: bool,
        valid_from,
        conn=None,
    ) -> dict:
        _ = (label, valid_from, conn)
        key = str(contact_type).upper()
        storage = self.by_person.setdefault(person_id, {})
        row = {
            "person_id": person_id,
            "contact_type": key,
            "contact_value": contact_value,
            "is_verified": bool(is_verified),
            "valid_from": None,
            "valid_to": None,
        }
        storage[key] = row
        return dict(row)

    def list_primary_contacts(self, *, person_id: int, conn=None) -> list[dict]:
        _ = conn
        values = list(self.by_person.get(person_id, {}).values())
        values.sort(key=lambda item: str(item["contact_type"]))
        return [dict(item) for item in values]


class InMemoryAddressRepository(AddressRepository):
    def __init__(self) -> None:
        self.by_person: dict[int, dict[str, dict]] = {}

    def upsert_primary_address(
        self,
        *,
        person_id: int,
        address_type: str,
        address_line: str,
        ward,
        district,
        province,
        country,
        valid_from,
        conn=None,
    ) -> dict:
        _ = (valid_from, conn)
        key = str(address_type).upper()
        storage = self.by_person.setdefault(person_id, {})
        row = {
            "person_id": person_id,
            "address_type": key,
            "address_line": address_line,
            "ward": ward,
            "district": district,
            "province": province,
            "country": country,
            "valid_from": None,
            "valid_to": None,
        }
        storage[key] = row
        return dict(row)

    def list_primary_addresses(self, *, person_id: int, conn=None) -> list[dict]:
        _ = conn
        values = list(self.by_person.get(person_id, {}).values())
        values.sort(key=lambda item: str(item["address_type"]))
        return [dict(item) for item in values]


class InMemoryAuditHook:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def record(self, event) -> None:
        self.events.append(
            {
                "entity": getattr(event, "entity", None),
                "action": getattr(event, "action", None),
                "actor_user_id": getattr(event, "actor_user_id", None),
                "entity_id": getattr(event, "entity_id", None),
                "payload": dict(getattr(event, "payload", None) or {}),
            }
        )


class InMemoryAccountProvisioningService:
    def __init__(self, *, fail: bool = False) -> None:
        self.accounts: dict[int, dict] = {}
        self.next_user_id = 1
        self.calls: list[dict] = []
        self.fail = fail

    def ensure_person_account(
        self,
        *,
        person_id: int,
        username: str,
        role_code: str,
        actor_user_id: int | None = None,
        conn=None,
    ) -> dict:
        _ = conn
        self.calls.append(
            {
                "person_id": person_id,
                "username": username,
                "role_code": role_code,
                "actor_user_id": actor_user_id,
            }
        )
        if self.fail:
            raise RuntimeError("simulated_account_provisioning_failure")

        account = self.accounts.get(int(person_id))
        if account is None:
            account = {
                "user_id": self.next_user_id,
                "person_id": int(person_id),
                "username": username,
                "email_login": None,
                "user_status": "ACTIVE",
                "roles": [],
            }
            self.accounts[int(person_id)] = account
            self.next_user_id += 1

        if role_code not in account["roles"]:
            account["roles"].append(role_code)
        return dict(account)


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
        "permissions": ["*", "master_data:write", "master_data:read", "student:sensitive_read"],
    }


def _reader_user() -> dict:
    return {
        "user_id": 2,
        "username": "reader",
        "roles": ["ACADEMIC_OFFICER"],
        "permissions": ["master_data:read"],
    }


def _build_student_service(*, fail_on_create: bool = False) -> tuple[StudentService, InMemoryStudentRepository]:
    person_repo = InMemoryPersonRepository()
    student_repo = InMemoryStudentRepository(person_repository=person_repo)
    student_repo.fail_on_create = fail_on_create
    person_service = PersonService(person_repository=person_repo)
    contact_repo = InMemoryContactRepository()
    address_repo = InMemoryAddressRepository()
    audit = InMemoryAuditHook()
    account_provisioner = InMemoryAccountProvisioningService()

    tx = SnapshotTransactionManager(person_repo, student_repo, contact_repo, address_repo, audit, account_provisioner)
    service = StudentService(
        student_repository=student_repo,
        person_service=person_service,
        contact_repository=contact_repo,
        address_repository=address_repo,
        account_provisioning_service=account_provisioner,
        audit_hook=audit,
        transaction_scope=tx.scope,
    )
    return service, student_repo


def _build_instructor_service() -> tuple[InstructorService, InMemoryInstructorRepository]:
    person_repo = InMemoryPersonRepository()
    instructor_repo = InMemoryInstructorRepository(person_repository=person_repo)
    person_service = PersonService(person_repository=person_repo)
    contact_repo = InMemoryContactRepository()
    address_repo = InMemoryAddressRepository()
    audit = InMemoryAuditHook()
    account_provisioner = InMemoryAccountProvisioningService()

    tx = SnapshotTransactionManager(person_repo, instructor_repo, contact_repo, address_repo, audit, account_provisioner)
    service = InstructorService(
        instructor_repository=instructor_repo,
        person_service=person_service,
        contact_repository=contact_repo,
        address_repository=address_repo,
        account_provisioning_service=account_provisioner,
        audit_hook=audit,
        transaction_scope=tx.scope,
    )
    return service, instructor_repo


def test_create_student_success() -> None:
    service, _repo = _build_student_service()

    result = service.create_student(
        command={
            "full_name": "Nguyen Van A",
            "student_code": "ST-0001",
            "entry_year": 2024,
            "contacts": [{"contact_type": "EMAIL", "contact_value": "STUDENT@EXAMPLE.COM", "is_verified": True}],
        },
        actor=_admin_user(),
    )

    assert result["student_id"] == 1
    assert result["student_code"] == "ST-0001"
    assert result["full_name"] == "Nguyen Van A"


def test_create_student_duplicate_code_rejected() -> None:
    service, _repo = _build_student_service()
    actor = _admin_user()

    service.create_student(command={"full_name": "A", "student_code": "ST-0001"}, actor=actor)

    with pytest.raises(MasterDataConflictError):
        service.create_student(command={"full_name": "B", "student_code": "ST-0001"}, actor=actor)


def test_create_student_rolls_back_when_profile_insert_fails() -> None:
    service, repo = _build_student_service(fail_on_create=True)

    with pytest.raises(RuntimeError):
        service.create_student(command={"full_name": "Rollback User", "student_code": "ST-ROLLBACK"}, actor=_admin_user())

    assert repo.students == {}


def test_list_students_pagination() -> None:
    service, _repo = _build_student_service()

    for idx in range(1, 6):
        service.create_student(
            command={"full_name": f"Student {idx}", "student_code": f"ST-{idx:04d}"},
            actor=_admin_user(),
        )

    response = service.list_students(
        filters={"query": "Student"},
        pagination={"page": 2, "page_size": 2},
        actor=_reader_user(),
    )

    assert len(response["items"]) == 2
    assert response["pagination"]["page"] == 2
    assert response["pagination"]["total"] == 5


def test_get_student_not_found() -> None:
    service, _repo = _build_student_service()

    with pytest.raises(MasterDataNotFoundError):
        service.get_student(student_id=999, actor=_reader_user(), include_sensitive=False)


def test_student_sensitive_fields_hidden_by_default() -> None:
    service, _repo = _build_student_service()

    created = service.create_student(
        command={
            "full_name": "Sensitive User",
            "student_code": "ST-SAFE",
            "national_id": "012345678",
            "contacts": [{"contact_type": "EMAIL", "contact_value": "safe@example.com"}],
        },
        actor=_admin_user(),
    )

    result = service.get_student(student_id=int(created["student_id"]), actor=_reader_user(), include_sensitive=False)

    assert "sensitive" not in result
    assert "contacts" not in result
    assert "addresses" not in result


def test_student_sensitive_fields_require_permission() -> None:
    service, _repo = _build_student_service()

    created = service.create_student(
        command={
            "full_name": "Sensitive User",
            "student_code": "ST-SENSITIVE",
            "national_id": "012345678",
            "contacts": [{"contact_type": "EMAIL", "contact_value": "safe@example.com"}],
        },
        actor=_admin_user(),
    )

    with pytest.raises(MasterDataSensitiveAccessError):
        service.get_student(student_id=int(created["student_id"]), actor=_reader_user(), include_sensitive=True)

    allowed = service.get_student(student_id=int(created["student_id"]), actor=_admin_user(), include_sensitive=True)
    assert "sensitive" in allowed
    assert allowed["sensitive"]["national_id"] == "012345678"
    assert allowed["contacts"][0]["contact_value"] == "safe@example.com"


def test_create_instructor_success() -> None:
    service, _repo = _build_instructor_service()

    result = service.create_instructor(
        command={"full_name": "Dr. Tran", "instructor_code": "INS-0001"},
        actor=_admin_user(),
    )

    assert result["instructor_id"] == 1
    assert result["instructor_code"] == "INS-0001"
    assert result["full_name"] == "Dr. Tran"


def test_create_instructor_duplicate_code_rejected() -> None:
    service, _repo = _build_instructor_service()
    actor = _admin_user()

    service.create_instructor(command={"full_name": "X", "instructor_code": "INS-001"}, actor=actor)

    with pytest.raises(MasterDataConflictError):
        service.create_instructor(command={"full_name": "Y", "instructor_code": "INS-001"}, actor=actor)
