"""Repository for assessment.question_grading_profile operations."""

from __future__ import annotations

from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.infrastructure.database.connection import open_connection


class QuestionGradingProfileRepository:
    """SQL operations for question grading profile configuration."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def list_profiles(
        self,
        *,
        exam_version_id: int | None,
        question_template_id: int | None,
        status: str | None,
        input_source: str | None,
        offset: int,
        limit: int,
        conn: Connection | object | None = None,
    ) -> tuple[list[dict], int]:
        where_clauses = ["1=1"]
        values: list[object] = []

        if exam_version_id is not None:
            where_clauses.append("qgp.exam_version_id = %s")
            values.append(int(exam_version_id))

        if question_template_id is not None:
            where_clauses.append("qgp.question_template_id = %s")
            values.append(int(question_template_id))

        if status:
            where_clauses.append("qgp.status = %s")
            values.append(status.strip().upper())

        if input_source:
            where_clauses.append("qgp.input_source = %s")
            values.append(input_source.strip().upper())

        where_sql = " AND ".join(where_clauses)

        list_query = f"""
        SELECT
            qgp.question_grading_profile_id,
            qgp.question_template_id,
            qgp.exam_version_id,
            qgp.input_source,
            qgp.answer_language,
            qgp.requires_capture,
            qgp.required_capture_type,
            qgp.capture_profile_code,
            qgp.grading_engine_code,
            qgp.comparison_method,
            qgp.timeout_seconds,
            qgp.max_score,
            qgp.status,
            qgp.created_at,
            qgp.updated_at
        FROM assessment.v_question_grading_profile_summary qgp
        WHERE {where_sql}
        ORDER BY qgp.question_grading_profile_id DESC
        OFFSET %s
        LIMIT %s
        """

        count_query = f"""
        SELECT count(*) AS total
        FROM assessment.v_question_grading_profile_summary qgp
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

    def get_profile_summary_by_id(
        self,
        question_grading_profile_id: int,
        conn: Connection | object | None = None,
    ) -> dict | None:
        query = """
        SELECT
            question_grading_profile_id,
            question_template_id,
            exam_version_id,
            input_source,
            answer_language,
            requires_capture,
            required_capture_type,
            capture_profile_code,
            grading_engine_code,
            comparison_method,
            timeout_seconds,
            max_score,
            status,
            created_at,
            updated_at
        FROM assessment.v_question_grading_profile_summary
        WHERE question_grading_profile_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(question_grading_profile_id),))
                return cur.fetchone()

    def get_profile_by_id(
        self,
        question_grading_profile_id: int,
        conn: Connection | object | None = None,
    ) -> dict | None:
        query = """
        SELECT
            question_grading_profile_id,
            question_template_id,
            exam_version_id,
            input_source,
            answer_language,
            requires_capture,
            required_capture_type,
            capture_profile_id,
            grading_engine_id,
            comparison_method,
            timeout_seconds,
            max_score,
            status,
            metadata_json,
            created_at,
            updated_at
        FROM assessment.question_grading_profile
        WHERE question_grading_profile_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(question_grading_profile_id),))
                return cur.fetchone()

    def get_existing_profile_for_question(
        self,
        *,
        question_template_id: int,
        exam_version_id: int | None,
        conn: Connection | object | None = None,
    ) -> dict | None:
        if exam_version_id is None:
            query = """
            SELECT
                question_grading_profile_id,
                question_template_id,
                exam_version_id
            FROM assessment.question_grading_profile
            WHERE question_template_id = %s
              AND exam_version_id IS NULL
            LIMIT 1
            """
            params = (int(question_template_id),)
        else:
            query = """
            SELECT
                question_grading_profile_id,
                question_template_id,
                exam_version_id
            FROM assessment.question_grading_profile
            WHERE question_template_id = %s
              AND exam_version_id = %s
            LIMIT 1
            """
            params = (int(question_template_id), int(exam_version_id))

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, params)
                return cur.fetchone()

    def create_profile(
        self,
        *,
        question_template_id: int,
        exam_version_id: int | None,
        input_source: str,
        answer_language: str,
        requires_capture: bool,
        required_capture_type: str | None,
        capture_profile_id: int | None,
        grading_engine_id: int,
        comparison_method: str,
        timeout_seconds: int | None,
        max_score: object | None,
        status: str,
        metadata_json: dict | None,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        INSERT INTO assessment.question_grading_profile (
            question_template_id,
            exam_version_id,
            input_source,
            answer_language,
            requires_capture,
            required_capture_type,
            capture_profile_id,
            grading_engine_id,
            comparison_method,
            timeout_seconds,
            max_score,
            status,
            metadata_json,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), NULL)
        RETURNING
            question_grading_profile_id,
            question_template_id,
            exam_version_id,
            input_source,
            answer_language,
            requires_capture,
            required_capture_type,
            capture_profile_id,
            grading_engine_id,
            comparison_method,
            timeout_seconds,
            max_score,
            status,
            metadata_json,
            created_at,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(question_template_id),
                        int(exam_version_id) if exam_version_id is not None else None,
                        input_source.strip().upper(),
                        answer_language.strip().upper(),
                        bool(requires_capture),
                        required_capture_type.strip().upper() if required_capture_type else None,
                        int(capture_profile_id) if capture_profile_id is not None else None,
                        int(grading_engine_id),
                        comparison_method.strip().upper(),
                        int(timeout_seconds) if timeout_seconds else None,
                        max_score,
                        status.strip().upper(),
                        Jsonb(metadata_json or {}),
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to create assessment.question_grading_profile")
        return row

    def update_profile(
        self,
        *,
        question_grading_profile_id: int,
        payload: dict,
        conn: Connection | object | None = None,
    ) -> dict | None:
        allowed = {
            "input_source": "input_source = %s",
            "answer_language": "answer_language = %s",
            "requires_capture": "requires_capture = %s",
            "required_capture_type": "required_capture_type = %s",
            "capture_profile_id": "capture_profile_id = %s",
            "grading_engine_id": "grading_engine_id = %s",
            "comparison_method": "comparison_method = %s",
            "timeout_seconds": "timeout_seconds = %s",
            "max_score": "max_score = %s",
            "status": "status = %s",
            "metadata_json": "metadata_json = %s",
        }

        updates: list[str] = []
        values: list[object] = []

        for key, clause in allowed.items():
            if key not in payload:
                continue

            value = payload[key]
            if key == "metadata_json":
                value = Jsonb(value or {})
            if key in {
                "input_source",
                "answer_language",
                "required_capture_type",
                "comparison_method",
                "status",
            } and value is not None:
                value = str(value).strip().upper()

            updates.append(clause)
            values.append(value)

        if not updates:
            return self.get_profile_by_id(int(question_grading_profile_id), conn=conn)

        values.append(int(question_grading_profile_id))
        query = f"""
        UPDATE assessment.question_grading_profile
        SET
            {", ".join(updates)},
            updated_at = now()
        WHERE question_grading_profile_id = %s
        RETURNING
            question_grading_profile_id,
            question_template_id,
            exam_version_id,
            input_source,
            answer_language,
            requires_capture,
            required_capture_type,
            capture_profile_id,
            grading_engine_id,
            comparison_method,
            timeout_seconds,
            max_score,
            status,
            metadata_json,
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

    def question_template_exists(
        self,
        question_template_id: int,
        conn: Connection | object | None = None,
    ) -> bool:
        query = """
        SELECT EXISTS (
            SELECT 1
            FROM assessment.question_template
            WHERE question_template_id = %s
        ) AS exists_flag
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(question_template_id),))
                row = cur.fetchone()

        return bool(row and row.get("exists_flag"))

    def exam_version_exists(
        self,
        exam_version_id: int,
        conn: Connection | object | None = None,
    ) -> bool:
        query = """
        SELECT EXISTS (
            SELECT 1
            FROM assessment.exam_version
            WHERE exam_version_id = %s
        ) AS exists_flag
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_version_id),))
                row = cur.fetchone()

        return bool(row and row.get("exists_flag"))
