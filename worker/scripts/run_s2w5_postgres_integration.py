#!/usr/bin/env python3
"""Run the S2W-5 PostgreSQL integration and smoke regression pack."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import os


REPO_ROOT = Path(__file__).resolve().parents[3]


INTEGRATION_GROUPS: list[tuple[str, list[str]]] = [
    (
        "S2W-5.3 capture claim/resume",
        [
            "apps/worker/tests/test_capture_job_claim_postgres_integration.py",
        ],
    ),
    (
        "S2W-5.5 capture worker",
        [
            "apps/worker/tests/test_capture_worker_postgres_integration.py",
        ],
    ),
    (
        "S2W-5.6 capture-aware materialization",
        [
            "apps/worker/tests/test_grading_worker_capture_route_postgres_integration.py",
        ],
    ),
    (
        "S2W-5 static guards",
        [
            "apps/worker/tests/test_capture_route_static_guards.py",
            "apps/worker/tests/test_grading_worker_no_mutable_answer_source_guard.py",
        ],
    ),
]


SMOKE_FILES: list[str] = [
    "db/postgres/05_tests/276_assert_s2w5_capture_job_lease_schema_ready.sql",
]


def _resolve_psql_path(explicit_path: str | None) -> str | None:
    if explicit_path:
        return explicit_path

    found = shutil.which("psql")
    if found:
        return found

    if os.name == "nt":
        roots = [
            Path(os.environ.get("ProgramFiles", "")) / "PostgreSQL",
            Path(os.environ.get("ProgramFiles(x86)", "")) / "PostgreSQL",
        ]
        for root in roots:
            if not str(root):
                continue
            if not root.exists():
                continue
            candidates = sorted(root.glob("**/psql.exe"))
            if candidates:
                return str(candidates[0])

    return None


def _smoke_env(db_name: str) -> tuple[str, str, str, str, str]:
    host = os.getenv("POSTGRES_MAINTENANCE_HOST") or os.getenv("POSTGRES_HOST") or "localhost"
    port = os.getenv("POSTGRES_MAINTENANCE_PORT") or os.getenv("POSTGRES_PORT") or "5432"
    user = os.getenv("POSTGRES_MAINTENANCE_USER") or os.getenv("PGUSER") or "postgres"
    password = (
        os.getenv("POSTGRES_MAINTENANCE_PASSWORD")
        or os.getenv("PGPASSWORD")
        or os.getenv("POSTGRES_PASSWORD")
        or ""
    )
    return host, port, user, password, db_name


def _run_cmd(cmd: list[str], env: dict[str, str] | None = None) -> int:
    print("[CMD]", " ".join(cmd))
    completed = subprocess.run(cmd, cwd=REPO_ROOT, env=env)
    return int(completed.returncode)


def _run_smoke(psql_path: str, db_name: str) -> int:
    host, port, user, password, target_db = _smoke_env(db_name)

    env = os.environ.copy()
    env["PGHOST"] = host
    env["PGPORT"] = port
    env["PGUSER"] = user
    env["PGPASSWORD"] = password

    print("\n[SMOKE] S2W-5 smoke SQL 276")
    print(f"[INFO] PGHOST={host} PGPORT={port} PGUSER={user} DB={target_db}")

    for rel_path in SMOKE_FILES:
        sql_file = REPO_ROOT / rel_path
        if not sql_file.exists():
            print(f"[ERROR] Missing smoke file: {rel_path}")
            return 2

        rc = _run_cmd(
            [
                psql_path,
                "-h",
                host,
                "-p",
                port,
                "-U",
                user,
                "-d",
                target_db,
                "-v",
                "ON_ERROR_STOP=1",
                "-f",
                str(sql_file),
            ],
            env=env,
        )
        if rc != 0:
            print(f"[FAIL] Smoke SQL failed: {rel_path}")
            return rc

    print("[OK] Smoke SQL 276 passed.")
    return 0


def _run_pytest_groups(groups: list[tuple[str, list[str]]], env: dict[str, str]) -> int:
    for name, tests in groups:
        print(f"\n[GROUP] {name}")
        rc = _run_cmd([sys.executable, "-m", "pytest", "-q", *tests], env=env)
        if rc != 0:
            print(f"[FAIL] Group failed: {name}")
            return rc
    return 0


def _validate_app_db_env() -> bool:
    required = [
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    ]
    missing = [name for name in required if not str(os.getenv(name, "")).strip()]
    if missing:
        print("[ERROR] Missing required app DB env for integration tests:")
        for name in missing:
            print(f"- {name}")
        return False
    return True


def _resolve_smoke_db_name(explicit_db_name: str | None) -> str:
    contract_db_name = str(os.getenv("POSTGRES_DB") or "").strip()
    if not contract_db_name:
        raise RuntimeError("POSTGRES_DB is required; generate it from root .env.lan DB_NAME.")
    if explicit_db_name is not None and str(explicit_db_name).strip() != contract_db_name:
        raise RuntimeError("--db-name must match POSTGRES_DB from the .env.lan contract.")
    return contract_db_name


def _warn_if_capture_source_dsn_missing() -> None:
    if str(os.getenv("STUDENT_CAPTURE_SOURCE_DSN", "")).strip():
        return
    print(
        "[WARN] STUDENT_CAPTURE_SOURCE_DSN is not set. "
        "This integration pack can still run with deterministic test adapter paths, "
        "but production capture adapter/CLI paths require STUDENT_CAPTURE_SOURCE_DSN."
    )


def _runtime_user_for_info() -> str:
    return str(os.getenv("POSTGRES_USER") or "<unset>").strip() or "<unset>"


def _maintenance_user_for_info() -> str:
    return str(os.getenv("POSTGRES_MAINTENANCE_USER") or os.getenv("PGUSER") or "postgres").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run S2W-5 PostgreSQL integration pack")
    parser.add_argument(
        "--group",
        action="append",
        default=[],
        help="Optional group name filter (can be passed multiple times)",
    )
    parser.add_argument("--skip-smoke", action="store_true", help="Skip DB smoke SQL 276")
    parser.add_argument(
        "--db-name",
        default=None,
        help="Target DB for smoke SQL; if provided, it must match POSTGRES_DB from .env.lan.",
    )
    parser.add_argument("--psql-path", default=None, help="Optional explicit path to psql executable")
    parser.add_argument(
        "--allow-app-db-dsn-for-tests",
        action="store_true",
        help="Set ALLOW_STUDENT_CAPTURE_APP_DB_DSN_FOR_TESTS=1 for this run",
    )
    args = parser.parse_args()

    print("S2W-5 PostgreSQL integration regression pack")
    print(f"Repo root: {REPO_ROOT}")
    print(
        "[INFO] DB users: "
        f"runtime_user={_runtime_user_for_info()} "
        f"maintenance_user={_maintenance_user_for_info()}"
    )

    selected_groups = INTEGRATION_GROUPS
    if args.group:
        wanted = {str(item).strip().lower() for item in args.group if str(item).strip()}
        selected_groups = [
            (name, tests)
            for name, tests in INTEGRATION_GROUPS
            if name.strip().lower() in wanted
        ]
        if not selected_groups:
            print("[ERROR] No matching groups were selected.")
            return 2

    if not _validate_app_db_env():
        return 2
    try:
        smoke_db_name = _resolve_smoke_db_name(args.db_name)
    except RuntimeError as exc:
        print(f"[ERROR] {exc}")
        return 2

    _warn_if_capture_source_dsn_missing()

    test_env = os.environ.copy()
    test_env["EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION"] = "1"
    if args.allow_app_db_dsn_for_tests:
        test_env["ALLOW_STUDENT_CAPTURE_APP_DB_DSN_FOR_TESTS"] = "1"

    if not args.skip_smoke:
        psql_path = _resolve_psql_path(args.psql_path)
        if not psql_path:
            print("[ERROR] psql not found. Install PostgreSQL client tools, add psql to PATH, or pass --psql-path.")
            return 2

        rc = _run_smoke(psql_path=psql_path, db_name=smoke_db_name)
        if rc != 0:
            return rc

    rc = _run_pytest_groups(selected_groups, env=test_env)
    if rc != 0:
        return rc

    print("\n[OK] S2W-5 PostgreSQL integration regression pack passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
