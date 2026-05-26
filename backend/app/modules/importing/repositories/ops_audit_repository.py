"""Repository for ops command run tracking and command events."""

from __future__ import annotations

from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.infrastructure.database.connection import open_connection


class OpsAuditRepository:
    """Repository for ops.agent_command* tables."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def get_or_create_command(self, command_code: str, conn: Connection | object | None = None) -> int:
        select_query = """
        SELECT agent_command_id
        FROM ops.agent_command
        WHERE command_code = %s
        LIMIT 1
        """
        insert_query = """
        INSERT INTO ops.agent_command (
            command_code,
            description,
            is_active,
            created_at
        )
        VALUES (%s, %s, true, now())
        RETURNING agent_command_id
        """

        inserted = None
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(select_query, (command_code,))
                existing = cur.fetchone()
                if existing is not None:
                    return int(existing["agent_command_id"])

                cur.execute(insert_query, (command_code, command_code))
                inserted = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if inserted is None:
            raise RuntimeError("Failed to create ops.agent_command record")

        return int(inserted["agent_command_id"])

    def create_command_run(
        self,
        *,
        command_code: str,
        actor_user_id: int | None,
        actor_agent: str | None,
        command_text: str,
        conn: Connection | object | None = None,
    ) -> int:
        command_id = self.get_or_create_command(command_code, conn=conn)
        query = """
        INSERT INTO ops.agent_command_run (
            agent_command_id,
            actor_user_id,
            actor_agent,
            command_text,
            run_status,
            started_at
        )
        VALUES (%s, %s, %s, %s, 'RUNNING', now())
        RETURNING agent_command_run_id
        """

        row = None
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (command_id, actor_user_id, actor_agent, command_text))
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to create ops.agent_command_run")

        return int(row["agent_command_run_id"])

    def add_command_event(
        self,
        *,
        run_id: int,
        event_type: str,
        payload: dict | None,
        conn: Connection | object | None = None,
    ) -> None:
        query = """
        INSERT INTO ops.agent_command_event (
            agent_command_run_id,
            event_type,
            event_payload_json,
            created_at
        )
        VALUES (%s, %s, %s, now())
        """

        event_payload = Jsonb(payload) if payload is not None else None
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor() as cur:
                cur.execute(query, (run_id, event_type, event_payload))
            if conn is None:
                db_conn.commit()

    def finish_command_run(self, *, run_id: int, run_status: str, output_json: dict | None) -> None:
        query = """
        UPDATE ops.agent_command_run
        SET
            run_status = %s,
            finished_at = now(),
            output_json = %s
        WHERE agent_command_run_id = %s
        """

        payload = Jsonb(output_json) if output_json is not None else None
        with open_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (run_status, payload, run_id))
            conn.commit()

    def list_command_runs(self, *, limit: int = 50, offset: int = 0) -> list[dict]:
        query = """
        SELECT
            run.agent_command_run_id,
            command.command_code,
            run.actor_user_id,
            run.actor_agent,
            run.command_text,
            run.run_status,
            run.started_at,
            run.finished_at,
            run.output_json
        FROM ops.agent_command_run AS run
        LEFT JOIN ops.agent_command AS command
            ON command.agent_command_id = run.agent_command_id
        ORDER BY run.agent_command_run_id DESC
        LIMIT %s OFFSET %s
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (limit, offset))
                return cur.fetchall()

    def list_command_events(self, *, run_id: int, limit: int = 100, offset: int = 0) -> list[dict]:
        query = """
        SELECT
            agent_command_event_id,
            agent_command_run_id,
            event_type,
            event_payload_json,
            created_at
        FROM ops.agent_command_event
        WHERE agent_command_run_id = %s
        ORDER BY agent_command_event_id DESC
        LIMIT %s OFFSET %s
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (run_id, limit, offset))
                return cur.fetchall()
