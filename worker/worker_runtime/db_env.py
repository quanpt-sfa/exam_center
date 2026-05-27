"""Database environment helpers for worker runtime connections."""

from __future__ import annotations

import os


def required_postgres_db_name() -> str:
    """Return generated POSTGRES_DB or fail instead of inventing a DB target."""

    database = os.getenv("POSTGRES_DB", "").strip()
    if not database:
        raise RuntimeError(
            "POSTGRES_DB is required. Set POSTGRES_DB in the standalone service environment or test environment."
        )
    return database


def build_postgres_conninfo_from_env() -> str:
    """Build worker runtime conninfo from generated POSTGRES_* service env."""

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = required_postgres_db_name()
    user = os.getenv("POSTGRES_USER", "exam_sys_app")
    password = os.getenv("POSTGRES_PASSWORD", "")
    sslmode = os.getenv("POSTGRES_SSLMODE", "prefer")
    timeout = os.getenv("POSTGRES_CONNECT_TIMEOUT", "3")
    return (
        f"host={host} port={port} dbname={database} user={user} "
        f"password={password} sslmode={sslmode} connect_timeout={timeout}"
    )
