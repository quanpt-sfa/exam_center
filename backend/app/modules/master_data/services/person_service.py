"""Service helpers for identity.person domain operations."""

from __future__ import annotations

from app.modules.master_data.repositories.person_repository import PersonRepository


class PersonService:
    """Owns person-level validation and persistence calls."""

    def __init__(self, *, person_repository: PersonRepository | None = None) -> None:
        self._person_repository = person_repository or PersonRepository()

    def create_person(self, *, payload: dict, conn: object | None = None) -> dict:
        full_name = str(payload.get("full_name", "")).strip()
        if not full_name:
            raise ValueError("full_name is required")

        person_status = str(payload.get("person_status") or "ACTIVE").strip().upper()

        return self._person_repository.create_person(
            full_name=full_name,
            date_of_birth=payload.get("date_of_birth"),
            gender_code=payload.get("gender_code"),
            national_id=payload.get("national_id"),
            person_status=person_status,
            conn=conn,
        )

    def update_person(self, *, person_id: int, payload: dict, conn: object | None = None) -> dict | None:
        return self._person_repository.update_person(person_id=person_id, payload=payload, conn=conn)
