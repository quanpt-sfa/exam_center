"""Identity role data access for auth and RBAC."""

from __future__ import annotations

from contextlib import contextmanager

from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class RoleRepository:
    """Repository for identity.role and identity.user_role."""

    @staticmethod
    @contextmanager
    def _connection_scope(conn=None):
        if conn is not None:
            yield conn
            return

        with open_connection() as db_conn:
            yield db_conn

    def get_active_roles_by_user_id(self, user_id: int, conn=None) -> list[str]:
        query = """
        SELECT r.role_code
        FROM identity.user_role AS ur
        INNER JOIN identity.role AS r
            ON r.role_id = ur.role_id
        WHERE ur.user_id = %s
          AND ur.is_active = true
        ORDER BY r.role_code
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (user_id,))
                rows = cur.fetchall()
                return [str(row["role_code"]) for row in rows]

    def assign_role_to_user(
        self,
        *,
        user_id: int,
        role_code: str,
        assigned_by: int | None = None,
        conn=None,
    ) -> dict | None:
        query = """
        WITH selected_role AS (
            SELECT role_id
            FROM identity.role
            WHERE upper(role_code) = upper(%s)
              AND coalesce(is_active, true) = true
            LIMIT 1
        )
        INSERT INTO identity.user_role (
            user_id,
            role_id,
            assigned_by,
            assigned_at,
            is_active
        )
        SELECT %s, role_id, %s, now(), true
        FROM selected_role
        ON CONFLICT (user_id, role_id)
        DO UPDATE SET
            is_active = true,
            assigned_by = EXCLUDED.assigned_by,
            assigned_at = now()
        RETURNING user_role_id, user_id, role_id, assigned_by, assigned_at, is_active
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        role_code,
                        int(user_id),
                        int(assigned_by) if assigned_by is not None else None,
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()
        return row

    def get_permissions_by_user_id(self, user_id: int) -> list[str]:
        """Return permissions if schema supports them, else empty for now.

        Current migrations expose role tables but no dedicated permission table.
        """

        _ = user_id
        return []
