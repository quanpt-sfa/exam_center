"""Repository for assessment.exam operations."""

from __future__ import annotations

from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class ExamRepository:
    """SQL operations for assessment.exam lifecycle."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def list_exams(
        self,
        *,
        query_text: str | None,
        status: str | None,
        class_section_id: int | None,
        assessment_type_id: int | None,
        offset: int,
        limit: int,
        conn: Connection | object | None = None,
    ) -> tuple[list[dict], int]:
        where_clauses = ["1=1"]
        values: list[object] = []

        if query_text:
            like_value = f"%{query_text.strip()}%"
            where_clauses.append(
                "(" 
                "lower(e.exam_code) LIKE lower(%s) OR "
                "lower(e.exam_name) LIKE lower(%s) OR "
                "lower(cs.class_code) LIKE lower(%s)"
                ")"
            )
            values.extend([like_value, like_value, like_value])

        if status:
            where_clauses.append("e.exam_status = %s")
            values.append(status.strip().upper())

        if class_section_id is not None:
            where_clauses.append("e.class_section_id = %s")
            values.append(int(class_section_id))

        if assessment_type_id is not None:
            where_clauses.append("e.assessment_type_id = %s")
            values.append(int(assessment_type_id))

        where_sql = " AND ".join(where_clauses)

        list_query = f"""
        SELECT
            e.exam_id,
            e.class_section_id,
            e.assessment_type_id,
            e.exam_code,
            e.exam_name,
            e.description,
            e.exam_status,
            e.created_by,
            e.created_at,
            e.updated_at,
            cs.class_code,
            cs.class_name,
            at.type_code AS assessment_type_code,
            at.type_name AS assessment_type_name,
            at.is_active AS assessment_type_active
        FROM assessment.exam e
        LEFT JOIN academic.class_section cs
          ON cs.class_section_id = e.class_section_id
        JOIN assessment.assessment_type at
          ON at.assessment_type_id = e.assessment_type_id
        WHERE {where_sql}
        ORDER BY e.exam_id DESC
        OFFSET %s
        LIMIT %s
        """

        count_query = f"""
        SELECT count(*) AS total
        FROM assessment.exam e
        LEFT JOIN academic.class_section cs
          ON cs.class_section_id = e.class_section_id
        JOIN assessment.assessment_type at
          ON at.assessment_type_id = e.assessment_type_id
        WHERE {where_sql}
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(count_query, tuple(values))
                count_row = cur.fetchone()
                total = int(count_row["total"] if count_row else 0)

                cur.execute(list_query, tuple([*values, int(offset), int(limit)]))
                rows = cur.fetchall()

        return rows, total

    def get_exam_by_id(self, exam_id: int, conn: Connection | object | None = None) -> dict | None:
        query = """
        SELECT
            e.exam_id,
            e.class_section_id,
            e.assessment_type_id,
            e.exam_code,
            e.exam_name,
            e.description,
            e.exam_status,
            e.created_by,
            e.created_at,
            e.updated_at,
            cs.class_code,
            cs.class_name,
            at.type_code AS assessment_type_code,
            at.type_name AS assessment_type_name,
            at.is_active AS assessment_type_active
        FROM assessment.exam e
        LEFT JOIN academic.class_section cs
          ON cs.class_section_id = e.class_section_id
        JOIN assessment.assessment_type at
          ON at.assessment_type_id = e.assessment_type_id
        WHERE e.exam_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_id),))
                return cur.fetchone()

    def get_exam_by_code(self, exam_code: str, conn: Connection | object | None = None) -> dict | None:
        query = """
        SELECT
            exam_id,
            class_section_id,
            assessment_type_id,
            exam_code,
            exam_name,
            description,
            exam_status,
            created_by,
            created_at,
            updated_at
        FROM assessment.exam
        WHERE lower(exam_code) = lower(%s)
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (exam_code.strip(),))
                return cur.fetchone()

    def class_section_exists(self, class_section_id: int, conn: Connection | object | None = None) -> bool:
        query = """
        SELECT 1
        FROM academic.class_section
        WHERE class_section_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor() as cur:
                cur.execute(query, (int(class_section_id),))
                return cur.fetchone() is not None

    def assessment_type_exists(
        self,
        assessment_type_id: int,
        *,
        require_active: bool,
        conn: Connection | object | None = None,
    ) -> bool:
        query = """
        SELECT 1
        FROM assessment.assessment_type
        WHERE assessment_type_id = %s
          AND (%s = false OR is_active = true)
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor() as cur:
                cur.execute(query, (int(assessment_type_id), bool(require_active)))
                return cur.fetchone() is not None

    def create_exam(
        self,
        *,
        class_section_id: int | None,
        assessment_type_id: int,
        exam_code: str,
        exam_name: str,
        description: str | None,
        exam_status: str,
        created_by: int,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        INSERT INTO assessment.exam (
            class_section_id,
            assessment_type_id,
            exam_code,
            exam_name,
            description,
            exam_status,
            created_by,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, now(), NULL)
        RETURNING
            exam_id,
            class_section_id,
            assessment_type_id,
            exam_code,
            exam_name,
            description,
            exam_status,
            created_by,
            created_at,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(class_section_id) if class_section_id is not None else None,
                        int(assessment_type_id),
                        exam_code.strip().upper(),
                        exam_name.strip(),
                        description,
                        exam_status.strip().upper(),
                        int(created_by),
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to create assessment.exam")
        return row

    def update_exam(self, *, exam_id: int, payload: dict, conn: Connection | object | None = None) -> dict | None:
        allowed = {
            "class_section_id": "class_section_id = %s",
            "assessment_type_id": "assessment_type_id = %s",
            "exam_code": "exam_code = %s",
            "exam_name": "exam_name = %s",
            "description": "description = %s",
            "exam_status": "exam_status = %s",
        }

        updates: list[str] = []
        values: list[object] = []

        for key, clause in allowed.items():
            if key not in payload:
                continue

            value = payload[key]
            if key in {"exam_code", "exam_status"} and value is not None:
                value = str(value).strip().upper()
            elif key == "exam_name" and value is not None:
                value = str(value).strip()
            elif key in {"class_section_id", "assessment_type_id"} and value is not None:
                value = int(value)

            updates.append(clause)
            values.append(value)

        if not updates:
            return self.get_exam_by_id(int(exam_id), conn=conn)

        values.append(int(exam_id))

        query = f"""
        UPDATE assessment.exam
        SET
            {", ".join(updates)},
            updated_at = now()
        WHERE exam_id = %s
        RETURNING
            exam_id,
            class_section_id,
            assessment_type_id,
            exam_code,
            exam_name,
            description,
            exam_status,
            created_by,
            created_at,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, tuple(values))
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        return row

    def archive_exam(self, *, exam_id: int, conn: Connection | object | None = None) -> dict | None:
        query = """
        UPDATE assessment.exam
        SET
            exam_status = 'ARCHIVED',
            updated_at = now()
        WHERE exam_id = %s
        RETURNING
            exam_id,
            exam_code,
            exam_status,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_id),))
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        return row
