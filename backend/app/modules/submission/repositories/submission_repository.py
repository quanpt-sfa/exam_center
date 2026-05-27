"""Repository layer for submission autosave and seal APIs."""

from __future__ import annotations

from datetime import datetime

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.infrastructure.database.connection import open_connection


_DELIVERY_VALID_PROCTOR_ASSIGNMENT_STATUSES = ("ASSIGNED", "CONFIRMED")


class SubmissionRepository:
    """SQL-only data access for submission runtime."""

    def is_proctor_assigned_to_room(self, *, exam_sitting_room_id: int, proctor_user_id: int) -> bool:
        query = """
        SELECT EXISTS (
            SELECT 1
            FROM delivery.proctor_assignment pa
            WHERE pa.exam_sitting_room_id = %s
              AND pa.proctor_user_id = %s
              AND pa.status = ANY(%s)
            LIMIT 1
        ) AS exists_flag
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(exam_sitting_room_id),
                        int(proctor_user_id),
                        list(_DELIVERY_VALID_PROCTOR_ASSIGNMENT_STATUSES),
                    ),
                )
                row = cur.fetchone()
        return bool(row and row.get("exists_flag"))

    def get_submission_by_id(self, submission_id: int) -> dict | None:
        query = """
        SELECT
            es.exam_submission_id,
            es.exam_session_id,
            es.generated_exam_instance_id,
            es.submission_status,
            es.opened_at,
            es.first_saved_at,
            es.last_saved_at,
            es.submitted_at,
            es.sealed_at,
            es.seal_reason,
            ea.student_id,
            sess.session_status,
            sess.deadline_at,
            room.exam_sitting_room_id,
            room.room_status
        FROM submission.exam_submission es
        JOIN delivery.exam_session sess
            ON sess.exam_session_id = es.exam_session_id
        JOIN delivery.exam_assignment ea
            ON ea.exam_assignment_id = sess.exam_assignment_id
        LEFT JOIN delivery.exam_station_assignment esa
            ON esa.exam_assignment_id = ea.exam_assignment_id
        LEFT JOIN delivery.exam_sitting_room room
            ON room.exam_sitting_room_id = esa.exam_sitting_room_id
        WHERE es.exam_submission_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (submission_id,))
                return cur.fetchone()

    def get_submission_runtime_policy_context(self, submission_id: int) -> dict | None:
        return self.get_submission_by_id(int(submission_id))

        def get_submission_runtime_contract_context(self, submission_id: int) -> dict | None:
                query = """
                SELECT
                        es.exam_submission_id,
                        es.exam_session_id,
                        es.generated_exam_instance_id,
                        es.submission_status,
                        es.opened_at,
                        es.first_saved_at,
                        es.last_saved_at,
                        es.submitted_at,
                        es.sealed_at,
                        es.seal_reason,
                        ea.student_id,
                        sess.session_status,
                        sess.deadline_at,
                        room.exam_sitting_room_id,
                        room.room_status,
                        gei.exam_version_id,
                        profile.exam_version_delivery_profile_id,
                        profile.delivery_mode,
                        profile.work_mode,
                        profile.primary_answer_source,
                        profile.requires_capture AS delivery_requires_capture,
                        profile.capture_timing,
                        profile.form_autosave_enabled,
                        profile.database_work_mode,
                        profile.status AS delivery_profile_status,
                        binding.session_device_binding_id,
                        binding.station_id AS active_station_id,
                        binding.device_id AS active_device_id,
                        binding.binding_status AS active_binding_status
                FROM submission.exam_submission es
                JOIN delivery.exam_session sess
                    ON sess.exam_session_id = es.exam_session_id
                JOIN delivery.exam_assignment ea
                    ON ea.exam_assignment_id = sess.exam_assignment_id
                LEFT JOIN delivery.exam_station_assignment esa
                    ON esa.exam_assignment_id = ea.exam_assignment_id
                LEFT JOIN delivery.exam_sitting_room room
                    ON room.exam_sitting_room_id = esa.exam_sitting_room_id
                LEFT JOIN delivery.generated_exam_instance gei
                    ON gei.generated_exam_instance_id = es.generated_exam_instance_id
                LEFT JOIN assessment.exam_version_delivery_profile profile
                    ON profile.exam_version_id = gei.exam_version_id
                LEFT JOIN LATERAL (
                        SELECT
                                sdb.session_device_binding_id,
                                sdb.station_id,
                                sdb.device_id,
                                sdb.binding_status
                        FROM delivery.exam_session_device_binding sdb
                        WHERE sdb.exam_session_id = es.exam_session_id
                            AND sdb.binding_status = 'ACTIVE'
                        ORDER BY sdb.session_device_binding_id DESC
                        LIMIT 1
                ) binding ON TRUE
                WHERE es.exam_submission_id = %s
                LIMIT 1
                """
                with open_connection() as conn:
                        with conn.cursor(row_factory=dict_row) as cur:
                                cur.execute(query, (int(submission_id),))
                                return cur.fetchone()

    def lock_submission_runtime_policy_context(self, submission_id: int) -> dict | None:
        query = """
        SELECT
            es.exam_submission_id,
            es.exam_session_id,
            es.generated_exam_instance_id,
            es.submission_status,
            es.opened_at,
            es.first_saved_at,
            es.last_saved_at,
            es.submitted_at,
            es.sealed_at,
            es.seal_reason,
            ea.student_id,
            sess.session_status,
            sess.deadline_at,
            room.exam_sitting_room_id,
            room.room_status
        FROM submission.exam_submission es
        JOIN delivery.exam_session sess
            ON sess.exam_session_id = es.exam_session_id
        JOIN delivery.exam_assignment ea
            ON ea.exam_assignment_id = sess.exam_assignment_id
        LEFT JOIN delivery.exam_station_assignment esa
            ON esa.exam_assignment_id = ea.exam_assignment_id
        LEFT JOIN delivery.exam_sitting_room room
            ON room.exam_sitting_room_id = esa.exam_sitting_room_id
        WHERE es.exam_submission_id = %s
        FOR UPDATE OF es, sess
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(submission_id),))
                return cur.fetchone()

    def get_student_id_by_user_id(self, user_id: int) -> int | None:
        query = """
        SELECT sp.student_id
        FROM identity.app_user u
        JOIN identity.student_profile sp
            ON sp.person_id = u.person_id
        WHERE u.user_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (user_id,))
                row = cur.fetchone()
        if row is None:
            return None
        return int(row["student_id"])

    def get_seal_by_submission_id(self, submission_id: int) -> dict | None:
        query = """
        SELECT
            submission_seal_id,
            exam_submission_id,
            seal_idempotency_key,
            seal_status,
            seal_reason,
            sealed_at,
            sealed_by,
            answer_count,
            submission_hash
        FROM submission.submission_seal
        WHERE exam_submission_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (submission_id,))
                return cur.fetchone()

    def get_batch_by_idempotency(self, *, submission_id: int, idempotency_key: str) -> dict | None:
        query = """
        SELECT
            answer_save_batch_id,
            exam_submission_id,
            idempotency_key,
            client_sequence_no,
            client_saved_at,
            server_received_at,
            device_id,
            station_id,
            batch_status,
            accepted_item_count,
            rejected_item_count
        FROM submission.answer_save_batch
        WHERE exam_submission_id = %s
          AND idempotency_key = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (submission_id, idempotency_key))
                return cur.fetchone()

    def create_answer_save_batch(
        self,
        *,
        submission_id: int,
        idempotency_key: str,
        client_sequence_no: int | None,
        client_saved_at: datetime | None,
        device_id: int | None,
        station_id: int | None,
        batch_status: str,
        accepted_item_count: int,
        rejected_item_count: int,
        metadata_json: dict | None,
    ) -> dict:
        query = """
        INSERT INTO submission.answer_save_batch (
            exam_submission_id,
            idempotency_key,
            client_sequence_no,
            client_saved_at,
            server_received_at,
            device_id,
            station_id,
            batch_status,
            accepted_item_count,
            rejected_item_count,
            metadata_json
        )
        VALUES (%s, %s, %s, %s, now(), %s, %s, %s, %s, %s, %s)
        RETURNING
            answer_save_batch_id,
            exam_submission_id,
            idempotency_key,
            client_sequence_no,
            client_saved_at,
            server_received_at,
            device_id,
            station_id,
            batch_status,
            accepted_item_count,
            rejected_item_count
        """
        payload = Jsonb(metadata_json) if metadata_json is not None else None
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        submission_id,
                        idempotency_key,
                        client_sequence_no,
                        client_saved_at,
                        device_id,
                        station_id,
                        batch_status,
                        accepted_item_count,
                        rejected_item_count,
                        payload,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to create answer save batch")
        return row

    def update_answer_save_batch(
        self,
        *,
        answer_save_batch_id: int,
        batch_status: str,
        accepted_item_count: int,
        rejected_item_count: int,
    ) -> dict | None:
        query = """
        UPDATE submission.answer_save_batch
        SET
            batch_status = %s,
            accepted_item_count = %s,
            rejected_item_count = %s
        WHERE answer_save_batch_id = %s
        RETURNING
            answer_save_batch_id,
            exam_submission_id,
            idempotency_key,
            client_sequence_no,
            client_saved_at,
            server_received_at,
            device_id,
            station_id,
            batch_status,
            accepted_item_count,
            rejected_item_count
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        batch_status,
                        accepted_item_count,
                        rejected_item_count,
                        answer_save_batch_id,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        return row

    def create_answer_save_item(
        self,
        *,
        answer_save_batch_id: int,
        generated_exam_question_id: int,
        answer_state_id: int | None,
        client_version: int | None,
        server_version: int | None,
        answer_hash: str | None,
        answer_length: int | None,
        item_status: str,
        error_code: str | None,
        error_message: str | None,
    ) -> dict:
        query = """
        INSERT INTO submission.answer_save_item (
            answer_save_batch_id,
            generated_exam_question_id,
            answer_state_id,
            client_version,
            server_version,
            answer_hash,
            answer_length,
            item_status,
            saved_at,
            error_code,
            error_message
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now(), %s, %s)
        RETURNING
            answer_save_item_id,
            answer_save_batch_id,
            generated_exam_question_id,
            answer_state_id,
            client_version,
            server_version,
            answer_hash,
            answer_length,
            item_status,
            saved_at,
            error_code,
            error_message
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        answer_save_batch_id,
                        generated_exam_question_id,
                        answer_state_id,
                        client_version,
                        server_version,
                        answer_hash,
                        answer_length,
                        item_status,
                        error_code,
                        error_message,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to create answer save item")
        return row

    def list_answer_save_items(self, *, answer_save_batch_id: int) -> list[dict]:
        query = """
        SELECT
            answer_save_item_id,
            answer_save_batch_id,
            generated_exam_question_id,
            answer_state_id,
            client_version,
            server_version,
            answer_hash,
            answer_length,
            item_status,
            saved_at,
            error_code,
            error_message
        FROM submission.answer_save_item
        WHERE answer_save_batch_id = %s
        ORDER BY answer_save_item_id
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (answer_save_batch_id,))
                return cur.fetchall()

    def upsert_answer_state(
        self,
        *,
        submission_id: int,
        generated_exam_question_id: int,
        answer_type: str,
        answer_text: str | None,
        answer_payload_json: dict | None,
        answer_hash: str | None,
        answer_length: int | None,
        client_version: int,
        client_saved_at: datetime | None,
        device_id: int | None,
        station_id: int | None,
        metadata_json: dict | None,
    ) -> dict:
        query = """
        INSERT INTO submission.answer_state (
            exam_submission_id,
            generated_exam_question_id,
            answer_type,
            answer_text,
            answer_payload_json,
            answer_hash,
            answer_length,
            client_version,
            server_version,
            client_saved_at,
            last_saved_at,
            last_saved_by_device_id,
            last_saved_by_station_id,
            answer_status,
            metadata_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, %s, now(), %s, %s, 'DRAFT', %s)
        ON CONFLICT (exam_submission_id, generated_exam_question_id)
        DO UPDATE SET
            answer_type = excluded.answer_type,
            answer_text = excluded.answer_text,
            answer_payload_json = excluded.answer_payload_json,
            answer_hash = excluded.answer_hash,
            answer_length = excluded.answer_length,
            client_version = excluded.client_version,
            server_version = submission.answer_state.server_version + 1,
            client_saved_at = excluded.client_saved_at,
            last_saved_at = now(),
            last_saved_by_device_id = excluded.last_saved_by_device_id,
            last_saved_by_station_id = excluded.last_saved_by_station_id,
            answer_status = 'DRAFT',
            metadata_json = excluded.metadata_json
        RETURNING
            answer_state_id,
            exam_submission_id,
            generated_exam_question_id,
            answer_type,
            answer_text,
            answer_payload_json,
            answer_hash,
            answer_length,
            client_version,
            server_version,
            client_saved_at,
            last_saved_at,
            answer_status
        """
        answer_payload = Jsonb(answer_payload_json) if answer_payload_json is not None else None
        metadata_payload = Jsonb(metadata_json) if metadata_json is not None else None

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        submission_id,
                        generated_exam_question_id,
                        answer_type,
                        answer_text,
                        answer_payload,
                        answer_hash,
                        answer_length,
                        client_version,
                        client_saved_at,
                        device_id,
                        station_id,
                        metadata_payload,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to upsert answer state")
        return row

    def list_answer_state(self, submission_id: int) -> list[dict]:
        query = """
        SELECT
            ast.answer_state_id,
            ast.exam_submission_id,
            ast.generated_exam_question_id,
            coalesce(geq.display_question_order, geq.question_order) AS question_order,
            ast.answer_type,
            ast.answer_text,
            ast.answer_payload_json,
            ast.answer_hash,
            ast.answer_length,
            ast.client_version,
            ast.server_version,
            ast.client_saved_at,
            ast.last_saved_at,
            ast.answer_status
        FROM submission.answer_state ast
        LEFT JOIN delivery.generated_exam_question geq
            ON geq.generated_exam_question_id = ast.generated_exam_question_id
        WHERE ast.exam_submission_id = %s
        ORDER BY coalesce(geq.display_question_order, geq.question_order) NULLS LAST, ast.generated_exam_question_id
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (submission_id,))
                return cur.fetchall()

    def list_submission_question_ids(self, submission_id: int) -> list[int]:
        query = """
        SELECT geq.generated_exam_question_id
        FROM submission.exam_submission es
        JOIN delivery.generated_exam_question geq
          ON geq.generated_exam_instance_id = es.generated_exam_instance_id
        WHERE es.exam_submission_id = %s
        ORDER BY coalesce(geq.display_question_order, geq.question_order), geq.generated_exam_question_id
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(submission_id),))
                rows = cur.fetchall()
        return [int(row["generated_exam_question_id"]) for row in rows]

    def get_max_server_revision(self, submission_id: int) -> int:
        query = """
        SELECT coalesce(max(server_version), 0) AS max_revision
        FROM submission.answer_state
        WHERE exam_submission_id = %s
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (submission_id,))
                row = cur.fetchone()
        if row is None:
            return 0
        return int(row["max_revision"])

    def get_answer_state_count(self, submission_id: int) -> int:
        query = """
        SELECT count(*)::bigint AS total
        FROM submission.answer_state
        WHERE exam_submission_id = %s
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (submission_id,))
                row = cur.fetchone()
        if row is None:
            return 0
        return int(row["total"])

    def update_submission_after_autosave(self, submission_id: int) -> None:
        query = """
        UPDATE submission.exam_submission
        SET
            first_saved_at = coalesce(first_saved_at, now()),
            last_saved_at = now(),
            submission_status = CASE
                WHEN submission_status = 'DRAFT' THEN 'IN_PROGRESS'
                ELSE submission_status
            END,
            updated_at = now()
        WHERE exam_submission_id = %s
        """
        with open_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (submission_id,))
            conn.commit()

    def create_submission_seal(
        self,
        *,
        submission_id: int,
        seal_idempotency_key: str,
        seal_status: str,
        seal_reason: str,
        sealed_by: int | None,
        answer_count: int,
        submission_hash: str | None,
        metadata_json: dict | None,
    ) -> dict:
        query = """
        INSERT INTO submission.submission_seal (
            exam_submission_id,
            seal_idempotency_key,
            seal_status,
            seal_reason,
            sealed_at,
            sealed_by,
            server_time_at_seal,
            answer_count,
            submission_hash,
            metadata_json
        )
        VALUES (%s, %s, %s, %s, now(), %s, now(), %s, %s, %s)
        RETURNING
            submission_seal_id,
            exam_submission_id,
            seal_idempotency_key,
            seal_status,
            seal_reason,
            sealed_at,
            sealed_by,
            answer_count,
            submission_hash
        """
        payload = Jsonb(metadata_json) if metadata_json is not None else None
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        submission_id,
                        seal_idempotency_key,
                        seal_status,
                        seal_reason,
                        sealed_by,
                        answer_count,
                        submission_hash,
                        payload,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to create submission seal")
        return row

    def create_sealed_answers_from_state(self, *, submission_id: int, submission_seal_id: int) -> int:
        query = """
        INSERT INTO submission.sealed_answer (
            submission_seal_id,
            exam_submission_id,
            generated_exam_question_id,
            answer_state_id,
            answer_type,
            answer_text,
            answer_payload_json,
            answer_hash,
            answer_length,
            sealed_at,
            metadata_json
        )
        SELECT
            %s AS submission_seal_id,
            ast.exam_submission_id,
            ast.generated_exam_question_id,
            ast.answer_state_id,
            ast.answer_type,
            ast.answer_text,
            ast.answer_payload_json,
            ast.answer_hash,
            ast.answer_length,
            now(),
            ast.metadata_json
        FROM submission.answer_state ast
        WHERE ast.exam_submission_id = %s
        ON CONFLICT (exam_submission_id, generated_exam_question_id)
        DO NOTHING
        RETURNING sealed_answer_id
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (submission_seal_id, submission_id))
                rows = cur.fetchall()
            conn.commit()
        return len(rows)

    def update_submission_after_seal(
        self,
        *,
        submission_id: int,
        submission_status: str,
        seal_reason: str,
    ) -> None:
        query = """
        UPDATE submission.exam_submission
        SET
            submission_status = %s,
            submitted_at = coalesce(submitted_at, now()),
            sealed_at = coalesce(sealed_at, now()),
            seal_reason = %s,
            updated_at = now()
        WHERE exam_submission_id = %s
        """
        with open_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (submission_status, seal_reason, submission_id))
            conn.commit()

    def insert_submission_history(
        self,
        *,
        exam_submission_id: int,
        exam_session_id: int | None,
        actor_user_id: int | None,
        actor_role: str,
        action_type: str,
        from_status: str | None,
        to_status: str,
        reason_code: str | None,
        note: str | None,
        context_json: dict | None,
        idempotency_key: str | None,
    ) -> dict:
        query = """
        INSERT INTO submission.submission_history (
            exam_submission_id,
            exam_session_id,
            actor_user_id,
            actor_role,
            action_type,
            from_status,
            to_status,
            reason_code,
            note,
            context_json,
            idempotency_key
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING
            submission_history_id,
            exam_submission_id,
            exam_session_id,
            actor_user_id,
            actor_role,
            action_type,
            from_status,
            to_status,
            reason_code,
            note,
            context_json,
            idempotency_key,
            changed_at
        """
        payload = Jsonb(context_json) if context_json is not None else None
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(exam_submission_id),
                        int(exam_session_id) if exam_session_id is not None else None,
                        int(actor_user_id) if actor_user_id is not None else None,
                        str(actor_role).strip().upper(),
                        str(action_type).strip().upper(),
                        str(from_status).strip().upper() if from_status is not None else None,
                        str(to_status).strip().upper(),
                        str(reason_code).strip().upper() if reason_code is not None else None,
                        note,
                        payload,
                        idempotency_key,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to create submission history row")
        return row

    def get_seal_summary(self, submission_id: int) -> dict | None:
        query = """
        SELECT
            ss.submission_seal_id,
            ss.exam_submission_id,
            es.submission_status,
            ss.seal_status,
            ss.seal_reason,
            ss.sealed_at,
            ss.answer_count,
            ss.submission_hash,
            coalesce(sa.sealed_answer_count, 0) AS sealed_answer_count
        FROM submission.submission_seal ss
        JOIN submission.exam_submission es
            ON es.exam_submission_id = ss.exam_submission_id
        LEFT JOIN (
            SELECT
                exam_submission_id,
                count(*)::bigint AS sealed_answer_count
            FROM submission.sealed_answer
            GROUP BY exam_submission_id
        ) sa
            ON sa.exam_submission_id = ss.exam_submission_id
        WHERE ss.exam_submission_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (submission_id,))
                return cur.fetchone()

    def get_submission_dispatch_context(self, submission_id: int) -> dict | None:
        query = """
        SELECT
            es.exam_submission_id,
            es.generated_exam_instance_id,
            es.submission_status,
            ss.submission_seal_id,
            ss.seal_status,
            gei.exam_version_id,
            coalesce(sa.sealed_answer_count, 0) AS sealed_answer_count
        FROM submission.exam_submission es
        LEFT JOIN submission.submission_seal ss
            ON ss.exam_submission_id = es.exam_submission_id
        LEFT JOIN delivery.generated_exam_instance gei
            ON gei.generated_exam_instance_id = es.generated_exam_instance_id
        LEFT JOIN (
            SELECT
                exam_submission_id,
                count(*)::bigint AS sealed_answer_count
            FROM submission.sealed_answer
            GROUP BY exam_submission_id
        ) sa
            ON sa.exam_submission_id = es.exam_submission_id
        WHERE es.exam_submission_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (submission_id,))
                return cur.fetchone()

    def get_submission_processing_context(self, submission_id: int) -> dict | None:
        """Return read-only post-seal processing context keyed by submission."""

        return self.get_submission_dispatch_context(int(submission_id))

    def get_exam_version_delivery_profile(self, exam_version_id: int) -> dict | None:
        query = """
        SELECT
            exam_version_delivery_profile_id,
            exam_version_id,
            delivery_mode,
            work_mode,
            primary_answer_source,
            requires_capture,
            capture_timing,
            default_capture_profile_id,
            default_grading_engine_id,
            allow_mixed_question_sources,
            form_autosave_enabled,
            database_work_mode,
            status,
            metadata_json,
            created_at,
            updated_at
        FROM assessment.exam_version_delivery_profile
        WHERE exam_version_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (exam_version_id,))
                return cur.fetchone()

    def count_active_question_grading_profiles(self, exam_version_id: int) -> int:
        query = """
        SELECT count(*)::bigint AS total
        FROM assessment.question_grading_profile
        WHERE exam_version_id = %s
          AND status IN ('ACTIVE', 'DRAFT')
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (exam_version_id,))
                row = cur.fetchone()
        if row is None:
            return 0
        return int(row["total"])

    def get_dispatch_grading_profile_summary(self, exam_version_id: int) -> dict | None:
        query = """
        SELECT
            question_grading_profile_id,
            input_source,
            answer_language,
            requires_capture,
            required_capture_type,
            capture_profile_code,
            grading_engine_code,
            comparison_method
        FROM assessment.v_question_grading_profile_summary
        WHERE exam_version_id = %s
          AND status IN ('ACTIVE', 'DRAFT')
        ORDER BY question_grading_profile_id
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (exam_version_id,))
                return cur.fetchone()

    def list_submission_question_dispatch_requirements(self, submission_id: int) -> list[dict]:
        query = """
        SELECT
            geq.generated_exam_question_id,
            geq.question_order,
            geq.question_template_id,
            geq.question_type,
            geq.rendered_question_payload_json,
            qgp.question_grading_profile_id,
            qgp.input_source,
            qgp.answer_language,
            qgp.requires_capture,
            qgp.required_capture_type,
            qgp.capture_profile_id,
            cp.profile_code AS capture_profile_code,
            qgp.comparison_method,
            ge.engine_code AS grading_engine_code,
            sa.sealed_answer_id,
            sa.answer_type AS sealed_answer_type,
            sa.answer_text AS sealed_answer_text,
            sa.answer_payload_json AS sealed_answer_payload_json
        FROM submission.exam_submission es
        JOIN delivery.generated_exam_instance gei
          ON gei.generated_exam_instance_id = es.generated_exam_instance_id
        JOIN delivery.generated_exam_question geq
          ON geq.generated_exam_instance_id = gei.generated_exam_instance_id
        LEFT JOIN LATERAL (
            SELECT
                profile.question_grading_profile_id,
                profile.input_source,
                profile.answer_language,
                profile.requires_capture,
                profile.required_capture_type,
                profile.capture_profile_id,
                profile.comparison_method,
                profile.grading_engine_id
            FROM assessment.question_grading_profile profile
            WHERE profile.question_template_id = geq.question_template_id
              AND profile.status IN ('ACTIVE', 'DRAFT')
              AND (
                profile.exam_version_id = gei.exam_version_id
                OR profile.exam_version_id IS NULL
              )
            ORDER BY
                CASE WHEN profile.exam_version_id = gei.exam_version_id THEN 0 ELSE 1 END,
                profile.question_grading_profile_id DESC
            LIMIT 1
        ) qgp ON TRUE
        LEFT JOIN capture.capture_profile cp
          ON cp.capture_profile_id = qgp.capture_profile_id
        LEFT JOIN grading.grading_engine ge
          ON ge.grading_engine_id = qgp.grading_engine_id
        LEFT JOIN submission.sealed_answer sa
          ON sa.exam_submission_id = es.exam_submission_id
         AND sa.generated_exam_question_id = geq.generated_exam_question_id
        WHERE es.exam_submission_id = %s
        ORDER BY geq.question_order, geq.generated_exam_question_id
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(submission_id),))
                return cur.fetchall()

    def has_active_capture_required_profile_config(self, exam_version_id: int) -> bool:
        query = """
        SELECT EXISTS (
            SELECT 1
            FROM assessment.v_question_grading_profile_summary
            WHERE exam_version_id = %s
              AND status IN ('ACTIVE', 'DRAFT')
              AND requires_capture = true
              AND capture_profile_code IS NOT NULL
            LIMIT 1
        ) AS exists_flag
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (exam_version_id,))
                row = cur.fetchone()
        return bool(row and row.get("exists_flag"))

    def get_submission_question_detail(self, *, submission_id: int, generated_exam_question_id: int) -> dict | None:
        query = """
        SELECT
            geq.generated_exam_question_id,
            geq.question_type,
            geq.rendered_question_payload_json
        FROM submission.exam_submission es
        JOIN delivery.generated_exam_question geq
          ON geq.generated_exam_instance_id = es.generated_exam_instance_id
        WHERE es.exam_submission_id = %s
          AND geq.generated_exam_question_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (submission_id, generated_exam_question_id))
                return cur.fetchone()

    def get_generated_option_selection_detail(
        self,
        *,
        submission_id: int,
        generated_exam_question_id: int,
        generated_exam_option_id: int,
    ) -> dict | None:
        query = """
        SELECT
            geq.generated_exam_question_id,
            geq.question_type,
            geo.generated_exam_option_id,
            geo.original_option_id,
            geo.option_order,
            geo.option_label,
            geo.rendered_option_text
        FROM submission.exam_submission es
        JOIN delivery.generated_exam_question geq
          ON geq.generated_exam_instance_id = es.generated_exam_instance_id
        JOIN delivery.generated_exam_option geo
          ON geo.generated_exam_question_id = geq.generated_exam_question_id
        WHERE es.exam_submission_id = %s
          AND geq.generated_exam_question_id = %s
          AND geo.generated_exam_option_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(submission_id),
                        int(generated_exam_question_id),
                        int(generated_exam_option_id),
                    ),
                )
                return cur.fetchone()

    def get_current_answer_file_asset(
        self,
        *,
        submission_id: int,
        generated_exam_question_id: int,
    ) -> dict | None:
        query = """
        SELECT
            answer_file_asset_id,
            exam_submission_id,
            generated_exam_question_id,
            answer_state_id,
            submission_seal_id,
            sealed_answer_id,
            original_filename,
            stored_filename,
            internal_storage_key,
            mime_type,
            file_size_bytes,
            sha256_hash,
            asset_status,
            uploaded_at,
            uploaded_by,
            superseded_at,
            superseded_by
        FROM submission.answer_file_asset
        WHERE exam_submission_id = %s
          AND generated_exam_question_id = %s
          AND asset_status IN ('ACTIVE', 'SEALED')
        ORDER BY uploaded_at DESC, answer_file_asset_id DESC
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (submission_id, generated_exam_question_id))
                return cur.fetchone()

    def supersede_active_answer_file_assets(
        self,
        *,
        submission_id: int,
        generated_exam_question_id: int,
        superseded_by: int | None,
    ) -> int:
        query = """
        UPDATE submission.answer_file_asset
        SET
            asset_status = 'SUPERSEDED',
            superseded_at = now(),
            superseded_by = %s
        WHERE exam_submission_id = %s
          AND generated_exam_question_id = %s
          AND asset_status = 'ACTIVE'
        """
        with open_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (superseded_by, submission_id, generated_exam_question_id))
                rowcount = cur.rowcount
            conn.commit()
        return int(rowcount)

    def create_answer_file_asset(
        self,
        *,
        submission_id: int,
        generated_exam_question_id: int,
        answer_state_id: int | None,
        original_filename: str,
        stored_filename: str,
        internal_storage_key: str,
        mime_type: str,
        file_size_bytes: int,
        sha256_hash: str,
        uploaded_by: int | None,
        metadata_json: dict | None,
    ) -> dict:
        query = """
        INSERT INTO submission.answer_file_asset (
            exam_submission_id,
            generated_exam_question_id,
            answer_state_id,
            original_filename,
            stored_filename,
            internal_storage_key,
            mime_type,
            file_size_bytes,
            sha256_hash,
            asset_status,
            uploaded_by,
            metadata_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVE', %s, %s)
        RETURNING
            answer_file_asset_id,
            exam_submission_id,
            generated_exam_question_id,
            answer_state_id,
            submission_seal_id,
            sealed_answer_id,
            original_filename,
            stored_filename,
            internal_storage_key,
            mime_type,
            file_size_bytes,
            sha256_hash,
            asset_status,
            uploaded_at,
            uploaded_by,
            superseded_at,
            superseded_by
        """
        payload = Jsonb(metadata_json) if metadata_json is not None else Jsonb({})
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        submission_id,
                        generated_exam_question_id,
                        answer_state_id,
                        original_filename,
                        stored_filename,
                        internal_storage_key,
                        mime_type,
                        file_size_bytes,
                        sha256_hash,
                        uploaded_by,
                        payload,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to create answer file asset")
        return row

    def attach_answer_state_to_file_asset(self, *, answer_file_asset_id: int, answer_state_id: int) -> None:
        query = """
        UPDATE submission.answer_file_asset
        SET answer_state_id = %s
        WHERE answer_file_asset_id = %s
        """
        with open_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (answer_state_id, answer_file_asset_id))
            conn.commit()

    def mark_sealed_file_assets(self, *, submission_id: int, submission_seal_id: int) -> int:
        table_check_query = "SELECT to_regclass('submission.answer_file_asset') AS table_name"
        query = """
        UPDATE submission.answer_file_asset afa
        SET
            asset_status = 'SEALED',
            submission_seal_id = %s,
            sealed_answer_id = sa.sealed_answer_id
        FROM submission.sealed_answer sa
        WHERE sa.exam_submission_id = %s
          AND sa.submission_seal_id = %s
          AND sa.answer_type = 'FILE_REF'
          AND sa.generated_exam_question_id = afa.generated_exam_question_id
          AND afa.exam_submission_id = sa.exam_submission_id
          AND afa.asset_status = 'ACTIVE'
        """
        with open_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(table_check_query)
                table_check = cur.fetchone()
                if table_check is None or table_check[0] is None:
                    return 0
                cur.execute(query, (submission_seal_id, submission_id, submission_seal_id))
                rowcount = cur.rowcount
            conn.commit()
        return int(rowcount)

    def list_submission_question_seal_requirements(self, submission_id: int) -> list[dict]:
        table_check_query = "SELECT to_regclass('submission.answer_file_asset') AS table_name"
        base_query = """
        SELECT
            geq.generated_exam_question_id,
            geq.question_order,
            geq.question_type,
            geq.rendered_question_payload_json,
            qgp.input_source,
            qgp.answer_language,
            qgp.requires_capture,
            qgp.required_capture_type,
            qgp.metadata_json AS grading_profile_metadata_json,
            ast.answer_state_id,
            ast.answer_type,
            ast.answer_text,
            ast.answer_payload_json,
            {file_asset_columns}
        FROM submission.exam_submission es
        JOIN delivery.generated_exam_instance gei
          ON gei.generated_exam_instance_id = es.generated_exam_instance_id
        JOIN delivery.generated_exam_question geq
          ON geq.generated_exam_instance_id = gei.generated_exam_instance_id
        LEFT JOIN LATERAL (
            SELECT
                profile.input_source,
                profile.answer_language,
                profile.requires_capture,
                profile.required_capture_type,
                profile.metadata_json
            FROM assessment.question_grading_profile profile
            WHERE profile.question_template_id = geq.question_template_id
              AND profile.status IN ('ACTIVE', 'DRAFT')
              AND (
                profile.exam_version_id = gei.exam_version_id
                OR profile.exam_version_id IS NULL
              )
            ORDER BY
                CASE WHEN profile.exam_version_id = gei.exam_version_id THEN 0 ELSE 1 END,
                profile.question_grading_profile_id DESC
            LIMIT 1
        ) qgp ON TRUE
        LEFT JOIN submission.answer_state ast
          ON ast.exam_submission_id = es.exam_submission_id
         AND ast.generated_exam_question_id = geq.generated_exam_question_id
        {file_asset_join}
        WHERE es.exam_submission_id = %s
        ORDER BY geq.question_order, geq.generated_exam_question_id
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(table_check_query)
                table_check = cur.fetchone()
                has_file_asset_table = table_check is not None and table_check.get("table_name") is not None
                query = base_query.format(
                    file_asset_columns=(
                        """
            afa.answer_file_asset_id,
            afa.asset_status,
            afa.exam_submission_id AS asset_submission_id,
            afa.generated_exam_question_id AS asset_question_id
                        """.strip()
                        if has_file_asset_table
                        else """
            NULL::bigint AS answer_file_asset_id,
            NULL::varchar AS asset_status,
            NULL::bigint AS asset_submission_id,
            NULL::bigint AS asset_question_id
                        """.strip()
                    ),
                    file_asset_join=(
                        """
        LEFT JOIN submission.answer_file_asset afa
          ON afa.exam_submission_id = es.exam_submission_id
         AND afa.generated_exam_question_id = geq.generated_exam_question_id
         AND afa.asset_status = 'ACTIVE'
                        """.rstrip()
                        if has_file_asset_table
                        else ""
                    ),
                )
                cur.execute(query, (int(submission_id),))
                return cur.fetchall()
