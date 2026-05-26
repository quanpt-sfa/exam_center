"""Service layer for instructor master-data workflows."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager

from app.infrastructure.database.unit_of_work import database_unit_of_work
from app.modules.master_data.common.audit import MasterDataAuditEvent
from app.modules.master_data.common.audit import MasterDataAuditHook
from app.modules.master_data.common.audit import build_master_data_audit_hook
from app.modules.master_data.common.errors import MasterDataConflictError
from app.modules.master_data.common.errors import MasterDataNotFoundError
from app.modules.master_data.common.errors import MasterDataValidationError
from app.modules.master_data.common.pagination import build_pagination_metadata
from app.modules.master_data.common.pagination import build_pagination_params
from app.modules.master_data.repositories.address_repository import AddressRepository
from app.modules.master_data.repositories.contact_repository import ContactRepository
from app.modules.master_data.repositories.instructor_repository import InstructorRepository
from app.modules.master_data.services.account_provisioning_service import AccountProvisioningService
from app.modules.master_data.services.account_provisioning_service import build_account_provisioning_service
from app.modules.master_data.services.person_service import PersonService


class InstructorService:
    """Coordinates instructor/person/contact persistence with one transaction boundary."""

    def __init__(
        self,
        *,
        instructor_repository: InstructorRepository | None = None,
        person_service: PersonService | None = None,
        contact_repository: ContactRepository | None = None,
        address_repository: AddressRepository | None = None,
        account_provisioning_service: AccountProvisioningService | None = None,
        audit_hook: MasterDataAuditHook | None = None,
        transaction_scope: Callable[[], object] | None = None,
    ) -> None:
        self._instructor_repository = instructor_repository or InstructorRepository()
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
                instructor_repository,
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
    def _safe_instructor_item(row: dict) -> dict:
        return {
            "instructor_id": row.get("instructor_id"),
            "person_id": row.get("person_id"),
            "instructor_code": row.get("instructor_code"),
            "full_name": row.get("full_name"),
            "instructor_status": row.get("instructor_status"),
            "person_status": row.get("person_status"),
            "department_id": row.get("department_id"),
            "department_code": row.get("department_code"),
            "department_name": row.get("department_name"),
            "user_id": row.get("account_user_id"),
            "username": row.get("account_username"),
            "user_status": row.get("account_user_status"),
            "created_at": row.get("instructor_created_at"),
            "updated_at": row.get("instructor_updated_at"),
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

    def list_instructors(self, *, filters: dict | None, pagination: dict | None, actor: dict) -> dict:
        _ = actor
        pagination = pagination or {}
        params = build_pagination_params(
            page=pagination.get("page"),
            page_size=pagination.get("page_size"),
        )

        safe_filters = filters or {}
        rows, total_items = self._instructor_repository.list_instructors(
            query_text=safe_filters.get("query"),
            status=safe_filters.get("status"),
            department_id=safe_filters.get("department_id"),
            offset=params.offset,
            limit=params.limit,
        )

        return {
            "items": [self._safe_instructor_item(row) for row in rows],
            "pagination": build_pagination_metadata(
                page=params.page,
                page_size=params.page_size,
                total=total_items,
            ),
        }

    def get_instructor(self, *, instructor_id: int, actor: dict) -> dict:
        _ = actor
        row = self._instructor_repository.get_instructor_by_id(instructor_id)
        if row is None:
            raise MasterDataNotFoundError("Instructor not found", details={"instructor_id": instructor_id})

        return self._safe_instructor_item(row)

    def create_instructor(self, *, command: dict, actor: dict) -> dict:
        normalized = dict(command)
        instructor_code = str(normalized.get("instructor_code", "")).strip()
        if not instructor_code:
            raise MasterDataValidationError("instructor_code is required")

        if self._instructor_repository.get_instructor_by_code(instructor_code):
            raise MasterDataConflictError(
                "Instructor code already exists",
                details={"instructor_code": instructor_code},
            )

        with self._transaction_scope() as conn:
            person = self._person_service.create_person(payload=normalized, conn=conn)
            instructor = self._instructor_repository.create_instructor(
                person_id=int(person["person_id"]),
                instructor_code=instructor_code,
                department_id=normalized.get("department_id"),
                instructor_status=str(normalized.get("instructor_status") or "ACTIVE"),
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
                username=instructor_code,
                role_code="INSTRUCTOR",
                actor_user_id=int(actor["user_id"]) if actor.get("user_id") is not None else None,
                conn=conn,
            )

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="instructor",
                    action="create",
                    entity_id=instructor.get("instructor_id"),
                    actor_user_id=int(actor.get("user_id", 0)) if actor.get("user_id") is not None else None,
                    payload={"instructor_code": instructor.get("instructor_code")},
                )
            )

        created = self._instructor_repository.get_instructor_by_id(int(instructor["instructor_id"]))
        if created is None:
            raise RuntimeError("created_instructor_not_found")

        result = self._safe_instructor_item(created)
        result["account"] = account
        return result

    def update_instructor(self, *, instructor_id: int, command: dict, actor: dict) -> dict:
        existing = self._instructor_repository.get_instructor_by_id(instructor_id)
        if existing is None:
            raise MasterDataNotFoundError("Instructor not found", details={"instructor_id": instructor_id})

        normalized = dict(command)
        instructor_update_keys = {"instructor_code", "department_id", "instructor_status"}
        person_update_keys = {"full_name", "date_of_birth", "gender_code", "national_id", "person_status"}

        next_instructor_code = normalized.get("instructor_code")
        if next_instructor_code:
            conflict = self._instructor_repository.get_instructor_by_code(str(next_instructor_code))
            if conflict and int(conflict["instructor_id"]) != int(instructor_id):
                raise MasterDataConflictError(
                    "Instructor code already exists",
                    details={"instructor_code": str(next_instructor_code).strip()},
                )

        person_payload = self._strip_none({key: normalized[key] for key in person_update_keys if key in normalized})
        instructor_payload = self._strip_none({key: normalized[key] for key in instructor_update_keys if key in normalized})

        with self._transaction_scope() as conn:
            if person_payload:
                self._person_service.update_person(
                    person_id=int(existing["person_id"]),
                    payload=person_payload,
                    conn=conn,
                )

            if instructor_payload:
                updated = self._instructor_repository.update_instructor(
                    instructor_id=instructor_id,
                    payload=instructor_payload,
                    conn=conn,
                )
                if updated is None:
                    raise MasterDataNotFoundError("Instructor not found", details={"instructor_id": instructor_id})

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
                    entity="instructor",
                    action="update",
                    entity_id=instructor_id,
                    actor_user_id=int(actor.get("user_id", 0)) if actor.get("user_id") is not None else None,
                    payload={},
                )
            )

        updated_row = self._instructor_repository.get_instructor_by_id(instructor_id)
        if updated_row is None:
            raise MasterDataNotFoundError("Instructor not found", details={"instructor_id": instructor_id})
        return self._safe_instructor_item(updated_row)

    def deactivate_instructor(self, *, instructor_id: int, reason: str, actor: dict) -> dict:
        _ = reason
        with self._transaction_scope() as conn:
            row = self._instructor_repository.deactivate_instructor(instructor_id=instructor_id, conn=conn)
            if row is None:
                raise MasterDataNotFoundError("Instructor not found", details={"instructor_id": instructor_id})

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="instructor",
                    action="deactivate",
                    entity_id=instructor_id,
                    actor_user_id=int(actor.get("user_id", 0)) if actor.get("user_id") is not None else None,
                    payload={"reason": reason},
                )
            )

        return {
            "success": True,
            "entity_id": int(instructor_id),
            "message": "Instructor deactivated",
            "code": "instructor_deactivated",
            "details": {"instructor_id": int(instructor_id)},
        }


def build_instructor_service() -> InstructorService:
    """FastAPI dependency factory for instructor service."""

    return InstructorService()
