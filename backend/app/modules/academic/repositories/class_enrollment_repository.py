"""Academic enrollment repository for import commit workflows."""

from __future__ import annotations

from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class ClassEnrollmentRepository:
    """Repository for academic.class_enrollment."""

    def create_enrollment(
        self,
        *,
        class_section_id: int,
        student_id: int,
        enrollment_status: str,
        note: str | None,
    ) -> int:
        query = """
        INSERT INTO academic.class_enrollment (
            class_section_id,
            student_id,
            enrollment_status,
            note,
            enrolled_at
        )
        VALUES (%s, %s, %s, %s, now())
        ON CONFLICT (class_section_id, student_id)
        DO UPDATE
        SET
            enrollment_status = EXCLUDED.enrollment_status,
            note = EXCLUDED.note
        RETURNING enrollment_id
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        class_section_id,
                        student_id,
                        enrollment_status.strip().upper(),
                        note.strip() if note else None,
                    ),
                )
                row = cur.fetchone()
            conn.commit()

        if row is None:
            raise RuntimeError("Failed to create enrollment record")

        return int(row["enrollment_id"])
