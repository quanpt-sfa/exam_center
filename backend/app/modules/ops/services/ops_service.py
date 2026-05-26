"""Application service for ops command run APIs."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
import re

from app.core.errors import ApiError
from app.infrastructure.database.unit_of_work import database_unit_of_work
from app.modules.importing.repositories.ops_audit_repository import OpsAuditRepository


_ROLE_EXECUTE_FALLBACK = {"ADMIN", "AGENT", "AGENT_SERVICE", "SERVICE_ACCOUNT", "SYSTEM_AGENT"}
_SENSITIVE_KEY_PATTERN = re.compile(
    r"password|passwd|secret|token|api[_-]?key|private[_-]?key|access[_-]?key|client[_-]?secret",
    re.IGNORECASE,
)


def _redact_sensitive_payload(payload: dict | None) -> dict | None:
    if payload is None:
        return None

    def _sanitize(value: object, *, key_hint: str | None = None) -> object:
        if key_hint and _SENSITIVE_KEY_PATTERN.search(key_hint):
            return "***REDACTED***"
        if isinstance(value, dict):
            return {str(k): _sanitize(v, key_hint=str(k)) for k, v in value.items()}
        if isinstance(value, list):
            return [_sanitize(item) for item in value]
        return value

    return _sanitize(payload) if isinstance(payload, dict) else None


class OpsService:
    def __init__(
        self,
        repository: OpsAuditRepository | None = None,
        transaction_scope: Callable[[], AbstractContextManager[object]] | None = None,
    ) -> None:
        self.repository = repository or OpsAuditRepository()
        has_custom_dependencies = repository is not None
        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif has_custom_dependencies:
            self._transaction_scope = nullcontext
        else:
            self._transaction_scope = database_unit_of_work

    @staticmethod
    def _ensure_execute_permission(current_user: dict) -> None:
        permissions = {
            str(item).strip().lower()
            for item in (current_user.get("permissions") or [])
            if str(item).strip()
        }
        if "ops:execute" in permissions or "*" in permissions:
            return

        roles = {
            str(item).strip().upper()
            for item in (current_user.get("roles") or [])
            if str(item).strip()
        }
        if roles.intersection(_ROLE_EXECUTE_FALLBACK):
            return

        raise ApiError(
            status_code=403,
            code="permission_denied",
            message="Missing required permission: ops:execute",
            details={},
        )

    @staticmethod
    def _actor_agent(current_user: dict) -> str | None:
        username = str(current_user.get("username") or "").strip()
        if username:
            return username
        email = str(current_user.get("email") or "").strip()
        if email:
            return email
        service_account = str(current_user.get("service_account_name") or "").strip()
        if service_account:
            return service_account
        principal_id = str(current_user.get("principal_id") or current_user.get("client_id") or "").strip()
        if principal_id:
            return principal_id
        return None

    def create_command_run(self, *, payload: dict, current_user: dict) -> dict:
        self._ensure_execute_permission(current_user)

        actor_user_id = int(current_user["user_id"])
        actor_agent = self._actor_agent(current_user)
        command_code = str(payload["command_code"]).strip().upper()
        command_text = str(payload.get("command_text") or payload["command_code"])
        redacted_payload = _redact_sensitive_payload(
            payload.get("event_payload") if isinstance(payload.get("event_payload"), dict) else None,
        )

        with self._transaction_scope() as conn:
            run_id = self.repository.create_command_run(
                command_code=command_code,
                actor_user_id=actor_user_id,
                actor_agent=actor_agent,
                command_text=command_text,
                conn=conn,
            )
            self.repository.add_command_event(
                run_id=run_id,
                event_type="RUN_CREATED",
                payload=redacted_payload,
                conn=conn,
            )

        return {
            "agent_command_run_id": run_id,
            "command_code": command_code,
            "run_status": "RUNNING",
            "actor_user_id": actor_user_id,
            "actor_agent": actor_agent,
        }

    def list_command_runs(self, *, limit: int, offset: int) -> dict:
        return {
            "items": self.repository.list_command_runs(limit=limit, offset=offset),
            "limit": limit,
            "offset": offset,
        }


def build_ops_service() -> OpsService:
    return OpsService()
