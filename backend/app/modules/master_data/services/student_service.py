"""Service layer for student master-data workflows."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager

from app.infrastructure.database.unit_of_work import database_unit_of_work
from app.modules.master_data.common.audit import MasterDataAuditEvent
from app.modules.master_data.common.audit import MasterDataAuditHook
from app.modules.master_data.common.audit import build_master_data_audit_hook
from app.modules.master_data.common.errors import MasterDataConflictError
from app.modules.master_data.common.errors import MasterDataNotFoundError
from app.modules.master_data.common.errors import MasterDataSensitiveAccessError
from app.modules.master_data.common.errors import MasterDataValidationError
from app.modules.master_data.common.pagination import build_pagination_metadata
from app.modules.master_data.common.pagination import build_pagination_params
from app.modules.master_data.repositories.address_repository import AddressRepository
from app.modules.master_data.repositories.contact_repository import ContactRepository
from app.modules.master_data.repositories.student_repository import StudentRepository
from app.modules.master_data.services.account_provisioning_service import AccountProvisioningService
from app.modules.master_data.services.account_provisioning_service import build_account_provisioning_service
from app.modules.master_data.services.person_service import PersonService


class StudentService:
    """Coordinates student/person/contact persistence with one transaction boundary."""

    def __init__(
        self,
        *,
        student_repository: StudentRepository | None = None,
        person_service: PersonService | None = None,
        contact_repository: ContactRepository | None = None,
        address_repository: AddressRepository | None = None,
        account_provisioning_service: AccountProvisioningService | None = None,
        audit_hook: MasterDataAuditHook | None = None,
        transaction_scope: Callable[[], object] | None = None,
    ) -> None:
        self._student_repository = student_repository or StudentRepository()
        self._person_service = person_service or PersonService()
        self._contact_repository = contact_repository or ContactRepository()
        self._address_repository = address_repository or AddressRepository()
        self._account_provisioning_service = account_provisioning_service or build_account_provisioning_service()
        self._audit_hook = audit_hook or build_master_data_audit_hook()

        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif any(
            dep is not None
            for dep in (
                student_repository,
                person_service,
                contact_repository,
                address_repository,
                account_provisioning_service,
                audit_hook,
            )
        ):
            self._transaction_scope = self._null_transaction_scope
        else:
            self._transaction_scope = database_unit_of_work

    @staticmethod
    @contextmanager
    def _null_transaction_scope():
        yield None

    @staticmethod
    def _has_permission(actor: dict | None, permission: str) -> bool:
        if not actor:
            return False

        required = permission.strip().lower()
        permissions = {str(item).strip().lower() for item in actor.get("permissions", []) if str(item).strip()}
        roles = {str(item).strip().upper() for item in actor.get("roles", []) if str(item).strip()}

        if "*" in permissions or required in permissions:
            return True
        return "ADMIN" in roles

    @staticmethod
    def _normalize_contact_value(contact_type: str, value: str) -> str:
        normalized_type = contact_type.strip().upper()
        normalized_value = value.strip()

        if "EMAIL" in normalized_type:
            return normalized_value.lower()

        if "PHONE" in normalized_type or normalized_type == "ZALO":
            kept = [ch for ch in normalized_value if ch.isdigit() or ch == "+"]
            if kept and kept.count("+") > 1:
                kept = [kept[0]] + [ch for ch in kept[1:] if ch != "+"]
            return "".join(kept)

        return normalized_value

    @staticmethod
    def _safe_student_item(row: dict) -> dict:
        return {
            "student_id": row.get("student_id"),
            "person_id": row.get("person_id"),
            "student_code": row.get("student_code"),
            "full_name": row.get("full_name"),
            "student_status": row.get("student_status"),
            "person_status": row.get("person_status"),
            "program_id": row.get("program_id"),
            "program_code": row.get("program_code"),
            "program_name": row.get("program_name"),
            "department_id": row.get("department_id"),
            "department_code": row.get("department_code"),
            "department_name": row.get("department_name"),
            "cohort": row.get("cohort"),
            "entry_year": row.get("entry_year"),
        }

    @staticmethod
    def _full_student_detail(row: dict) -> dict:
        return {
            "student_id": row.get("student_id"),
            "person_id": row.get("person_id"),
            "student_code": row.get("student_code"),
            "full_name": row.get("full_name"),
            "student_status": row.get("student_status"),
            "person_status": row.get("person_status"),
            "program_id": row.get("program_id"),
            "program_code": row.get("program_code"),
            "program_name": row.get("program_name"),
            "department_id": row.get("department_id"),
            "department_code": row.get("department_code"),
            "department_name": row.get("department_name"),
            "cohort": row.get("cohort"),
            "entry_year": row.get("entry_year"),
            "created_at": row.get("student_created_at"),
            "updated_at": row.get("student_updated_at"),
            "person_created_at": row.get("person_created_at"),
            "person_updated_at": row.get("person_updated_at"),
            "sensitive": {
                "date_of_birth": row.get("date_of_birth"),
                "gender_code": row.get("gender_code"),
                "national_id": row.get("national_id"),
            },
        }

    @staticmethod
    def _strip_none(payload: dict) -> dict:
        return {key: value for key, value in payload.items() if value is not None}

    def _persist_contacts(self, *, person_id: int, contacts: list[dict] | None, conn: object | None) -> list[dict]:
        if not contacts:
            return []

        rows: list[dict] = []
        for contact in contacts:
            contact_type = str(contact.get("contact_type", "")).strip().upper()
            if not contact_type:
                continue

            contact_value_raw = str(contact.get("contact_value", "")).strip()
            if not contact_value_raw:
                continue

            row = self._contact_repository.upsert_primary_contact(
                person_id=person_id,
                contact_type=contact_type,
                contact_value=self._normalize_contact_value(contact_type, contact_value_raw),
                label=contact.get("label"),
                is_verified=bool(contact.get("is_verified", False)),
                valid_from=None,
                conn=conn,
            )
            rows.append(row)

        return rows

    def _persist_addresses(self, *, person_id: int, addresses: list[dict] | None, conn: object | None) -> list[dict]:
        if not addresses:
            return []

        rows: list[dict] = []
        for address in addresses:
            address_type = str(address.get("address_type", "")).strip().upper()
            if not address_type:
                continue

            address_line = str(address.get("address_line", "")).strip()
            if not address_line:
                continue

            row = self._address_repository.upsert_primary_address(
                person_id=person_id,
                address_type=address_type,
                address_line=address_line,
                ward=address.get("ward"),
                district=address.get("district"),
                province=address.get("province"),
                country=address.get("country"),
                valid_from=None,
                conn=conn,
            )
            rows.append(row)

        return rows

    def list_students(self, *, filters: dict | None, pagination: dict | None, actor: dict) -> dict:
        _ = actor
        pagination = pagination or {}
        params = build_pagination_params(
            page=pagination.get("page"),
            page_size=pagination.get("page_size"),
        )

        safe_filters = filters or {}
        rows, total_items = self._student_repository.list_students(
            query_text=safe_filters.get("query"),
            status=safe_filters.get("status"),
            program_id=safe_filters.get("program_id"),
            offset=params.offset,
            limit=params.limit,
        )

        return {
            "items": [self._safe_student_item(row) for row in rows],
            "pagination": build_pagination_metadata(
                page=params.page,
                page_size=params.page_size,
                total=total_items,
            ),
        }

    def get_student(self, *, student_id: int, actor: dict, include_sensitive: bool = False) -> dict:
        row = self._student_repository.get_student_by_id(student_id)
        if row is None:
            raise MasterDataNotFoundError("Student not found", details={"student_id": student_id})

        payload = self._safe_student_item(row)
        payload["created_at"] = row.get("student_created_at")
        payload["updated_at"] = row.get("student_updated_at")

        if include_sensitive:
            if not self._has_permission(actor, "student:sensitive_read"):
                raise MasterDataSensitiveAccessError(
                    "Sensitive student detail requires student:sensitive_read permission"
                )

            payload.update(self._full_student_detail(row))
            payload["contacts"] = self._contact_repository.list_primary_contacts(person_id=int(row["person_id"]))
            payload["addresses"] = self._address_repository.list_primary_addresses(person_id=int(row["person_id"]))

        return payload

    def create_student(self, *, command: dict, actor: dict) -> dict:
        normalized = dict(command)
        student_code = str(normalized.get("student_code", "")).strip()
        if not student_code:
            raise MasterDataValidationError("student_code is required")

        if self._student_repository.get_student_by_code(student_code):
            raise MasterDataConflictError(
                "Student code already exists",
                details={"student_code": student_code},
            )

        with self._transaction_scope() as conn:
            person = self._person_service.create_person(payload=normalized, conn=conn)
            student = self._student_repository.create_student(
                person_id=int(person["person_id"]),
                student_code=student_code,
                program_id=normalized.get("program_id"),
                cohort=normalized.get("cohort"),
                entry_year=normalized.get("entry_year"),
                student_status=str(normalized.get("student_status") or "ACTIVE"),
                conn=conn,
            )

            self._persist_contacts(
                person_id=int(person["person_id"]),
                contacts=normalized.get("contacts"),
                conn=conn,
            )
            self._persist_addresses(
                person_id=int(person["person_id"]),
                addresses=normalized.get("addresses"),
                conn=conn,
            )
            account = self._account_provisioning_service.ensure_person_account(
                person_id=int(person["person_id"]),
                username=student_code,
                role_code="STUDENT",
                actor_user_id=int(actor["user_id"]) if actor.get("user_id") is not None else None,
                conn=conn,
            )

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="student",
                    action="create",
                    entity_id=student.get("student_id"),
                    actor_user_id=int(actor.get("user_id", 0)) if actor.get("user_id") is not None else None,
                    payload={"student_code": student.get("student_code")},
                )
            )

        created = self._student_repository.get_student_by_id(int(student["student_id"]))
        if created is None:
            raise MasterDataNotFoundError(
                "Created student not found",
                details={"student_id": int(student["student_id"])},
            )

        result = self._safe_student_item(created)
        result["account"] = account
        return result

    def update_student(self, *, student_id: int, command: dict, actor: dict) -> dict:
        existing = self._student_repository.get_student_by_id(student_id)
        if existing is None:
            raise MasterDataNotFoundError("Student not found", details={"student_id": student_id})

        normalized = dict(command)
        student_update_keys = {"student_code", "program_id", "cohort", "entry_year", "student_status"}
        person_update_keys = {"full_name", "date_of_birth", "gender_code", "national_id", "person_status"}

        next_student_code = normalized.get("student_code")
        if next_student_code:
            conflict = self._student_repository.get_student_by_code(str(next_student_code))
            if conflict and int(conflict["student_id"]) != int(student_id):
                raise MasterDataConflictError(
                    "Student code already exists",
                    details={"student_code": str(next_student_code).strip()},
                )

        person_payload = self._strip_none({key: normalized[key] for key in person_update_keys if key in normalized})
        student_payload = self._strip_none({key: normalized[key] for key in student_update_keys if key in normalized})

        with self._transaction_scope() as conn:
            if person_payload:
                self._person_service.update_person(
                    person_id=int(existing["person_id"]),
                    payload=person_payload,
                    conn=conn,
                )

            if student_payload:
                updated = self._student_repository.update_student(
                    student_id=student_id,
                    payload=student_payload,
                    conn=conn,
                )
                if updated is None:
                    raise MasterDataNotFoundError("Student not found", details={"student_id": student_id})

            if "contacts" in normalized:
                self._persist_contacts(
                    person_id=int(existing["person_id"]),
                    contacts=normalized.get("contacts"),
                    conn=conn,
                )

            if "addresses" in normalized:
                self._persist_addresses(
                    person_id=int(existing["person_id"]),
                    addresses=normalized.get("addresses"),
                    conn=conn,
                )

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="student",
                    action="update",
                    entity_id=student_id,
                    actor_user_id=int(actor.get("user_id", 0)) if actor.get("user_id") is not None else None,
                    payload={},
                )
            )

        updated_row = self._student_repository.get_student_by_id(student_id)
        if updated_row is None:
            raise MasterDataNotFoundError("Student not found", details={"student_id": student_id})
        return self._safe_student_item(updated_row)

    def deactivate_student(self, *, student_id: int, reason: str, actor: dict) -> dict:
        _ = reason
        with self._transaction_scope() as conn:
            row = self._student_repository.deactivate_student(student_id=student_id, conn=conn)
            if row is None:
                raise MasterDataNotFoundError("Student not found", details={"student_id": student_id})

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="student",
                    action="deactivate",
                    entity_id=student_id,
                    actor_user_id=int(actor.get("user_id", 0)) if actor.get("user_id") is not None else None,
                    payload={"reason": reason},
                )
            )
        return {
            "success": True,
            "entity_id": int(student_id),
            "message": "Student deactivated",
            "code": "student_deactivated",
            "details": {"student_id": int(student_id)},
        }


def build_student_service() -> StudentService:
    """FastAPI dependency factory for student service."""

    return StudentService()
