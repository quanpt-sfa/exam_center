"""Identity user data access for auth flows."""

from __future__ import annotations

from contextlib import contextmanager

from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class UserRepository:
    """Repository for identity.app_user and identity.person reads/writes."""

    @staticmethod
    @contextmanager
    def _connection_scope(conn=None):
        if conn is not None:
            yield conn
            return

        with open_connection() as db_conn:
            yield db_conn

    def list_users(
        self,
        *,
        query_text: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict], int]:
        filters: list[str] = []
        params: list[object] = []

        normalized_query = str(query_text or "").strip()
        if normalized_query:
            filters.append(
                "(lower(u.username) LIKE lower(%s) OR lower(coalesce(u.email_login, '')) LIKE lower(%s) "
                "OR lower(coalesce(p.full_name, '')) LIKE lower(%s))"
            )
            like_value = f"%{normalized_query}%"
            params.extend([like_value, like_value, like_value])

        normalized_status = str(status or "").strip().upper()
        if normalized_status:
            filters.append("u.user_status = %s")
            params.append(normalized_status)

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        count_query = f"""
        SELECT count(*) AS total
        FROM identity.app_user AS u
        LEFT JOIN identity.person AS p
            ON p.person_id = u.person_id
        {where_clause}
        """
        list_query = f"""
        SELECT
            u.user_id,
            u.person_id,
            u.username,
            u.email_login,
            u.user_status,
            u.last_login_at,
            u.created_at,
            u.updated_at,
            p.full_name AS display_name,
            coalesce(
                array_agg(DISTINCT r.role_code) FILTER (WHERE r.role_code IS NOT NULL),
                array[]::varchar[]
            ) AS roles
        FROM identity.app_user AS u
        LEFT JOIN identity.person AS p
            ON p.person_id = u.person_id
        LEFT JOIN identity.user_role AS ur
            ON ur.user_id = u.user_id
           AND ur.is_active = true
        LEFT JOIN identity.role AS r
            ON r.role_id = ur.role_id
        {where_clause}
        GROUP BY
            u.user_id,
            u.person_id,
            u.username,
            u.email_login,
            u.user_status,
            u.last_login_at,
            u.created_at,
            u.updated_at,
            p.full_name
        ORDER BY u.username
        OFFSET %s
        LIMIT %s
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(count_query, tuple(params))
                count_row = cur.fetchone() or {"total": 0}
                cur.execute(list_query, tuple([*params, int(offset), int(limit)]))
                return cur.fetchall(), int(count_row["total"])

    def get_user_by_identifier(self, identifier: str) -> dict | None:
        query = """
        SELECT
            u.user_id,
            u.person_id,
            u.username,
            u.email_login,
            u.password_hash,
            u.user_status,
            p.full_name AS display_name
        FROM identity.app_user AS u
        LEFT JOIN identity.person AS p
            ON p.person_id = u.person_id
        WHERE lower(u.username) = lower(%s)
           OR lower(coalesce(u.email_login, '')) = lower(%s)
        LIMIT 1
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (identifier, identifier))
                return cur.fetchone()

    def get_user_by_id(self, user_id: int) -> dict | None:
        query = """
        SELECT
            u.user_id,
            u.person_id,
            u.username,
            u.email_login,
            u.password_hash,
            u.user_status,
            p.full_name AS display_name
        FROM identity.app_user AS u
        LEFT JOIN identity.person AS p
            ON p.person_id = u.person_id
        WHERE u.user_id = %s
        LIMIT 1
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (user_id,))
                return cur.fetchone()

    def get_user_by_person_id(self, person_id: int, conn=None) -> dict | None:
        query = """
        SELECT
            u.user_id,
            u.person_id,
            u.username,
            u.email_login,
            u.user_status,
            p.full_name AS display_name
        FROM identity.app_user AS u
        LEFT JOIN identity.person AS p
            ON p.person_id = u.person_id
        WHERE u.person_id = %s
        ORDER BY u.user_id
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(person_id),))
                return cur.fetchone()

    def get_user_by_username(self, username: str, conn=None) -> dict | None:
        query = """
        SELECT
            u.user_id,
            u.person_id,
            u.username,
            u.email_login,
            u.user_status,
            p.full_name AS display_name
        FROM identity.app_user AS u
        LEFT JOIN identity.person AS p
            ON p.person_id = u.person_id
        WHERE lower(u.username) = lower(%s)
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (username,))
                return cur.fetchone()

    def create_user_for_person(
        self,
        *,
        person_id: int,
        username: str,
        password_hash: str,
        email_login: str | None = None,
        user_status: str = "ACTIVE",
        conn=None,
    ) -> dict:
        query = """
        INSERT INTO identity.app_user (
            person_id,
            username,
            email_login,
            password_hash,
            user_status,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, now(), NULL)
        RETURNING
            user_id,
            person_id,
            username,
            email_login,
            user_status,
            created_at,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(person_id),
                        username,
                        email_login,
                        password_hash,
                        user_status,
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()
        if row is None:
            raise RuntimeError("Failed to create identity.app_user")
        return row

    def update_last_login(self, user_id: int) -> None:
        query = """
        UPDATE identity.app_user
        SET last_login_at = now(),
            updated_at = now()
        WHERE user_id = %s
        """

        with open_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (user_id,))
            conn.commit()

    def update_password_hash(self, user_id: int, password_hash: str) -> None:
        query = """
        UPDATE identity.app_user
        SET password_hash = %s,
            updated_at = now()
        WHERE user_id = %s
        """

        with open_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (password_hash, user_id))
            conn.commit()
