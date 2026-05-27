"""Validate that CI/local test DB env points at a safe PostgreSQL test database."""

from __future__ import annotations

import os
import sys


def _required(name: str) -> str:
    value = str(os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for PostgreSQL test DB checks.")
    return value


def _is_safe_test_database(name: str) -> bool:
    normalized = name.strip().lower()
    return normalized == "exam_sys_test" or normalized.endswith("_test")


def main() -> int:
    database = _required("POSTGRES_DB")
    _required("POSTGRES_HOST")
    _required("POSTGRES_PORT")
    _required("POSTGRES_USER")
    _required("POSTGRES_PASSWORD")

    if not _is_safe_test_database(database):
        raise RuntimeError(
            "POSTGRES_DB must be a dedicated test database name ending with '_test' "
            "or exactly 'exam_sys_test'."
        )

    print(
        "[OK] PostgreSQL test DB target is safe:",
        f"host={os.getenv('POSTGRES_HOST')}",
        f"port={os.getenv('POSTGRES_PORT')}",
        f"user={os.getenv('POSTGRES_USER')}",
        f"db={database}",
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
