"""Worker identity helpers for runtime process isolation and traceability."""

from __future__ import annotations

import os
import re
import socket


_ROLE_SET = {"dispatcher", "capture", "grading", "session-monitor", "all"}


def _clean_token(value: str | None, *, fallback: str) -> str:
    token = str(value or "").strip().lower()
    if not token:
        token = fallback
    token = re.sub(r"[^a-z0-9._-]+", "-", token)
    token = re.sub(r"-+", "-", token).strip("-")
    return token or fallback


def normalize_worker_role(role: str) -> str:
    normalized = _clean_token(role, fallback="all")
    if normalized not in _ROLE_SET:
        raise ValueError("Unsupported worker role; expected one of: dispatcher, capture, grading, session-monitor, all")
    return normalized


def ensure_worker_role_suffix(worker_id: str, *, role: str) -> str:
    normalized_role = normalize_worker_role(role)
    candidate = str(worker_id or "").strip()
    if not candidate:
        return normalized_role
    if candidate.endswith(f"-{normalized_role}"):
        return candidate
    return f"{candidate}-{normalized_role}"


def generate_worker_id(
    *,
    role: str,
    worker_id: str | None = None,
    worker_id_prefix: str | None = None,
    hostname: str | None = None,
    pid: int | None = None,
) -> str:
    """Return an explicit worker id if provided, otherwise generate role-aware id."""

    explicit = str(worker_id or "").strip()
    if explicit:
        return explicit

    normalized_role = normalize_worker_role(role)
    prefix = _clean_token(worker_id_prefix, fallback="worker")
    host = _clean_token(hostname or socket.gethostname(), fallback="host")
    process_id = int(pid if pid is not None else os.getpid())

    return f"{prefix}-{host}-p{process_id}-{normalized_role}"
