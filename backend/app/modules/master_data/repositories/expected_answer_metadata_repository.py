"""Repository for safe metadata-level reads from delivery.generated_expected_answer."""

from __future__ import annotations

from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class ExpectedAnswerMetadataRepository:
    """Read-only metadata helper queries for generated expected answers."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def table_exists(self, conn: Connection | object | None = None) -> bool:
        query = "SELECT to_regclass('delivery.generated_expected_answer') IS NOT NULL AS exists_flag"

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query)
                row = cur.fetchone()

        return bool(row and row.get("exists_flag"))

    def count_for_exam_version(
        self,
        exam_version_id: int,
        conn: Connection | object | None = None,
    ) -> int:
        query = """
        SELECT count(*) AS total
        FROM delivery.generated_expected_answer gea
        JOIN delivery.generated_exam_question geq
            ON geq.generated_exam_question_id = gea.generated_exam_question_id
        JOIN delivery.generated_exam_instance gei
            ON gei.generated_exam_instance_id = geq.generated_exam_instance_id
        WHERE gei.exam_version_id = %s
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_version_id),))
                row = cur.fetchone()

        return int(row["total"] if row else 0)

    def count_with_metadata_for_exam_version(
        self,
        exam_version_id: int,
        conn: Connection | object | None = None,
    ) -> int:
        query = """
        SELECT count(*) AS total
        FROM delivery.generated_expected_answer gea
        JOIN delivery.generated_exam_question geq
            ON geq.generated_exam_question_id = gea.generated_exam_question_id
        JOIN delivery.generated_exam_instance gei
            ON gei.generated_exam_instance_id = geq.generated_exam_instance_id
        WHERE gei.exam_version_id = %s
          AND jsonb_typeof(COALESCE(gea.metadata_json, '{}'::jsonb)) = 'object'
          AND gea.metadata_json <> '{}'::jsonb
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_version_id),))
                row = cur.fetchone()

        return int(row["total"] if row else 0)
