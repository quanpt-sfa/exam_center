"""Identity person repository for import and identity workflows."""

from __future__ import annotations

from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class PersonRepository:
    """Repository for create/read operations on identity.person."""

    def create_person(self, full_name: str, person_status: str = "ACTIVE") -> int:
        query = """
        INSERT INTO identity.person (
            full_name,
            person_status,
            created_at
        )
        VALUES (%s, %s, now())
        RETURNING person_id
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (full_name.strip(), person_status.strip().upper()))
                row = cur.fetchone()
            conn.commit()

        if row is None:
            raise RuntimeError("Failed to create person record")

        return int(row["person_id"])
