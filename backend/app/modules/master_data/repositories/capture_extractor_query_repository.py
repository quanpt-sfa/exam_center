"""Repository for capture.capture_extractor_query configuration operations."""

from __future__ import annotations

from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class CaptureExtractorQueryRepository:
    """SQL operations for capture extractor query configuration."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def list_queries_for_profile(
        self,
        capture_profile_id: int,
        *,
        status: str | None,
        offset: int,
        limit: int,
        conn: Connection | object | None = None,
    ) -> tuple[list[dict], int]:
        where_clauses = ["capture_profile_id = %s"]
        values: list[object] = [int(capture_profile_id)]

        if status:
            where_clauses.append("status = %s")
            values.append(status.strip().upper())

        where_sql = " AND ".join(where_clauses)

        list_query = f"""
        SELECT
            capture_extractor_query_id,
            capture_profile_id,
            query_code,
            query_name,
            extractor_kind,
            query_text,
            output_dataset_name,
            is_required,
            execution_order,
            timeout_seconds,
            normalizer_code,
            status,
            metadata_json,
            created_at,
            updated_at
        FROM capture.capture_extractor_query
        WHERE {where_sql}
        ORDER BY execution_order ASC, capture_extractor_query_id ASC
        OFFSET %s
        LIMIT %s
        """

        count_query = f"""
        SELECT count(*) AS total
        FROM capture.capture_extractor_query
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

    def get_query_by_id(
        self,
        capture_extractor_query_id: int,
        conn: Connection | object | None = None,
    ) -> dict | None:
        query = """
        SELECT
            capture_extractor_query_id,
            capture_profile_id,
            query_code,
            query_name,
            extractor_kind,
            query_text,
            output_dataset_name,
            is_required,
            execution_order,
            timeout_seconds,
            normalizer_code,
            status,
            metadata_json,
            created_at,
            updated_at
        FROM capture.capture_extractor_query
        WHERE capture_extractor_query_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(capture_extractor_query_id),))
                return cur.fetchone()

    def get_query_by_code(
        self,
        capture_profile_id: int,
        query_code: str,
        conn: Connection | object | None = None,
    ) -> dict | None:
        query = """
        SELECT
            capture_extractor_query_id,
            capture_profile_id,
            query_code,
            query_name,
            extractor_kind,
            query_text,
            output_dataset_name,
            is_required,
            execution_order,
            timeout_seconds,
            normalizer_code,
            status,
            metadata_json,
            created_at,
            updated_at
        FROM capture.capture_extractor_query
        WHERE capture_profile_id = %s
          AND lower(query_code) = lower(%s)
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(capture_profile_id), query_code.strip()))
                return cur.fetchone()

    def create_query(
        self,
        *,
        capture_profile_id: int,
        query_code: str,
        query_name: str,
        extractor_kind: str,
        query_text: str | None,
        output_dataset_name: str,
        is_required: bool,
        execution_order: int,
        timeout_seconds: int | None,
        normalizer_code: str | None,
        status: str,
        metadata_json: dict | None,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        INSERT INTO capture.capture_extractor_query (
            capture_profile_id,
            query_code,
            query_name,
            extractor_kind,
            query_text,
            output_dataset_name,
            is_required,
            execution_order,
            timeout_seconds,
            normalizer_code,
            status,
            metadata_json,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), NULL)
        RETURNING
            capture_extractor_query_id,
            capture_profile_id,
            query_code,
            query_name,
            extractor_kind,
            query_text,
            output_dataset_name,
            is_required,
            execution_order,
            timeout_seconds,
            normalizer_code,
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
                        int(capture_profile_id),
                        query_code.strip().upper(),
                        query_name.strip(),
                        extractor_kind.strip().upper(),
                        query_text,
                        output_dataset_name.strip(),
                        bool(is_required),
                        int(execution_order),
                        int(timeout_seconds) if timeout_seconds else None,
                        normalizer_code.strip().upper() if normalizer_code else None,
                        status.strip().upper(),
                        metadata_json or {},
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to create capture.capture_extractor_query")
        return row
