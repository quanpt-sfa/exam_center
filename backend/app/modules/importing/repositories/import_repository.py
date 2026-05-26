"""Database repository for importing schema operations."""

from __future__ import annotations

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.infrastructure.database.connection import open_connection


class ImportRepository:
    """Repository for importing.* tables."""

    def list_templates(self) -> list[dict]:
        query = """
        SELECT
            import_template_id,
            template_code,
            template_name,
            schema_version,
            entity_code,
            is_active
        FROM importing.import_template
        WHERE is_active = true
        ORDER BY template_code
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query)
                return cur.fetchall()

    def get_template_by_code(self, template_code: str) -> dict | None:
        query = """
        SELECT
            import_template_id,
            template_code,
            template_name,
            schema_version,
            entity_code,
            is_active
        FROM importing.import_template
        WHERE template_code = %s
          AND is_active = true
        LIMIT 1
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (template_code,))
                return cur.fetchone()

    def create_job(
        self,
        *,
        import_template_id: int,
        template_code: str,
        actor_user_id: int | None,
        actor_agent: str | None,
        agent_command_run_id: int | None,
    ) -> dict:
        query = """
        INSERT INTO importing.import_job (
            import_template_id,
            template_code,
            job_status,
            validation_status,
            commit_status,
            actor_user_id,
            actor_agent,
            agent_command_run_id,
            created_at,
            updated_at
        )
        VALUES (%s, %s, 'CREATED', 'PENDING', 'NOT_COMMITTED', %s, %s, %s, now(), now())
        RETURNING
            import_job_id,
            template_code,
            job_status,
            validation_status,
            commit_status,
            actor_user_id,
            actor_agent,
            agent_command_run_id,
            created_at,
            updated_at
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        import_template_id,
                        template_code,
                        actor_user_id,
                        actor_agent,
                        agent_command_run_id,
                    ),
                )
                row = cur.fetchone()
            conn.commit()

        if row is None:
            raise RuntimeError("Failed to create import job")

        return row

    def get_job(self, job_id: int) -> dict | None:
        query = """
        SELECT
            import_job_id,
            import_template_id,
            template_code,
            job_status,
            validation_status,
            commit_status,
            actor_user_id,
            actor_agent,
            agent_command_run_id,
            created_at,
            updated_at
        FROM importing.import_job
        WHERE import_job_id = %s
        LIMIT 1
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (job_id,))
                return cur.fetchone()

    def update_job_state(
        self,
        *,
        job_id: int,
        job_status: str | None = None,
        validation_status: str | None = None,
        commit_status: str | None = None,
    ) -> None:
        query = """
        UPDATE importing.import_job
        SET
            job_status = coalesce(%s, job_status),
            validation_status = coalesce(%s, validation_status),
            commit_status = coalesce(%s, commit_status),
            updated_at = now()
        WHERE import_job_id = %s
        """

        with open_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (job_status, validation_status, commit_status, job_id))
            conn.commit()

    def create_file_record(
        self,
        *,
        job_id: int,
        original_filename: str,
        storage_ref: str,
        local_dev_path: str,
        file_size_bytes: int,
    ) -> dict:
        query = """
        INSERT INTO importing.import_file (
            import_job_id,
            original_filename,
            storage_ref,
            local_dev_path,
            file_size_bytes,
            uploaded_at
        )
        VALUES (%s, %s, %s, %s, %s, now())
        RETURNING
            import_file_id,
            import_job_id,
            original_filename,
            storage_ref,
            local_dev_path,
            file_size_bytes,
            uploaded_at
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        job_id,
                        original_filename,
                        storage_ref,
                        local_dev_path,
                        file_size_bytes,
                    ),
                )
                row = cur.fetchone()
            conn.commit()

        if row is None:
            raise RuntimeError("Failed to create import file record")

        return row

    def get_latest_file_for_job(self, job_id: int) -> dict | None:
        query = """
        SELECT
            import_file_id,
            import_job_id,
            original_filename,
            storage_ref,
            local_dev_path,
            file_size_bytes,
            uploaded_at
        FROM importing.import_file
        WHERE import_job_id = %s
        ORDER BY uploaded_at DESC, import_file_id DESC
        LIMIT 1
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (job_id,))
                return cur.fetchone()

    def clear_job_staging(self, job_id: int) -> None:
        with open_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM importing.import_row_error WHERE import_job_id = %s", (job_id,))
                cur.execute("DELETE FROM importing.import_entity_link WHERE import_job_id = %s", (job_id,))
                cur.execute("DELETE FROM importing.import_row_staging WHERE import_job_id = %s", (job_id,))
                cur.execute(
                    """
                    DELETE FROM importing.import_sheet
                    WHERE import_file_id IN (
                        SELECT import_file_id
                        FROM importing.import_file
                        WHERE import_job_id = %s
                    )
                    """,
                    (job_id,),
                )
            conn.commit()

    def create_sheet_record(
        self,
        *,
        import_file_id: int,
        sheet_name: str,
        row_count: int,
    ) -> dict:
        query = """
        INSERT INTO importing.import_sheet (
            import_file_id,
            sheet_name,
            row_count,
            parsed_at
        )
        VALUES (%s, %s, %s, now())
        RETURNING
            import_sheet_id,
            import_file_id,
            sheet_name,
            row_count,
            parsed_at
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (import_file_id, sheet_name, row_count))
                row = cur.fetchone()
            conn.commit()

        if row is None:
            raise RuntimeError("Failed to create import sheet record")
        return row

    def insert_staging_row(
        self,
        *,
        job_id: int,
        sheet_id: int | None,
        row_number: int,
        raw_row_json: dict,
    ) -> dict:
        query = """
        INSERT INTO importing.import_row_staging (
            import_job_id,
            import_sheet_id,
            row_number,
            raw_row_json,
            validation_status,
            commit_status,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, 'PENDING', 'NOT_COMMITTED', now(), now())
        RETURNING
            import_row_staging_id,
            import_job_id,
            import_sheet_id,
            row_number,
            raw_row_json,
            normalized_row_json,
            validation_status,
            commit_status
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (job_id, sheet_id, row_number, Jsonb(raw_row_json)))
                row = cur.fetchone()
            conn.commit()

        if row is None:
            raise RuntimeError("Failed to create staging row")

        return row

    def list_staging_rows(
        self,
        *,
        job_id: int,
        validation_status: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict]:
        query = """
        SELECT
            import_row_staging_id,
            import_job_id,
            import_sheet_id,
            row_number,
            raw_row_json,
            normalized_row_json,
            validation_status,
            commit_status,
            created_at,
            updated_at
        FROM importing.import_row_staging
        WHERE import_job_id = %s
          AND (%s IS NULL OR validation_status = %s)
        ORDER BY row_number
        LIMIT coalesce(%s, 5000)
        OFFSET %s
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (job_id, validation_status, validation_status, limit, offset))
                return cur.fetchall()

    def update_staging_row_validation(
        self,
        *,
        row_staging_id: int,
        validation_status: str,
        normalized_row_json: dict | None,
    ) -> None:
        query = """
        UPDATE importing.import_row_staging
        SET
            validation_status = %s,
            normalized_row_json = %s,
            updated_at = now()
        WHERE import_row_staging_id = %s
        """

        normalized = Jsonb(normalized_row_json) if normalized_row_json is not None else None
        with open_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (validation_status, normalized, row_staging_id))
            conn.commit()

    def update_staging_row_commit(
        self,
        *,
        row_staging_id: int,
        commit_status: str,
    ) -> None:
        query = """
        UPDATE importing.import_row_staging
        SET
            commit_status = %s,
            updated_at = now()
        WHERE import_row_staging_id = %s
        """
        with open_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (commit_status, row_staging_id))
            conn.commit()

    def clear_row_errors(self, job_id: int) -> None:
        query = "DELETE FROM importing.import_row_error WHERE import_job_id = %s"
        with open_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (job_id,))
            conn.commit()

    def add_row_error(
        self,
        *,
        job_id: int,
        row_staging_id: int,
        error_code: str,
        error_message: str,
        error_details_json: dict | None,
    ) -> None:
        query = """
        INSERT INTO importing.import_row_error (
            import_job_id,
            import_row_staging_id,
            error_code,
            error_message,
            error_details_json,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, now())
        """

        payload = Jsonb(error_details_json) if error_details_json is not None else None
        with open_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (job_id, row_staging_id, error_code, error_message, payload))
            conn.commit()

    def list_row_errors(self, *, job_id: int, limit: int = 100, offset: int = 0) -> list[dict]:
        query = """
        SELECT
            import_row_error_id,
            import_job_id,
            import_row_staging_id,
            error_code,
            error_message,
            error_details_json,
            created_at
        FROM importing.import_row_error
        WHERE import_job_id = %s
        ORDER BY import_row_error_id
        LIMIT %s OFFSET %s
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (job_id, limit, offset))
                return cur.fetchall()

    def get_row_status_counts(self, job_id: int) -> dict:
        query = """
        SELECT
            count(*)::bigint AS total_rows,
            count(*) FILTER (WHERE validation_status = 'VALID')::bigint AS valid_rows,
            count(*) FILTER (WHERE validation_status = 'INVALID')::bigint AS invalid_rows,
            count(*) FILTER (WHERE validation_status = 'PENDING')::bigint AS pending_rows,
            count(*) FILTER (WHERE commit_status = 'COMMITTED')::bigint AS committed_rows,
            count(*) FILTER (WHERE commit_status = 'FAILED')::bigint AS failed_rows
        FROM importing.import_row_staging
        WHERE import_job_id = %s
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (job_id,))
                row = cur.fetchone()
                return row or {
                    "total_rows": 0,
                    "valid_rows": 0,
                    "invalid_rows": 0,
                    "pending_rows": 0,
                    "committed_rows": 0,
                    "failed_rows": 0,
                }

    def create_commit_record(
        self,
        *,
        job_id: int,
        commit_status: str,
        committed_by: int | None,
        summary_json: dict | None,
        committed_at: bool = False,
    ) -> dict:
        query = """
        INSERT INTO importing.import_commit (
            import_job_id,
            commit_status,
            committed_at,
            committed_by,
            summary_json,
            created_at
        )
        VALUES (
            %s,
            %s,
            CASE WHEN %s THEN now() ELSE NULL END,
            %s,
            %s,
            now()
        )
        RETURNING
            import_commit_id,
            import_job_id,
            commit_status,
            committed_at,
            committed_by,
            summary_json,
            created_at
        """

        payload = Jsonb(summary_json) if summary_json is not None else None
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (job_id, commit_status, committed_at, committed_by, payload))
                row = cur.fetchone()
            conn.commit()

        if row is None:
            raise RuntimeError("Failed to create commit record")

        return row

    def add_entity_link(
        self,
        *,
        job_id: int,
        row_staging_id: int,
        entity_schema: str,
        entity_table: str,
        entity_pk: str,
    ) -> None:
        query = """
        INSERT INTO importing.import_entity_link (
            import_job_id,
            import_row_staging_id,
            entity_schema,
            entity_table,
            entity_pk,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, now())
        """

        with open_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (job_id, row_staging_id, entity_schema, entity_table, entity_pk))
            conn.commit()

    def add_audit_event(
        self,
        *,
        job_id: int | None,
        event_type: str,
        event_payload_json: dict | None,
        actor_user_id: int | None,
        actor_agent: str | None,
    ) -> None:
        query = """
        INSERT INTO importing.import_audit_event (
            import_job_id,
            event_type,
            event_payload_json,
            actor_user_id,
            actor_agent,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, now())
        """

        payload = Jsonb(event_payload_json) if event_payload_json is not None else None
        with open_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (job_id, event_type, payload, actor_user_id, actor_agent))
            conn.commit()

    def list_audit_events(self, *, job_id: int, limit: int = 100, offset: int = 0) -> list[dict]:
        query = """
        SELECT
            import_audit_event_id,
            import_job_id,
            event_type,
            event_payload_json,
            actor_user_id,
            actor_agent,
            created_at
        FROM importing.import_audit_event
        WHERE import_job_id = %s
        ORDER BY import_audit_event_id
        LIMIT %s OFFSET %s
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (job_id, limit, offset))
                return cur.fetchall()
