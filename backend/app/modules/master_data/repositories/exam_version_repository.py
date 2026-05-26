"""Repository for assessment.exam_version operations."""

from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal

from psycopg import Connection
from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class ExamVersionRepository:
    """SQL operations for exam version lifecycle and publish checks."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def list_exam_versions(
        self,
        *,
        exam_id: int,
        status: str | None,
        offset: int,
        limit: int,
        conn: Connection | object | None = None,
    ) -> tuple[list[dict], int]:
        where_clauses = ["ev.exam_id = %s"]
        values: list[object] = [int(exam_id)]

        if status:
            where_clauses.append("ev.status = %s")
            values.append(status.strip().upper())

        where_sql = " AND ".join(where_clauses)

        list_query = f"""
        SELECT
            ev.exam_version_id,
            ev.exam_id,
            ev.version_no,
            ev.version_label,
            ev.duration_seconds,
            ev.total_score,
            ev.shuffle_questions,
            ev.shuffle_options,
            ev.randomization_mode,
            ev.status,
            ev.published_at,
            ev.published_by,
            ev.created_at,
            ev.updated_at,
            e.exam_code,
            e.exam_name,
            e.exam_status
        FROM assessment.exam_version ev
        JOIN assessment.exam e
          ON e.exam_id = ev.exam_id
        WHERE {where_sql}
        ORDER BY ev.version_no DESC, ev.exam_version_id DESC
        OFFSET %s
        LIMIT %s
        """

        count_query = f"""
        SELECT count(*) AS total
        FROM assessment.exam_version ev
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

    def get_exam_version_by_id(self, exam_version_id: int, conn: Connection | object | None = None) -> dict | None:
        query = """
        SELECT
            ev.exam_version_id,
            ev.exam_id,
            ev.version_no,
            ev.version_label,
            ev.duration_seconds,
            ev.total_score,
            ev.shuffle_questions,
            ev.shuffle_options,
            ev.randomization_mode,
            ev.status,
            ev.published_at,
            ev.published_by,
            ev.created_at,
            ev.updated_at,
            e.exam_code,
            e.exam_name,
            e.exam_status
        FROM assessment.exam_version ev
        JOIN assessment.exam e
          ON e.exam_id = ev.exam_id
        WHERE ev.exam_version_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_version_id),))
                return cur.fetchone()

    def get_exam_version_by_exam_and_version_no(
        self,
        *,
        exam_id: int,
        version_no: int,
        conn: Connection | object | None = None,
    ) -> dict | None:
        query = """
        SELECT
            exam_version_id,
            exam_id,
            version_no,
            version_label,
            duration_seconds,
            total_score,
            shuffle_questions,
            shuffle_options,
            randomization_mode,
            status,
            published_at,
            published_by,
            created_at,
            updated_at
        FROM assessment.exam_version
        WHERE exam_id = %s
          AND version_no = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_id), int(version_no)))
                return cur.fetchone()

    def get_next_version_no(self, exam_id: int, conn: Connection | object | None = None) -> int:
        query = """
        SELECT coalesce(max(version_no), 0) + 1 AS next_version_no
        FROM assessment.exam_version
        WHERE exam_id = %s
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_id),))
                row = cur.fetchone()

        return int(row["next_version_no"] if row else 1)

    def create_exam_version(
        self,
        *,
        exam_id: int,
        version_no: int,
        version_label: str | None,
        duration_seconds: int,
        total_score: Decimal | float | int,
        shuffle_questions: bool,
        shuffle_options: bool,
        randomization_mode: str,
        status: str,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        INSERT INTO assessment.exam_version (
            exam_id,
            version_no,
            version_label,
            duration_seconds,
            total_score,
            shuffle_questions,
            shuffle_options,
            randomization_mode,
            status,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now(), NULL)
        RETURNING
            exam_version_id,
            exam_id,
            version_no,
            version_label,
            duration_seconds,
            total_score,
            shuffle_questions,
            shuffle_options,
            randomization_mode,
            status,
            published_at,
            published_by,
            created_at,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(exam_id),
                        int(version_no),
                        version_label.strip() if isinstance(version_label, str) and version_label.strip() else None,
                        int(duration_seconds),
                        total_score,
                        bool(shuffle_questions),
                        bool(shuffle_options),
                        randomization_mode.strip().upper(),
                        status.strip().upper(),
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to create assessment.exam_version")
        return row

    def update_exam_version(
        self,
        *,
        exam_version_id: int,
        payload: dict,
        conn: Connection | object | None = None,
    ) -> dict | None:
        allowed = {
            "version_label": "version_label = %s",
            "duration_seconds": "duration_seconds = %s",
            "total_score": "total_score = %s",
            "shuffle_questions": "shuffle_questions = %s",
            "shuffle_options": "shuffle_options = %s",
            "randomization_mode": "randomization_mode = %s",
            "status": "status = %s",
        }

        updates: list[str] = []
        values: list[object] = []

        for key, clause in allowed.items():
            if key not in payload:
                continue

            value = payload[key]
            if key in {"randomization_mode", "status"} and value is not None:
                value = str(value).strip().upper()
            elif key == "version_label" and value is not None:
                value = str(value).strip()
            elif key == "duration_seconds" and value is not None:
                value = int(value)

            updates.append(clause)
            values.append(value)

        if not updates:
            return self.get_exam_version_by_id(int(exam_version_id), conn=conn)

        values.append(int(exam_version_id))

        query = f"""
        UPDATE assessment.exam_version
        SET
            {", ".join(updates)},
            updated_at = now()
        WHERE exam_version_id = %s
        RETURNING
            exam_version_id,
            exam_id,
            version_no,
            version_label,
            duration_seconds,
            total_score,
            shuffle_questions,
            shuffle_options,
            randomization_mode,
            status,
            published_at,
            published_by,
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

    def publish_exam_version(
        self,
        *,
        exam_version_id: int,
        published_by: int,
        conn: Connection | object | None = None,
    ) -> dict | None:
        query = """
        UPDATE assessment.exam_version
        SET
            status = 'PUBLISHED',
            published_at = now(),
            published_by = %s,
            updated_at = now()
        WHERE exam_version_id = %s
        RETURNING
            exam_version_id,
            exam_id,
            version_no,
            version_label,
            duration_seconds,
            total_score,
            shuffle_questions,
            shuffle_options,
            randomization_mode,
            status,
            published_at,
            published_by,
            created_at,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(published_by), int(exam_version_id)))
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        return row

    def retire_exam_version(self, *, exam_version_id: int, conn: Connection | object | None = None) -> dict | None:
        query = """
        UPDATE assessment.exam_version
        SET
            status = 'RETIRED',
            updated_at = now()
        WHERE exam_version_id = %s
        RETURNING
            exam_version_id,
            exam_id,
            version_no,
            version_label,
            duration_seconds,
            total_score,
            shuffle_questions,
            shuffle_options,
            randomization_mode,
            status,
            published_at,
            published_by,
            created_at,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_version_id),))
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        return row

    def has_other_published_version(
        self,
        *,
        exam_id: int,
        excluded_exam_version_id: int,
        conn: Connection | object | None = None,
    ) -> bool:
        query = """
        SELECT EXISTS (
            SELECT 1
            FROM assessment.exam_version
            WHERE exam_id = %s
              AND exam_version_id <> %s
              AND status = 'PUBLISHED'
            LIMIT 1
        ) AS has_conflict
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_id), int(excluded_exam_version_id)))
                row = cur.fetchone()

        return bool(row and row.get("has_conflict"))

    def question_grading_profile_table_exists(self, conn: Connection | object | None = None) -> bool:
        query = "SELECT to_regclass('assessment.question_grading_profile') IS NOT NULL AS exists_flag"

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query)
                row = cur.fetchone()

        return bool(row and row.get("exists_flag"))

    def has_active_question_grading_profile(
        self,
        *,
        exam_version_id: int,
        conn: Connection | object | None = None,
    ) -> bool:
        if not self.question_grading_profile_table_exists(conn=conn):
            return False

        query = """
        SELECT EXISTS (
            SELECT 1
            FROM assessment.question_grading_profile
            WHERE exam_version_id = %s
              AND status IN ('DRAFT', 'ACTIVE')
            LIMIT 1
        ) AS has_profile
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_version_id),))
                row = cur.fetchone()

        return bool(row and row.get("has_profile"))

    def list_active_question_grading_profiles(
        self,
        *,
        exam_version_id: int,
        conn: Connection | object | None = None,
    ) -> list[dict]:
        if not self.question_grading_profile_table_exists(conn=conn):
            return []

        query = """
        SELECT
            qgp.question_grading_profile_id,
            qgp.question_template_id,
            qgp.answer_language,
            qgp.input_source,
            qgp.comparison_method,
            qgp.max_score,
            qgp.metadata_json,
            ge.engine_code AS grading_engine_code
        FROM assessment.question_grading_profile qgp
        LEFT JOIN grading.grading_engine ge
          ON ge.grading_engine_id = qgp.grading_engine_id
        WHERE qgp.exam_version_id = %s
          AND qgp.status IN ('DRAFT', 'ACTIVE')
        ORDER BY qgp.question_grading_profile_id
        """
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_version_id),))
                return cur.fetchall()

    def question_has_active_expected_answer(
        self,
        *,
        question_template_id: int,
        conn: Connection | object | None = None,
    ) -> bool:
        query = """
        SELECT EXISTS (
            SELECT 1
            FROM assessment.reference_solution
            WHERE question_template_id = %s
              AND status IN ('DRAFT', 'ACTIVE')
            LIMIT 1
        ) AS exists_flag
        """
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(question_template_id),))
                row = cur.fetchone()
        return bool(row and row.get("exists_flag"))

    def python_test_case_table_exists(self, conn: Connection | object | None = None) -> bool:
        query = "SELECT to_regclass('assessment.python_test_case') IS NOT NULL AS exists_flag"

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query)
                row = cur.fetchone()

        return bool(row and row.get("exists_flag"))

    def question_has_active_python_test_case(
        self,
        *,
        question_template_id: int,
        conn: Connection | object | None = None,
    ) -> bool:
        if not self.python_test_case_table_exists(conn=conn):
            return False

        query = """
        SELECT EXISTS (
            SELECT 1
            FROM assessment.python_test_case
            WHERE question_template_id = %s
              AND is_active = true
            LIMIT 1
        ) AS exists_flag
        """
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(question_template_id),))
                row = cur.fetchone()
        return bool(row and row.get("exists_flag"))

    def paper_asset_table_exists(self, conn: Connection | object | None = None) -> bool:
        query = "SELECT to_regclass('assessment.exam_version_paper_asset') IS NOT NULL AS exists_flag"

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query)
                row = cur.fetchone()

        return bool(row and row.get("exists_flag"))

    def has_active_visual_paper_asset(
        self,
        *,
        exam_version_id: int,
        conn: Connection | object | None = None,
    ) -> bool:
        if not self.paper_asset_table_exists(conn=conn):
            return False

        query = """
        SELECT EXISTS (
            SELECT 1
            FROM assessment.exam_version_paper_asset
            WHERE exam_version_id = %s
              AND is_active = true
              AND asset_kind IN ('PDF_SOURCE', 'IMAGE_PAGE_SET', 'IMAGE_PAGE')
            LIMIT 1
        ) AS exists_flag
        """
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_version_id),))
                row = cur.fetchone()
        return bool(row and row.get("exists_flag"))
