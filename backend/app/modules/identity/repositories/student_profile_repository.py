"""Identity student profile repository for import and identity workflows."""

from __future__ import annotations

from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class StudentProfileRepository:
    """Repository for identity.student_profile."""

    def get_student_by_code(self, student_code: str) -> dict | None:
        query = """
        SELECT
            student_id,
            person_id,
            student_code,
            program_id,
            cohort,
            entry_year,
            student_status
        FROM identity.student_profile
        WHERE lower(student_code) = lower(%s)
        LIMIT 1
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (student_code.strip(),))
                return cur.fetchone()

    def create_student_profile(
        self,
        *,
        person_id: int,
        student_code: str,
        program_id: int | None,
        cohort: str | None,
        entry_year: int | None,
        student_status: str,
    ) -> int:
        query = """
        INSERT INTO identity.student_profile (
            person_id,
            student_code,
            program_id,
            cohort,
            entry_year,
            student_status,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, now())
        RETURNING student_id
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        person_id,
                        student_code.strip(),
                        program_id,
                        cohort.strip() if cohort else None,
                        entry_year,
                        student_status.strip().upper(),
                    ),
                )
                row = cur.fetchone()
            conn.commit()

        if row is None:
            raise RuntimeError("Failed to create student profile")

        return int(row["student_id"])
