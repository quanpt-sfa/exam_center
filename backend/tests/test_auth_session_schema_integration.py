from __future__ import annotations

from contextlib import contextmanager
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app.api.v1.auth import build_auth_service
from app.core.security import clear_security_settings_cache
from app.infrastructure.database.connection import open_connection
from app.infrastructure.database.pool import close_pool, initialize_pool
from app.main import app
from app.modules.auth.repositories.session_repository import SessionRepository
from app.modules.auth.services.auth_service import AuthService
from app.modules.auth.services.password_service import PasswordService
from app.modules.auth.services.session_service import SessionService
from app.modules.auth.services.token_service import TokenService


pytestmark = pytest.mark.skipif(
    os.getenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION") != "1",
    reason="Set EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION=1 to run PostgreSQL integration tests",
)


@pytest.fixture(scope="module", autouse=True)
def db_pool():
    initialize_pool()
    yield
    close_pool()


class _AlwaysValidPasswordService(PasswordService):
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        _ = (plain_password, hashed_password)
        return True


class _DbBackedAuthRepository:
    def __init__(self, user_row: dict) -> None:
        self._user_row = dict(user_row)
        self.last_login_updates = 0

    def get_user_by_identifier(self, identifier: str) -> dict | None:
        normalized = identifier.strip().lower()
        usernames = {
            str(self._user_row.get("username") or "").lower(),
            str(self._user_row.get("email_login") or "").lower(),
        }
        if normalized in usernames:
            return dict(self._user_row)
        return None

    def get_user_by_id(self, user_id: int) -> dict | None:
        if int(user_id) == int(self._user_row["user_id"]):
            return dict(self._user_row)
        return None

    def get_roles_by_user_id(self, user_id: int) -> list[str]:
        _ = user_id
        return ["STUDENT"]

    def get_permissions_by_user_id(self, user_id: int) -> list[str]:
        _ = user_id
        return []

    def update_last_login(self, user_id: int) -> None:
        _ = user_id
        self.last_login_updates += 1


@contextmanager
def _seed_auth_user() -> dict:
    suffix = uuid4().hex[:12]
    full_name = f"Auth Session Schema {suffix}"

    with open_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO identity.person (full_name, person_status)
                VALUES (%s, 'ACTIVE')
                RETURNING person_id
                """,
                (full_name,),
            )
            person_id = int(cur.fetchone()["person_id"])

            username = f"auth_schema_{suffix}"
            email_login = f"auth_schema_{suffix}@example.com"
            cur.execute(
                """
                INSERT INTO identity.app_user (person_id, username, email_login, password_hash, user_status)
                VALUES (%s, %s, %s, %s, 'ACTIVE')
                RETURNING user_id
                """,
                (person_id, username, email_login, f"hash_{suffix}"),
            )
            user_id = int(cur.fetchone()["user_id"])
        conn.commit()

    user_row = {
        "user_id": user_id,
        "person_id": person_id,
        "username": username,
        "email_login": email_login,
        "password_hash": f"hash_{suffix}",
        "user_status": "ACTIVE",
        "display_name": full_name,
    }

    try:
        yield user_row
    finally:
        with open_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM identity.user_session WHERE user_id = %s", (user_id,))
                cur.execute("DELETE FROM identity.app_user WHERE user_id = %s", (user_id,))
                cur.execute("DELETE FROM identity.person WHERE person_id = %s", (person_id,))
            conn.commit()


def test_identity_user_session_contains_revoke_audit_columns() -> None:
    query = """
    SELECT column_name
    FROM information_schema.columns
    WHERE table_schema = 'identity'
      AND table_name = 'user_session'
      AND column_name IN ('revoked_by_user_id', 'revoke_actor_role', 'revoke_context_json')
    ORDER BY column_name
    """

    with open_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query)
            rows = cur.fetchall()

    assert [row["column_name"] for row in rows] == [
        "revoke_actor_role",
        "revoke_context_json",
        "revoked_by_user_id",
    ]


def test_get_active_session_by_user_id_does_not_fail_after_migration() -> None:
    with _seed_auth_user() as user_row:
        repository = SessionRepository()

        session = repository.get_active_session_by_user_id(user_id=int(user_row["user_id"]))

        assert session is None


def test_login_endpoint_returns_controlled_response_not_500_after_session_schema_alignment(monkeypatch) -> None:
    monkeypatch.setenv("EXAM_SYS_NEXT_ACCESS_TOKEN_SECRET", "access-test-secret")
    monkeypatch.setenv("EXAM_SYS_NEXT_REFRESH_TOKEN_SECRET", "refresh-test-secret")
    monkeypatch.setenv("EXAM_SYS_NEXT_TOKEN_ALGORITHM", "HS256")
    monkeypatch.setenv("EXAM_SYS_NEXT_ACCESS_TOKEN_EXPIRES_MINUTES", "5")
    monkeypatch.setenv("EXAM_SYS_NEXT_REFRESH_TOKEN_EXPIRES_MINUTES", "60")
    clear_security_settings_cache()

    with _seed_auth_user() as user_row:
        token_service = TokenService()
        session_service = SessionService(repository=SessionRepository(), token_service=token_service)
        auth_service = AuthService(
            repository=_DbBackedAuthRepository(user_row),
            password_service=_AlwaysValidPasswordService(),
            token_service=token_service,
            session_service=session_service,
        )

        app.dependency_overrides[build_auth_service] = lambda: auth_service
        client = TestClient(app)

        try:
            response = client.post(
                "/api/v1/auth/login",
                json={"identifier": user_row["username"], "password": "pw"},
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["error"] is None
        assert payload["data"]["token_type"] == "bearer"

        active_session = SessionRepository().get_active_session_by_user_id(user_id=int(user_row["user_id"]))
        assert active_session is not None
        assert active_session["revoked_by_user_id"] is None
        assert active_session["revoke_actor_role"] is None
        assert active_session["revoke_context_json"] is None