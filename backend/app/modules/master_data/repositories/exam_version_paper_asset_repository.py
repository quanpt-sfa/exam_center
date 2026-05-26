"""Repository for assessment.exam_version_paper_asset operations."""

from __future__ import annotations

from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.infrastructure.database.connection import open_connection


class ExamVersionPaperAssetRepository:
    """SQL data access for exam-version visual paper assets."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def exam_version_belongs_to_exam(
        self,
        *,
        exam_id: int,
        exam_version_id: int,
        conn: Connection | object | None = None,
    ) -> bool:
        query = """
        SELECT EXISTS (
            SELECT 1
            FROM assessment.exam_version ev
            WHERE ev.exam_version_id = %s
              AND ev.exam_id = %s
            LIMIT 1
        ) AS exists_flag
        """
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_version_id), int(exam_id)))
                row = cur.fetchone()
        return bool(row and row.get("exists_flag"))

    def paper_asset_table_exists(self, conn: Connection | object | None = None) -> bool:
        query = "SELECT to_regclass('assessment.exam_version_paper_asset') IS NOT NULL AS exists_flag"
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query)
                row = cur.fetchone()
        return bool(row and row.get("exists_flag"))

    def deactivate_active_source_assets(
        self,
        *,
        exam_version_id: int,
        retired_by: int | None,
        conn: Connection | object | None = None,
    ) -> int:
        query = """
        UPDATE assessment.exam_version_paper_asset
        SET
            is_active = false,
            render_status = 'RETIRED',
            retired_at = now(),
            retired_by = %s
        WHERE exam_version_id = %s
          AND is_active = true
          AND asset_kind IN ('PDF_SOURCE', 'IMAGE_PAGE_SET')
        """
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor() as cur:
                cur.execute(query, (retired_by, int(exam_version_id)))
                updated = cur.rowcount
            if conn is None:
                db_conn.commit()
        return int(updated or 0)

    def create_paper_asset(
        self,
        *,
        exam_version_id: int,
        asset_kind: str,
        original_filename: str,
        stored_filename: str,
        storage_relative_path: str,
        mime_type: str,
        file_size_bytes: int,
        sha256_hash: str,
        page_count: int | None,
        created_by: int | None,
        metadata_json: dict | None,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        INSERT INTO assessment.exam_version_paper_asset (
            exam_version_id,
            asset_kind,
            original_filename,
            stored_filename,
            storage_relative_path,
            mime_type,
            file_size_bytes,
            sha256_hash,
            page_count,
            render_status,
            is_active,
            created_by,
            metadata_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'UPLOADED', true, %s, %s)
        RETURNING
            paper_asset_id,
            exam_version_id,
            asset_kind,
            original_filename,
            stored_filename,
            storage_relative_path,
            mime_type,
            file_size_bytes,
            sha256_hash,
            page_count,
            render_status,
            is_active,
            created_by,
            created_at,
            retired_at,
            retired_by,
            metadata_json
        """
        payload = Jsonb(metadata_json or {})
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(exam_version_id),
                        str(asset_kind).strip().upper(),
                        str(original_filename).strip(),
                        str(stored_filename).strip(),
                        str(storage_relative_path).strip(),
                        str(mime_type).strip().lower(),
                        int(file_size_bytes),
                        str(sha256_hash).strip().lower(),
                        int(page_count) if page_count is not None else None,
                        int(created_by) if created_by is not None else None,
                        payload,
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()
        if row is None:
            raise RuntimeError("Failed to create paper asset metadata")
        return row

    def list_paper_assets_for_exam_version(
        self,
        *,
        exam_id: int,
        exam_version_id: int,
        conn: Connection | object | None = None,
    ) -> list[dict]:
        if not self.paper_asset_table_exists(conn=conn):
            return []

        query = """
        SELECT
            pa.paper_asset_id,
            pa.exam_version_id,
            pa.asset_kind,
            pa.original_filename,
            pa.stored_filename,
            pa.storage_relative_path,
            pa.mime_type,
            pa.file_size_bytes,
            pa.sha256_hash,
            pa.page_count,
            pa.render_status,
            pa.is_active,
            pa.created_by,
            pa.created_at,
            pa.retired_at,
            pa.retired_by,
            pa.metadata_json
        FROM assessment.exam_version_paper_asset pa
        JOIN assessment.exam_version ev
          ON ev.exam_version_id = pa.exam_version_id
        WHERE pa.exam_version_id = %s
          AND ev.exam_id = %s
        ORDER BY pa.created_at DESC, pa.paper_asset_id DESC
        """
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_version_id), int(exam_id)))
                return cur.fetchall()

    def retire_paper_asset(
        self,
        *,
        exam_id: int,
        exam_version_id: int,
        paper_asset_id: int,
        retired_by: int | None,
        retirement_reason: str | None,
        conn: Connection | object | None = None,
    ) -> dict | None:
        query = """
        UPDATE assessment.exam_version_paper_asset pa
        SET
            is_active = false,
            render_status = 'RETIRED',
            retired_at = now(),
            retired_by = %s,
            metadata_json = jsonb_set(
                coalesce(pa.metadata_json, '{}'::jsonb),
                '{retirement_reason}',
                to_jsonb(%s::text),
                true
            )
        FROM assessment.exam_version ev
        WHERE pa.paper_asset_id = %s
          AND pa.exam_version_id = %s
          AND ev.exam_version_id = pa.exam_version_id
          AND ev.exam_id = %s
        RETURNING
            pa.paper_asset_id,
            pa.exam_version_id,
            pa.asset_kind,
            pa.original_filename,
            pa.stored_filename,
            pa.storage_relative_path,
            pa.mime_type,
            pa.file_size_bytes,
            pa.sha256_hash,
            pa.page_count,
            pa.render_status,
            pa.is_active,
            pa.created_by,
            pa.created_at,
            pa.retired_at,
            pa.retired_by,
            pa.metadata_json
        """
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(retired_by) if retired_by is not None else None,
                        retirement_reason,
                        int(paper_asset_id),
                        int(exam_version_id),
                        int(exam_id),
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()
        return row

