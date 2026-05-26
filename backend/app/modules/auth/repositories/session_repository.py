"""Repository for persisted refresh session lifecycle."""

from __future__ import annotations

from datetime import datetime

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.infrastructure.database.connection import open_connection


class SessionRepository:
    """Data access for identity.user_session."""

    def create_session(
        self,
        *,
        user_id: int,
        refresh_jti: str,
        refresh_token_hash: str,
        expires_at: datetime,
        user_agent: str | None,
        ip_address: str | None,
    ) -> dict:
        query = """
        INSERT INTO identity.user_session (
            user_id,
            refresh_jti,
            refresh_token_hash,
            issued_at,
            expires_at,
            user_agent,
            ip_address,
            created_at
        )
        VALUES (%s, %s, %s, now(), %s, %s, %s, now())
        RETURNING
            session_id,
            user_id,
            refresh_jti,
            refresh_token_hash,
            issued_at,
            expires_at,
            revoked_at,
            revoke_reason,
            revoked_by_user_id,
            revoke_actor_role,
            revoke_context_json,
            replaced_by_session_id,
            user_agent,
            ip_address,
            created_at,
            updated_at
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        user_id,
                        refresh_jti,
                        refresh_token_hash,
                        expires_at,
                        user_agent,
                        ip_address,
                    ),
                )
                row = cur.fetchone()
            conn.commit()

        if row is None:
            raise RuntimeError("Failed to create refresh session")
        return row

    def get_session_by_jti(self, *, refresh_jti: str, for_update: bool = False) -> dict | None:
        lock_clause = "FOR UPDATE" if for_update else ""
        query = f"""
        SELECT
            session_id,
            user_id,
            refresh_jti,
            refresh_token_hash,
            issued_at,
            expires_at,
            revoked_at,
            revoke_reason,
            revoked_by_user_id,
            revoke_actor_role,
            revoke_context_json,
            replaced_by_session_id,
            user_agent,
            ip_address,
            created_at,
            updated_at
        FROM identity.user_session
        WHERE refresh_jti = %s
        {lock_clause}
        LIMIT 1
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (refresh_jti,))
                return cur.fetchone()

    def get_active_session_by_user_id(self, *, user_id: int, for_update: bool = False) -> dict | None:
        lock_clause = "FOR UPDATE" if for_update else ""
        query = f"""
        SELECT
            session_id,
            user_id,
            refresh_jti,
            refresh_token_hash,
            issued_at,
            expires_at,
            revoked_at,
            revoke_reason,
            revoked_by_user_id,
            revoke_actor_role,
            revoke_context_json,
            replaced_by_session_id,
            user_agent,
            ip_address,
            created_at,
            updated_at
        FROM identity.user_session
        WHERE user_id = %s
          AND revoked_at IS NULL
          AND expires_at > now()
        ORDER BY issued_at DESC
        {lock_clause}
        LIMIT 1
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (user_id,))
                return cur.fetchone()

    def revoke_session(
        self,
        *,
        session_id: int,
        revoke_reason: str,
        replaced_by_session_id: int | None = None,
    ) -> dict | None:
        query = """
        UPDATE identity.user_session
        SET
            revoked_at = COALESCE(revoked_at, now()),
            revoke_reason = COALESCE(revoke_reason, %s),
            replaced_by_session_id = COALESCE(replaced_by_session_id, %s),
            updated_at = now()
        WHERE session_id = %s
        RETURNING
            session_id,
            user_id,
            refresh_jti,
            refresh_token_hash,
            issued_at,
            expires_at,
            revoked_at,
            revoke_reason,
            revoked_by_user_id,
            revoke_actor_role,
            revoke_context_json,
            replaced_by_session_id,
            user_agent,
            ip_address,
            created_at,
            updated_at
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (revoke_reason, replaced_by_session_id, session_id))
                row = cur.fetchone()
            conn.commit()

        return row

    def revoke_active_session_for_user(
        self,
        *,
        user_id: int,
        revoked_by_user_id: int | None,
        revoke_actor_role: str,
        revoke_reason: str,
        revoke_context_json: dict | None,
    ) -> bool:
        query = """
        WITH target AS (
            SELECT session_id
            FROM identity.user_session
            WHERE user_id = %s
              AND revoked_at IS NULL
              AND expires_at > now()
            ORDER BY issued_at DESC, session_id DESC
            LIMIT 1
            FOR UPDATE
        )
        UPDATE identity.user_session AS session
        SET
            revoked_at = now(),
            revoke_reason = %s,
            revoked_by_user_id = %s,
            revoke_actor_role = %s,
            revoke_context_json = %s,
            updated_at = now()
        FROM target
        WHERE session.session_id = target.session_id
        RETURNING session.session_id
        """

        context_value = Jsonb(revoke_context_json) if revoke_context_json is not None else None

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(user_id),
                        revoke_reason,
                        int(revoked_by_user_id) if revoked_by_user_id is not None else None,
                        str(revoke_actor_role).strip().upper(),
                        context_value,
                    ),
                )
                row = cur.fetchone()
            conn.commit()

        return row is not None
