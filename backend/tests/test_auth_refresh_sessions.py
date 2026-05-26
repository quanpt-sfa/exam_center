"""Auth refresh-session persistence tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.errors import ApiError
from app.core.security import clear_security_settings_cache
from app.modules.auth.services.auth_service import AuthService
from app.modules.auth.services.password_service import PasswordService
from app.modules.auth.services.session_service import SessionService
from app.modules.auth.services.token_service import TokenService


class InMemoryAuthRepository:
    def __init__(self) -> None:
        self.user_row = {
            "user_id": 10,
            "person_id": 2,
            "username": "tester",
            "email_login": "tester@example.com",
            "password_hash": "hashed",
            "user_status": "ACTIVE",
            "display_name": "Test User",
        }
        self.last_login_updates = 0

    def get_user_by_identifier(self, identifier: str) -> dict | None:
        if identifier.lower() in {"tester", "tester@example.com"}:
            return dict(self.user_row)
        return None

    def get_user_by_id(self, user_id: int) -> dict | None:
        if int(user_id) == int(self.user_row["user_id"]):
            return dict(self.user_row)
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

    def update_password_hash(self, user_id: int, password_hash: str) -> None:
        _ = (user_id, password_hash)


class AlwaysValidPasswordService(PasswordService):
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        _ = (plain_password, hashed_password)
        return True


class InMemorySessionRepository:
    def __init__(self) -> None:
        self._next_session_id = 1
        self.sessions: dict[int, dict] = {}

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
        now = datetime.now(UTC)
        row = {
            "session_id": self._next_session_id,
            "user_id": user_id,
            "refresh_jti": refresh_jti,
            "refresh_token_hash": refresh_token_hash,
            "issued_at": now,
            "expires_at": expires_at,
            "revoked_at": None,
            "revoke_reason": None,
            "revoked_by_user_id": None,
            "revoke_actor_role": None,
            "revoke_context_json": None,
            "replaced_by_session_id": None,
            "user_agent": user_agent,
            "ip_address": ip_address,
            "created_at": now,
            "updated_at": None,
        }
        self.sessions[self._next_session_id] = row
        self._next_session_id += 1
        return dict(row)

    def get_session_by_jti(self, *, refresh_jti: str, for_update: bool = False) -> dict | None:
        _ = for_update
        for row in self.sessions.values():
            if row["refresh_jti"] == refresh_jti:
                return row
        return None

    def get_active_session_by_user_id(self, *, user_id: int, for_update: bool = False) -> dict | None:
        _ = for_update
        now = datetime.now(UTC)
        active = [
            row
            for row in self.sessions.values()
            if int(row["user_id"]) == int(user_id) and row["revoked_at"] is None and row["expires_at"] > now
        ]
        if not active:
            return None
        active.sort(key=lambda item: item["issued_at"], reverse=True)
        return active[0]

    def revoke_session(
        self,
        *,
        session_id: int,
        revoke_reason: str,
        replaced_by_session_id: int | None = None,
    ) -> dict | None:
        row = self.sessions.get(session_id)
        if row is None:
            return None

        if row["revoked_at"] is None:
            row["revoked_at"] = datetime.now(UTC)
        if row["revoke_reason"] is None:
            row["revoke_reason"] = revoke_reason
        if row["replaced_by_session_id"] is None:
            row["replaced_by_session_id"] = replaced_by_session_id
        row["updated_at"] = datetime.now(UTC)
        return dict(row)

    def revoke_active_session_for_user(
        self,
        *,
        user_id: int,
        revoked_by_user_id: int | None,
        revoke_actor_role: str,
        revoke_reason: str,
        revoke_context_json: dict | None,
    ) -> bool:
        row = self.get_active_session_by_user_id(user_id=user_id, for_update=True)
        if row is None:
            return False

        row["revoked_at"] = datetime.now(UTC)
        row["revoke_reason"] = revoke_reason
        row["revoked_by_user_id"] = revoked_by_user_id
        row["revoke_actor_role"] = revoke_actor_role
        row["revoke_context_json"] = dict(revoke_context_json) if revoke_context_json is not None else None
        row["updated_at"] = datetime.now(UTC)
        return True


def _build_auth_service(monkeypatch, *, session_repository: InMemorySessionRepository | None = None) -> tuple[AuthService, InMemoryAuthRepository, InMemorySessionRepository, TokenService]:
    monkeypatch.setenv("EXAM_SYS_NEXT_ACCESS_TOKEN_SECRET", "access-test-secret")
    monkeypatch.setenv("EXAM_SYS_NEXT_REFRESH_TOKEN_SECRET", "refresh-test-secret")
    monkeypatch.setenv("EXAM_SYS_NEXT_TOKEN_ALGORITHM", "HS256")
    monkeypatch.setenv("EXAM_SYS_NEXT_ACCESS_TOKEN_EXPIRES_MINUTES", "5")
    monkeypatch.setenv("EXAM_SYS_NEXT_REFRESH_TOKEN_EXPIRES_MINUTES", "60")
    clear_security_settings_cache()

    auth_repo = InMemoryAuthRepository()
    session_repo = session_repository or InMemorySessionRepository()
    token_service = TokenService()
    session_service = SessionService(repository=session_repo, token_service=token_service)

    service = AuthService(
        repository=auth_repo,
        password_service=AlwaysValidPasswordService(),
        token_service=token_service,
        session_service=session_service,
    )
    return service, auth_repo, session_repo, token_service


def _extract_jti(token_service: TokenService, refresh_token: str) -> str:
    claims = token_service.verify_refresh_token(refresh_token)
    return str(claims["jti"])


def test_login_creates_persisted_refresh_session(monkeypatch) -> None:
    service, auth_repo, session_repo, token_service = _build_auth_service(monkeypatch)

    result = service.login(identifier="tester", password="pw")

    assert auth_repo.last_login_updates == 1
    assert len(session_repo.sessions) == 1
    jti = _extract_jti(token_service, result["refresh_token"])
    stored = session_repo.get_session_by_jti(refresh_jti=jti)
    assert stored is not None
    assert int(stored["user_id"]) == 10


def test_second_login_is_rejected_when_active_session_exists(monkeypatch) -> None:
    service, _auth_repo, _session_repo, _token_service = _build_auth_service(monkeypatch)

    _ = service.login(identifier="tester", password="pw")

    with pytest.raises(ApiError) as exc_info:
        service.login(identifier="tester", password="pw")

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "account_already_logged_in"


def test_refresh_rotates_session(monkeypatch) -> None:
    service, _auth_repo, session_repo, token_service = _build_auth_service(monkeypatch)

    login_result = service.login(identifier="tester", password="pw")
    old_refresh = login_result["refresh_token"]
    old_jti = _extract_jti(token_service, old_refresh)

    refresh_result = service.refresh(old_refresh)
    new_refresh = refresh_result["refresh_token"]
    new_jti = _extract_jti(token_service, new_refresh)

    assert new_refresh != old_refresh
    assert len(session_repo.sessions) == 2

    old_session = session_repo.get_session_by_jti(refresh_jti=old_jti)
    new_session = session_repo.get_session_by_jti(refresh_jti=new_jti)
    assert old_session is not None
    assert new_session is not None
    assert old_session["revoked_at"] is not None
    assert old_session["revoke_reason"] == "ROTATED"
    assert int(old_session["replaced_by_session_id"]) == int(new_session["session_id"])


def test_old_refresh_token_cannot_be_reused_after_rotation(monkeypatch) -> None:
    service, _auth_repo, _session_repo, _token_service = _build_auth_service(monkeypatch)

    login_result = service.login(identifier="tester", password="pw")
    old_refresh = login_result["refresh_token"]

    _ = service.refresh(old_refresh)

    with pytest.raises(ApiError) as exc_info:
        service.refresh(old_refresh)

    assert exc_info.value.code == "invalid_token"


def test_logout_revokes_refresh_session(monkeypatch) -> None:
    service, _auth_repo, session_repo, token_service = _build_auth_service(monkeypatch)

    login_result = service.login(identifier="tester", password="pw")
    refresh_token = login_result["refresh_token"]
    refresh_jti = _extract_jti(token_service, refresh_token)

    result = service.logout(refresh_token=refresh_token)

    assert result["status"] == "logged_out"
    session = session_repo.get_session_by_jti(refresh_jti=refresh_jti)
    assert session is not None
    assert session["revoked_at"] is not None
    assert session["revoke_reason"] == "LOGOUT"


def test_operator_revoke_active_session_records_audit_fields(monkeypatch) -> None:
    _service, _auth_repo, session_repo, _token_service = _build_auth_service(monkeypatch)
    session_service = SessionService(repository=session_repo, token_service=TokenService())

    session_repo.create_session(
        user_id=10,
        refresh_jti="refresh-jti-1",
        refresh_token_hash="hashed-refresh-token",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        user_agent="pytest",
        ip_address="127.0.0.1",
    )

    revoked = session_service.revoke_active_session_for_user(
        user_id=10,
        revoked_by_user_id=2,
        revoke_actor_role="PROCTOR",
        revoke_reason="PROCTOR_REVOKED",
        revoke_context_json={"action": "stale_session_revoke", "exam_sitting_room_id": 100, "student_id": 1001},
    )

    assert revoked is True
    active = session_repo.get_active_session_by_user_id(user_id=10)
    assert active is None
    stored = session_repo.sessions[1]
    assert stored["revoked_by_user_id"] == 2
    assert stored["revoke_actor_role"] == "PROCTOR"
    assert stored["revoke_reason"] == "PROCTOR_REVOKED"
    assert stored["revoke_context_json"] == {"action": "stale_session_revoke", "exam_sitting_room_id": 100, "student_id": 1001}


def test_operator_revoke_active_session_returns_false_when_no_session(monkeypatch) -> None:
    _service, _auth_repo, session_repo, _token_service = _build_auth_service(monkeypatch)
    session_service = SessionService(repository=session_repo, token_service=TokenService())

    revoked = session_service.revoke_active_session_for_user(
        user_id=10,
        revoked_by_user_id=2,
        revoke_actor_role="PROCTOR",
        revoke_reason="PROCTOR_REVOKED",
        revoke_context_json={"action": "stale_session_revoke"},
    )

    assert revoked is False


def test_revoked_refresh_token_cannot_refresh(monkeypatch) -> None:
    service, _auth_repo, _session_repo, _token_service = _build_auth_service(monkeypatch)

    login_result = service.login(identifier="tester", password="pw")
    refresh_token = login_result["refresh_token"]

    _ = service.logout(refresh_token=refresh_token)

    with pytest.raises(ApiError) as exc_info:
        service.refresh(refresh_token)

    assert exc_info.value.code == "invalid_token"


def test_admin_can_revoke_active_session(monkeypatch) -> None:
    service, _auth_repo, session_repo, token_service = _build_auth_service(monkeypatch)

    login_result = service.login(identifier="tester", password="pw")
    refresh_jti = _extract_jti(token_service, login_result["refresh_token"])

    revoked = service.session_service.revoke_active_session_for_user(
        user_id=10,
        revoked_by_user_id=1,
        revoke_actor_role="ADMIN",
        revoke_reason="ADMIN_REVOKED",
        revoke_context_json={"action": "admin_revoke_active_session", "target_user_id": 10},
    )

    assert revoked is True
    session = session_repo.get_session_by_jti(refresh_jti=refresh_jti)
    assert session is not None
    assert session["revoked_at"] is not None
    assert session["revoke_reason"] == "ADMIN_REVOKED"
    assert session["revoked_by_user_id"] == 1
    assert session["revoke_actor_role"] == "ADMIN"
    assert session["revoke_context_json"] == {"action": "admin_revoke_active_session", "target_user_id": 10}


def test_proctor_can_revoke_active_session(monkeypatch) -> None:
    service, _auth_repo, session_repo, token_service = _build_auth_service(monkeypatch)

    login_result = service.login(identifier="tester", password="pw")
    refresh_jti = _extract_jti(token_service, login_result["refresh_token"])

    revoked = service.session_service.revoke_active_session_for_user(
        user_id=10,
        revoked_by_user_id=2,
        revoke_actor_role="PROCTOR",
        revoke_reason="PROCTOR_REVOKED",
        revoke_context_json={
            "action": "stale_session_revoke",
            "exam_sitting_room_id": 100,
            "student_id": 20,
        },
    )

    assert revoked is True
    session = session_repo.get_session_by_jti(refresh_jti=refresh_jti)
    assert session is not None
    assert session["revoke_reason"] == "PROCTOR_REVOKED"
    assert session["revoked_by_user_id"] == 2
    assert session["revoke_actor_role"] == "PROCTOR"
    assert session["revoke_context_json"] == {
        "action": "stale_session_revoke",
        "exam_sitting_room_id": 100,
        "student_id": 20,
    }


def test_revoke_active_session_returns_false_when_none_exists(monkeypatch) -> None:
    service, _auth_repo, _session_repo, _token_service = _build_auth_service(monkeypatch)

    revoked = service.session_service.revoke_active_session_for_user(
        user_id=10,
        revoked_by_user_id=1,
        revoke_actor_role="ADMIN",
        revoke_reason="ADMIN_REVOKED",
        revoke_context_json={"action": "admin_revoke_active_session", "target_user_id": 10},
    )

    assert revoked is False


def test_admin_revoked_refresh_token_cannot_refresh(monkeypatch) -> None:
    service, _auth_repo, _session_repo, _token_service = _build_auth_service(monkeypatch)

    login_result = service.login(identifier="tester", password="pw")
    refresh_token = login_result["refresh_token"]

    revoked = service.session_service.revoke_active_session_for_user(
        user_id=10,
        revoked_by_user_id=1,
        revoke_actor_role="ADMIN",
        revoke_reason="ADMIN_REVOKED",
        revoke_context_json={"action": "admin_revoke_active_session", "target_user_id": 10},
    )

    assert revoked is True

    with pytest.raises(ApiError) as exc_info:
        service.refresh(refresh_token)

    assert exc_info.value.code == "invalid_token"


def test_revoking_active_session_permits_subsequent_login(monkeypatch) -> None:
    service, _auth_repo, _session_repo, _token_service = _build_auth_service(monkeypatch)

    _ = service.login(identifier="tester", password="pw")
    revoked = service.session_service.revoke_active_session_for_user(
        user_id=10,
        revoked_by_user_id=1,
        revoke_actor_role="ADMIN",
        revoke_reason="ADMIN_REVOKED",
        revoke_context_json={"action": "admin_revoke_active_session", "target_user_id": 10},
    )

    assert revoked is True

    second_login = service.login(identifier="tester", password="pw")
    assert second_login["token_type"] == "bearer"


def test_expired_session_cannot_refresh(monkeypatch) -> None:
    service, _auth_repo, session_repo, token_service = _build_auth_service(monkeypatch)

    login_result = service.login(identifier="tester", password="pw")
    refresh_token = login_result["refresh_token"]
    refresh_jti = _extract_jti(token_service, refresh_token)
    session = session_repo.get_session_by_jti(refresh_jti=refresh_jti)
    assert session is not None

    session["expires_at"] = datetime.now(UTC) - timedelta(seconds=1)

    with pytest.raises(ApiError) as exc_info:
        service.refresh(refresh_token)

    assert exc_info.value.code == "invalid_token"


def test_refresh_token_hash_is_stored_raw_token_is_not(monkeypatch) -> None:
    service, _auth_repo, session_repo, token_service = _build_auth_service(monkeypatch)

    login_result = service.login(identifier="tester", password="pw")
    refresh_token = login_result["refresh_token"]
    refresh_jti = _extract_jti(token_service, refresh_token)

    stored = session_repo.get_session_by_jti(refresh_jti=refresh_jti)
    assert stored is not None
    assert stored["refresh_token_hash"] != refresh_token
    assert refresh_token not in stored.values()


def test_refresh_state_survives_token_service_restart(monkeypatch) -> None:
    shared_session_repo = InMemorySessionRepository()
    service_1, _auth_repo_1, _session_repo_1, _token_service_1 = _build_auth_service(
        monkeypatch,
        session_repository=shared_session_repo,
    )

    login_result = service_1.login(identifier="tester", password="pw")
    old_refresh = login_result["refresh_token"]
    rotated = service_1.refresh(old_refresh)
    new_refresh = rotated["refresh_token"]

    service_2, _auth_repo_2, _session_repo_2, _token_service_2 = _build_auth_service(
        monkeypatch,
        session_repository=shared_session_repo,
    )

    with pytest.raises(ApiError) as exc_info:
        service_2.refresh(old_refresh)
    assert exc_info.value.code == "invalid_token"

    second_rotate = service_2.refresh(new_refresh)
    assert second_rotate["refresh_token"] != new_refresh
