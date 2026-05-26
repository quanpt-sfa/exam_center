#!/usr/bin/env python3
"""UE2E seed and cleanup helper for browser hybrid scenarios.

Design notes:
- Uses maintenance DB role for setup/cleanup.
- Generates UE2E-prefixed metadata and idempotency keys.
- Cleanup is prefix-targeted (`ue2e-`) and does not perform broad deletions.
- Canonical UE2E principals are seeded idempotently for bearer-token E2E flows.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import sys
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


REPO_ROOT = Path(__file__).resolve().parents[3]
WORKER_SRC = REPO_ROOT / "apps" / "worker"
TESTS_SRC = WORKER_SRC / "tests"
API_SRC = REPO_ROOT / "apps" / "api"

for import_path in (str(API_SRC), str(WORKER_SRC), str(TESTS_SRC)):
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

from app.modules.auth.services.password_service import PasswordService
from app.modules.auth.services.token_service import TokenService
from s2w7_e2e_test_support import create_s2w7_capture_seed_graph
from s2w7_e2e_test_support import create_s2w7_textbox_sql_seed_graph
from s2w7_e2e_test_support import open_maintenance_connection
from ue2e_seed_auth_output import build_seed_auth_payload
from ue2e_seed_auth_output import validate_emit_request


PASSWORD_SERVICE = PasswordService()
TOKEN_SERVICE = TokenService()

CANONICAL_PRINCIPALS: dict[str, dict[str, Any]] = {
    "admin": {
        "username": "ue2e_admin",
        "email_login": "ue2e_admin@local.test",
        "full_name": "UE2E Admin",
        "roles": ["ADMIN"],
        "student_code": None,
    },
    "owner": {
        "username": "ue2e_student_owner",
        "email_login": "ue2e_student_owner@local.test",
        "full_name": "UE2E Student Owner",
        "roles": ["STUDENT"],
        "student_code": "UE2E-STUDENT-OWNER",
    },
    "non_owner": {
        "username": "ue2e_student_non_owner",
        "email_login": "ue2e_student_non_owner@local.test",
        "full_name": "UE2E Student Non Owner",
        "roles": ["STUDENT"],
        "student_code": "UE2E-STUDENT-NON-OWNER",
    },
}

KNOWN_TEST_PREFIXES: dict[str, list[str]] = {
    "ue2e-": ["ue2e-%", "ue2e_%"],
    "s2w-": ["s2w-%", "s2w_%"],
    "test-": ["test-%", "test_%"],
    "codex-": ["codex-%", "codex_%"],
}

AUTH_JUNK_EMAIL_PATTERNS: list[str] = [
    "ue2e-%@%",
    "ue2e_%@%",
    "s2w-%@%",
    "s2w_%@%",
    "test-%@%",
    "test_%@%",
    "codex-%@%",
    "codex_%@%",
]

AUTH_JUNK_FULL_NAME_PATTERNS: list[str] = [
    "UE2E %",
    "S2W %",
    "TEST %",
    "CODEX %",
]


_COLUMN_CACHE: dict[tuple[str, str, str], bool] = {}


class SeedHelperStatementError(RuntimeError):
    """Database statement error with sanitized context."""

    def __init__(self, *, command: str, action: str, table: str, postgres_message: str) -> None:
        self.command = str(command)
        self.action = str(action)
        self.table = str(table)
        self.postgres_message = str(postgres_message)
        super().__init__(
            f"DB statement failed (command={self.command}, action={self.action}, table={self.table}): "
            f"{self.postgres_message}"
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "action": self.action,
            "table": self.table,
            "postgres_message": self.postgres_message,
        }


def _sanitize_error_text(text: str) -> str:
    sanitized = str(text or "")
    sanitized = re.sub(r"(?i)(password\s*[:=]\s*)([^,\s;]+)", r"\1<redacted>", sanitized)
    sanitized = re.sub(r"(?i)(authorization\s*[:=]\s*bearer\s+)([A-Za-z0-9._-]+)", r"\1<redacted>", sanitized)
    sanitized = re.sub(r"(?i)(token\s*[:=]\s*)([A-Za-z0-9._-]+)", r"\1<redacted>", sanitized)
    sanitized = re.sub(r"postgres(?:ql)?:\/\/[^\s]+", "postgresql://<redacted>", sanitized)
    return sanitized


def _extract_pg_error_message(exc: Exception) -> str:
    diag = getattr(exc, "diag", None)
    if diag is not None:
        primary = getattr(diag, "message_primary", None)
        detail = getattr(diag, "message_detail", None)
        if primary and detail:
            return _sanitize_error_text(f"{primary} ({detail})")
        if primary:
            return _sanitize_error_text(str(primary))
    return _sanitize_error_text(str(exc))


def _execute_sql(
    cur,
    *,
    command: str,
    action: str,
    table: str,
    query: str,
    params: tuple[Any, ...] = (),
) -> None:
    try:
        cur.execute(query, params)
    except Exception as exc:  # noqa: BLE001
        raise SeedHelperStatementError(
            command=command,
            action=action,
            table=table,
            postgres_message=_extract_pg_error_message(exc),
        ) from exc


def _table_exists(conn, schema: str, table: str) -> bool:
    with conn.cursor(row_factory=dict_row) as cur:
        _execute_sql(
            cur,
            command="schema-check",
            action="table_exists",
            table=f"{schema}.{table}",
            query="""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables t
                WHERE t.table_schema = %s
                  AND t.table_name = %s
            ) AS table_exists
            """,
            params=(str(schema), str(table)),
        )
        row = cur.fetchone()
    return bool(row and row.get("table_exists"))


def _table_has_column(conn, schema: str, table: str, column: str) -> bool:
    cache_key = (str(schema), str(table), str(column))
    cached = _COLUMN_CACHE.get(cache_key)
    if cached is not None:
        return bool(cached)

    with conn.cursor(row_factory=dict_row) as cur:
        _execute_sql(
            cur,
            command="schema-check",
            action="table_has_column",
            table=f"{schema}.{table}",
            query="""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns c
                WHERE c.table_schema = %s
                  AND c.table_name = %s
                  AND c.column_name = %s
            ) AS column_exists
            """,
            params=(str(schema), str(table), str(column)),
        )
        row = cur.fetchone()

    result = bool(row and row.get("column_exists"))
    _COLUMN_CACHE[cache_key] = result
    return result


def _update_source_metadata(
    conn,
    *,
    command: str,
    table: str,
    id_column: str,
    row_id: int | None,
    prefix: str,
) -> None:
    if row_id is None:
        return

    schema_name, table_name = table.split(".", 1)
    if not _table_has_column(conn, schema_name, table_name, "metadata_json"):
        return

    with conn.cursor(row_factory=dict_row) as cur:
        _execute_sql(
            cur,
            command=command,
            action="retag_source_metadata",
            table=table,
            query=f"""
            UPDATE {table}
            SET metadata_json = coalesce(metadata_json, '{{}}'::jsonb) || %s
            WHERE {id_column} = %s
            """,
            params=(Jsonb({"source": prefix}), int(row_id)),
        )


def _retag_seed_records(conn, *, command: str, seed: dict[str, Any], prefix: str, suffix: str) -> None:
    has_exam_submission_metadata = _table_has_column(conn, "submission", "exam_submission", "metadata_json")
    has_submission_seal_metadata = _table_has_column(conn, "submission", "submission_seal", "metadata_json")
    has_grading_job_metadata = _table_has_column(conn, "grading", "grading_job", "metadata_json")
    has_capture_job_metadata = _table_has_column(conn, "capture", "capture_job", "metadata_json")
    has_generated_question_metadata = _table_has_column(conn, "delivery", "generated_exam_question", "metadata_json")

    with conn.cursor(row_factory=dict_row) as cur:
        submission_id = int(seed["exam_submission_id"])
        submission_seal_id = int(seed["submission_seal_id"])
        grading_job_id = int(seed["grading_job_id"])

        if has_exam_submission_metadata:
            _execute_sql(
                cur,
                command=command,
                action="retag_exam_submission",
                table="submission.exam_submission",
                query="""
                UPDATE submission.exam_submission
                SET metadata_json = coalesce(metadata_json, '{}'::jsonb) || %s
                WHERE exam_submission_id = %s
                """,
                params=(Jsonb({"source": prefix}), submission_id),
            )

        if has_submission_seal_metadata:
            _execute_sql(
                cur,
                command=command,
                action="retag_submission_seal",
                table="submission.submission_seal",
                query="""
                UPDATE submission.submission_seal
                SET
                    seal_idempotency_key = %s,
                    metadata_json = coalesce(metadata_json, '{}'::jsonb) || %s
                WHERE submission_seal_id = %s
                """,
                params=(f"{prefix}-seal", Jsonb({"source": prefix}), submission_seal_id),
            )
        else:
            _execute_sql(
                cur,
                command=command,
                action="retag_submission_seal",
                table="submission.submission_seal",
                query="""
                UPDATE submission.submission_seal
                SET seal_idempotency_key = %s
                WHERE submission_seal_id = %s
                """,
                params=(f"{prefix}-seal", submission_seal_id),
            )

        if has_grading_job_metadata:
            _execute_sql(
                cur,
                command=command,
                action="retag_grading_job",
                table="grading.grading_job",
                query="""
                UPDATE grading.grading_job
                SET
                    idempotency_key = %s,
                    metadata_json = coalesce(metadata_json, '{}'::jsonb) || %s
                WHERE grading_job_id = %s
                """,
                params=(f"{prefix}-grading-job", Jsonb({"source": prefix}), grading_job_id),
            )
        else:
            _execute_sql(
                cur,
                command=command,
                action="retag_grading_job",
                table="grading.grading_job",
                query="""
                UPDATE grading.grading_job
                SET idempotency_key = %s
                WHERE grading_job_id = %s
                """,
                params=(f"{prefix}-grading-job", grading_job_id),
            )

        capture_job_id = seed.get("capture_job_id")
        if capture_job_id is not None:
            if has_capture_job_metadata:
                _execute_sql(
                    cur,
                    command=command,
                    action="retag_capture_job",
                    table="capture.capture_job",
                    query="""
                    UPDATE capture.capture_job
                    SET
                        idempotency_key = %s,
                        metadata_json = coalesce(metadata_json, '{}'::jsonb) || %s
                    WHERE capture_job_id = %s
                    """,
                    params=(f"{prefix}-capture-job", Jsonb({"source": prefix}), int(capture_job_id)),
                )
            else:
                _execute_sql(
                    cur,
                    command=command,
                    action="retag_capture_job",
                    table="capture.capture_job",
                    query="""
                    UPDATE capture.capture_job
                    SET idempotency_key = %s
                    WHERE capture_job_id = %s
                    """,
                    params=(f"{prefix}-capture-job", int(capture_job_id)),
                )

        question_template_id = seed.get("question_template_id")
        if question_template_id is not None:
            _execute_sql(
                cur,
                command=command,
                action="retag_question_template",
                table="assessment.question_template",
                query="""
                UPDATE assessment.question_template
                SET template_code = %s
                WHERE question_template_id = %s
                """,
                params=(f"UE2E_QT_{suffix}".upper(), int(question_template_id)),
            )

        generated_exam_question_id = seed.get("generated_exam_question_id")
        if generated_exam_question_id is not None:
            if has_generated_question_metadata:
                _execute_sql(
                    cur,
                    command=command,
                    action="retag_generated_exam_question",
                    table="delivery.generated_exam_question",
                    query="""
                    UPDATE delivery.generated_exam_question
                    SET
                        question_code = %s,
                        metadata_json = coalesce(metadata_json, '{}'::jsonb) || %s
                    WHERE generated_exam_question_id = %s
                    """,
                    params=(f"UE2E_Q_{suffix}".upper(), Jsonb({"source": prefix}), int(generated_exam_question_id)),
                )
            else:
                _execute_sql(
                    cur,
                    command=command,
                    action="retag_generated_exam_question",
                    table="delivery.generated_exam_question",
                    query="""
                    UPDATE delivery.generated_exam_question
                    SET question_code = %s
                    WHERE generated_exam_question_id = %s
                    """,
                    params=(f"UE2E_Q_{suffix}".upper(), int(generated_exam_question_id)),
                )

        _update_source_metadata(
            conn,
            command=command,
            table="delivery.generated_expected_answer",
            id_column="generated_expected_answer_id",
            row_id=(int(seed["generated_expected_answer_id"]) if seed.get("generated_expected_answer_id") else None),
            prefix=prefix,
        )
        _update_source_metadata(
            conn,
            command=command,
            table="assessment.question_grading_profile",
            id_column="question_grading_profile_id",
            row_id=(int(seed["question_grading_profile_id"]) if seed.get("question_grading_profile_id") else None),
            prefix=prefix,
        )

    conn.commit()


def _mark_capture_failed(conn, *, command: str, capture_job_id: int) -> None:
    has_capture_job_metadata = _table_has_column(conn, "capture", "capture_job", "metadata_json")

    with conn.cursor(row_factory=dict_row) as cur:
        if has_capture_job_metadata:
            _execute_sql(
                cur,
                command=command,
                action="mark_capture_failed",
                table="capture.capture_job",
                query="""
                UPDATE capture.capture_job
                SET
                    capture_status = 'FAILED',
                    started_at = coalesce(started_at, now()),
                    finished_at = now(),
                    worker_id = 'ue2e-capture-worker',
                    error_code = 'UE2E_CAPTURE_FAILED',
                    error_message = %s,
                    metadata_json = coalesce(metadata_json, '{}'::jsonb) || %s
                WHERE capture_job_id = %s
                RETURNING capture_job_id
                """,
                params=(
                    "STUDENT_CAPTURE_SOURCE_DSN=postgresql://user:secret@db.local/exam password=123 traceback select * from hidden_rows",
                    Jsonb({"source": "ue2e-failure"}),
                    int(capture_job_id),
                ),
            )
        else:
            _execute_sql(
                cur,
                command=command,
                action="mark_capture_failed",
                table="capture.capture_job",
                query="""
                UPDATE capture.capture_job
                SET
                    capture_status = 'FAILED',
                    started_at = coalesce(started_at, now()),
                    finished_at = now(),
                    worker_id = 'ue2e-capture-worker',
                    error_code = 'UE2E_CAPTURE_FAILED',
                    error_message = %s
                WHERE capture_job_id = %s
                RETURNING capture_job_id
                """,
                params=(
                    "STUDENT_CAPTURE_SOURCE_DSN=postgresql://user:secret@db.local/exam password=123 traceback select * from hidden_rows",
                    int(capture_job_id),
                ),
            )
        row = cur.fetchone()
    conn.commit()
    if row is None:
        raise RuntimeError("Failed to mark capture job as FAILED")


def _resolve_seed_password(username: str) -> str:
    explicit = str(os.getenv("UE2E_DEV_TEST_PASSWORD", "")).strip()
    if explicit:
        return explicit
    return f"ue2e-dev-only-{username}-{secrets.token_hex(8)}"


def _ensure_role_ids(conn, role_codes: list[str]) -> dict[str, int]:
    unique_codes = sorted(set(role_codes))
    if not unique_codes:
        return {}

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT role_code, role_id
            FROM identity.role
            WHERE role_code = ANY(%s)
            """,
            (unique_codes,),
        )
        rows = cur.fetchall()
        existing = {str(row["role_code"]): int(row["role_id"]) for row in rows}

        missing = [code for code in unique_codes if code not in existing]
        for code in missing:
            role_name = code.replace("_", " ").title()
            cur.execute(
                """
                INSERT INTO identity.role (role_code, role_name, description)
                VALUES (%s, %s, %s)
                ON CONFLICT (role_code)
                DO UPDATE SET
                    role_name = EXCLUDED.role_name,
                    description = EXCLUDED.description
                RETURNING role_id
                """,
                (code, role_name, f"UE2E canonical role seed for {code}"),
            )
            inserted = cur.fetchone()
            if inserted is None:
                raise RuntimeError(f"Failed to ensure role: {code}")
            existing[code] = int(inserted["role_id"])

    conn.commit()
    return existing


def _ensure_student_profile(conn, *, person_id: int, student_code: str) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT student_id
            FROM identity.student_profile
            WHERE student_code = %s OR person_id = %s
            ORDER BY CASE WHEN student_code = %s THEN 0 ELSE 1 END, student_id ASC
            LIMIT 1
            """,
            (student_code, int(person_id), student_code),
        )
        row = cur.fetchone()

        if row is None:
            cur.execute(
                """
                INSERT INTO identity.student_profile (
                    person_id,
                    student_code,
                    program_id,
                    cohort,
                    entry_year,
                    student_status
                )
                VALUES (%s, %s, NULL, NULL, NULL, 'ACTIVE')
                RETURNING student_id
                """,
                (int(person_id), student_code),
            )
            created = cur.fetchone()
            if created is None:
                raise RuntimeError("Failed to insert canonical student_profile")
            student_id = int(created["student_id"])
        else:
            student_id = int(row["student_id"])
            cur.execute(
                """
                UPDATE identity.student_profile
                SET
                    person_id = %s,
                    student_code = %s,
                    student_status = 'ACTIVE',
                    updated_at = now()
                WHERE student_id = %s
                """,
                (int(person_id), student_code, student_id),
            )

    conn.commit()
    return int(student_id)


def _ensure_canonical_principal(conn, *, principal: dict[str, Any], role_ids: dict[str, int]) -> dict[str, Any]:
    username = str(principal["username"])
    email_login = str(principal["email_login"])
    full_name = str(principal["full_name"])
    required_roles = [str(item) for item in principal.get("roles", [])]
    student_code = principal.get("student_code")

    password_hash = PASSWORD_SERVICE.hash_password(_resolve_seed_password(username))

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT user_id, person_id
            FROM identity.app_user
            WHERE username = %s
            LIMIT 1
            """,
            (username,),
        )
        user_row = cur.fetchone()

        if user_row is None:
            cur.execute(
                """
                INSERT INTO identity.person (full_name, person_status)
                VALUES (%s, 'ACTIVE')
                RETURNING person_id
                """,
                (full_name,),
            )
            person_row = cur.fetchone()
            if person_row is None:
                raise RuntimeError(f"Failed to insert person for {username}")
            person_id = int(person_row["person_id"])

            cur.execute(
                """
                INSERT INTO identity.app_user (
                    person_id,
                    username,
                    email_login,
                    password_hash,
                    user_status
                )
                VALUES (%s, %s, %s, %s, 'ACTIVE')
                RETURNING user_id
                """,
                (person_id, username, email_login, password_hash),
            )
            created_user = cur.fetchone()
            if created_user is None:
                raise RuntimeError(f"Failed to insert app_user for {username}")
            user_id = int(created_user["user_id"])
        else:
            user_id = int(user_row["user_id"])
            person_id = int(user_row["person_id"])

            cur.execute(
                """
                UPDATE identity.person
                SET full_name = %s, person_status = 'ACTIVE', updated_at = now()
                WHERE person_id = %s
                """,
                (full_name, person_id),
            )

            cur.execute(
                """
                UPDATE identity.app_user
                SET
                    email_login = %s,
                    password_hash = %s,
                    user_status = 'ACTIVE',
                    updated_at = now()
                WHERE user_id = %s
                """,
                (email_login, password_hash, user_id),
            )

        for role_code in required_roles:
            role_id = role_ids.get(role_code)
            if role_id is None:
                raise RuntimeError(f"Missing required role_id for {role_code}")
            cur.execute(
                """
                INSERT INTO identity.user_role (user_id, role_id, assigned_at, assigned_by, is_active)
                VALUES (%s, %s, now(), NULL, true)
                ON CONFLICT (user_id, role_id)
                DO UPDATE SET
                    is_active = true
                """,
                (int(user_id), int(role_id)),
            )

    conn.commit()

    student_id: int | None = None
    if student_code:
        student_id = _ensure_student_profile(conn, person_id=int(person_id), student_code=str(student_code))

    roles = _fetch_active_roles(conn, user_id=int(user_id))
    return {
        "username": username,
        "email_login": email_login,
        "user_id": int(user_id),
        "person_id": int(person_id),
        "student_id": (int(student_id) if student_id is not None else None),
        "roles": roles,
    }


def _fetch_active_roles(conn, *, user_id: int) -> list[str]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT r.role_code
            FROM identity.user_role ur
            JOIN identity.role r ON r.role_id = ur.role_id
            WHERE ur.user_id = %s
              AND coalesce(ur.is_active, true) = true
            ORDER BY r.role_code ASC
            """,
            (int(user_id),),
        )
        rows = cur.fetchall()
    return [str(row["role_code"]) for row in rows]


def _ensure_auth_principals(conn, *, issue_tokens: bool) -> dict[str, dict[str, Any]]:
    required_role_codes: list[str] = []
    for principal in CANONICAL_PRINCIPALS.values():
        for role_code in principal.get("roles", []):
            required_role_codes.append(str(role_code))

    role_ids = _ensure_role_ids(conn, required_role_codes)

    principals: dict[str, dict[str, Any]] = {}
    for key in ("admin", "owner", "non_owner"):
        principal = _ensure_canonical_principal(conn, principal=CANONICAL_PRINCIPALS[key], role_ids=role_ids)
        if issue_tokens:
            principal["access_token"] = TOKEN_SERVICE.create_access_token(
                {
                    "user_id": int(principal["user_id"]),
                    "username": str(principal["username"]),
                    "roles": list(principal["roles"]),
                }
            )
        principals[key] = principal

    return principals


def _ensure_minimal_delivery_assignment_for_student(
    conn,
    *,
    student_id: int,
    suffix: str,
    force_create: bool = False,
) -> int:
    def _ensure_minimal_class_section() -> int:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT class_section_id
                FROM academic.class_section
                WHERE status IN ('PLANNED', 'ACTIVE')
                ORDER BY class_section_id DESC
                LIMIT 1
                """,
            )
            existing_class = cur.fetchone()
            if existing_class is not None:
                return int(existing_class["class_section_id"])

            chain_suffix = f"{suffix}-{secrets.token_hex(4)}".upper()

            cur.execute(
                """
                INSERT INTO academic.department (
                    department_code,
                    department_name,
                    parent_department_id,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, NULL, 'ACTIVE', now(), now())
                RETURNING department_id
                """,
                (
                    f"UE2E_DEP_{chain_suffix}",
                    f"UE2E bootstrap department {suffix}",
                ),
            )
            department_row = cur.fetchone()
            if department_row is None:
                raise RuntimeError("Failed to insert bootstrap academic.department")

            cur.execute(
                """
                INSERT INTO academic.course (
                    department_id,
                    course_code,
                    course_name,
                    course_type,
                    credit,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, 'GENERAL', 3, 'ACTIVE', now(), now())
                RETURNING course_id
                """,
                (
                    int(department_row["department_id"]),
                    f"UE2E_COURSE_{chain_suffix}",
                    f"UE2E bootstrap course {suffix}",
                ),
            )
            course_row = cur.fetchone()
            if course_row is None:
                raise RuntimeError("Failed to insert bootstrap academic.course")

            cur.execute(
                """
                INSERT INTO academic.term (
                    term_code,
                    term_name,
                    start_date,
                    end_date,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, current_date - 30, current_date + 60, 'ACTIVE', now(), now())
                RETURNING term_id
                """,
                (
                    f"UE2E_TERM_{chain_suffix}",
                    f"UE2E bootstrap term {suffix}",
                ),
            )
            term_row = cur.fetchone()
            if term_row is None:
                raise RuntimeError("Failed to insert bootstrap academic.term")

            cur.execute(
                """
                INSERT INTO academic.course_offering (
                    course_id,
                    term_id,
                    offering_code,
                    coordinator_id,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, NULL, 'ACTIVE', now(), now())
                RETURNING course_offering_id
                """,
                (
                    int(course_row["course_id"]),
                    int(term_row["term_id"]),
                    f"UE2E_OFFER_{chain_suffix}",
                ),
            )
            offering_row = cur.fetchone()
            if offering_row is None:
                raise RuntimeError("Failed to insert bootstrap academic.course_offering")

            cur.execute(
                """
                INSERT INTO academic.class_section (
                    course_offering_id,
                    class_code,
                    class_name,
                    capacity,
                    delivery_mode,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, 100, 'LAB', 'ACTIVE', now(), now())
                RETURNING class_section_id
                """,
                (
                    int(offering_row["course_offering_id"]),
                    f"UE2E_CLASS_{chain_suffix}",
                    f"UE2E bootstrap class {suffix}",
                ),
            )
            class_row = cur.fetchone()
            if class_row is None:
                raise RuntimeError("Failed to insert bootstrap academic.class_section")

        conn.commit()
        return int(class_row["class_section_id"])

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT exam_assignment_id
            FROM delivery.exam_assignment
            WHERE student_id = %s
              AND assignment_status <> 'VOIDED'
            ORDER BY exam_assignment_id DESC
            LIMIT 1
            """,
            (int(student_id),),
        )
        existing = cur.fetchone()
        if existing is not None and not force_create:
            return int(existing["exam_assignment_id"])

        cur.execute(
            """
            SELECT assessment_type_id
            FROM assessment.assessment_type
            ORDER BY assessment_type_id ASC
            LIMIT 1
            """,
        )
        assessment_type_row = cur.fetchone()
        if assessment_type_row is None:
            raise RuntimeError("Cannot bootstrap delivery assignment: assessment.assessment_type is empty")

        class_section_id = _ensure_minimal_class_section()

        cur.execute(
            """
            SELECT user_id
            FROM identity.app_user
            ORDER BY user_id ASC
            LIMIT 1
            """,
        )
        created_by_row = cur.fetchone()
        if created_by_row is None:
            raise RuntimeError("Cannot bootstrap delivery assignment: identity.app_user is empty")
        created_by = int(created_by_row["user_id"])
        code_suffix = f"{suffix}-{secrets.token_hex(4)}".upper()

        cur.execute(
            """
            INSERT INTO assessment.exam (
                class_section_id,
                assessment_type_id,
                exam_code,
                exam_name,
                exam_status,
                created_by,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, 'ACTIVE', %s, now(), now())
            RETURNING exam_id
            """,
            (
                int(class_section_id),
                int(assessment_type_row["assessment_type_id"]),
                f"UE2E_BOOT_EXAM_{code_suffix}",
                f"UE2E bootstrap exam {suffix}",
                int(created_by),
            ),
        )
        exam_row = cur.fetchone()
        if exam_row is None:
            raise RuntimeError("Failed to insert bootstrap assessment.exam")

        cur.execute(
            """
            INSERT INTO assessment.exam_version (
                exam_id,
                version_no,
                version_label,
                duration_seconds,
                total_score,
                shuffle_questions,
                shuffle_options,
                randomization_mode,
                status,
                published_at,
                published_by,
                created_at,
                updated_at
            )
            VALUES (%s, 1, %s, 3600, 10.00, false, false, 'FIXED', 'PUBLISHED', now(), %s, now(), now())
            RETURNING exam_version_id
            """,
            (
                int(exam_row["exam_id"]),
                f"UE2E bootstrap version {suffix}",
                int(created_by),
            ),
        )
        version_row = cur.fetchone()
        if version_row is None:
            raise RuntimeError("Failed to insert bootstrap assessment.exam_version")

        cur.execute(
            """
            INSERT INTO delivery.exam_sitting (
                exam_version_id,
                sitting_code,
                sitting_name,
                scheduled_start_at,
                scheduled_end_at,
                sitting_status,
                created_by,
                created_at,
                updated_at
            )
            VALUES (
                %s,
                %s,
                %s,
                now() - interval '30 minute',
                now() + interval '90 minute',
                'READY',
                %s,
                now(),
                now()
            )
            RETURNING exam_sitting_id
            """,
            (
                int(version_row["exam_version_id"]),
                f"UE2E_BOOT_SIT_{code_suffix}",
                f"UE2E bootstrap sitting {suffix}",
                int(created_by),
            ),
        )
        sitting_row = cur.fetchone()
        if sitting_row is None:
            raise RuntimeError("Failed to insert bootstrap delivery.exam_sitting")

        cur.execute(
            """
            INSERT INTO delivery.exam_assignment (
                exam_sitting_id,
                student_id,
                assignment_status,
                assigned_at,
                assigned_by,
                note
            )
            VALUES (%s, %s, 'ASSIGNED', now(), %s, %s)
            RETURNING exam_assignment_id
            """,
            (
                int(sitting_row["exam_sitting_id"]),
                int(student_id),
                int(created_by),
                "UE2E bootstrap assignment",
            ),
        )
        assignment_row = cur.fetchone()
        if assignment_row is None:
            raise RuntimeError("Failed to insert bootstrap delivery.exam_assignment")

    conn.commit()
    return int(assignment_row["exam_assignment_id"])


def _assign_submission_owner_student(conn, *, exam_submission_id: int, owner_student_id: int) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT sess.exam_assignment_id
            FROM submission.exam_submission sub
            JOIN delivery.exam_session sess
              ON sess.exam_session_id = sub.exam_session_id
            WHERE sub.exam_submission_id = %s
            LIMIT 1
            """,
            (int(exam_submission_id),),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("Failed to resolve exam_assignment_id for seeded submission")

        exam_assignment_id = int(row["exam_assignment_id"])
        cur.execute(
            """
            UPDATE delivery.exam_assignment
            SET student_id = %s
            WHERE exam_assignment_id = %s
            """,
            (int(owner_student_id), exam_assignment_id),
        )

    conn.commit()
    return int(exam_assignment_id)


def _reset_seed_to_draft_submit_flow(
    conn,
    *,
    exam_session_id: int,
    exam_submission_id: int,
    submission_seal_id: int | None,
    grading_job_id: int | None,
    seeded_answer_text: str,
) -> None:
    with conn.cursor(row_factory=dict_row) as cur:
        if grading_job_id is not None:
            _execute_sql(
                cur,
                command="seed-submit-seal-flow",
                action="delete_submission_score",
                table="grading.submission_score",
                query="DELETE FROM grading.submission_score WHERE grading_job_id = %s",
                params=(int(grading_job_id),),
            )
            _execute_sql(
                cur,
                command="seed-submit-seal-flow",
                action="delete_question_score",
                table="grading.question_score",
                query="""
                DELETE FROM grading.question_score
                WHERE question_grading_task_id IN (
                    SELECT question_grading_task_id
                    FROM grading.question_grading_task
                    WHERE grading_job_id = %s
                )
                """,
                params=(int(grading_job_id),),
            )
            _execute_sql(
                cur,
                command="seed-submit-seal-flow",
                action="delete_expected_actual_comparison",
                table="grading.expected_actual_comparison",
                query="""
                DELETE FROM grading.expected_actual_comparison
                WHERE question_grading_task_id IN (
                    SELECT question_grading_task_id
                    FROM grading.question_grading_task
                    WHERE grading_job_id = %s
                )
                """,
                params=(int(grading_job_id),),
            )
            _execute_sql(
                cur,
                command="seed-submit-seal-flow",
                action="delete_actual_result",
                table="grading.actual_result",
                query="""
                DELETE FROM grading.actual_result
                WHERE question_grading_task_id IN (
                    SELECT question_grading_task_id
                    FROM grading.question_grading_task
                    WHERE grading_job_id = %s
                )
                """,
                params=(int(grading_job_id),),
            )
            _execute_sql(
                cur,
                command="seed-submit-seal-flow",
                action="delete_grading_event",
                table="grading.grading_event",
                query="DELETE FROM grading.grading_event WHERE grading_job_id = %s",
                params=(int(grading_job_id),),
            )
            _execute_sql(
                cur,
                command="seed-submit-seal-flow",
                action="delete_question_grading_task",
                table="grading.question_grading_task",
                query="DELETE FROM grading.question_grading_task WHERE grading_job_id = %s",
                params=(int(grading_job_id),),
            )
            _execute_sql(
                cur,
                command="seed-submit-seal-flow",
                action="delete_grading_run",
                table="grading.grading_run",
                query="DELETE FROM grading.grading_run WHERE grading_job_id = %s",
                params=(int(grading_job_id),),
            )
            _execute_sql(
                cur,
                command="seed-submit-seal-flow",
                action="delete_grading_job",
                table="grading.grading_job",
                query="DELETE FROM grading.grading_job WHERE grading_job_id = %s",
                params=(int(grading_job_id),),
            )

        if submission_seal_id is not None:
            _execute_sql(
                cur,
                command="seed-submit-seal-flow",
                action="delete_sealed_answer_by_seal",
                table="submission.sealed_answer",
                query="DELETE FROM submission.sealed_answer WHERE submission_seal_id = %s",
                params=(int(submission_seal_id),),
            )
            _execute_sql(
                cur,
                command="seed-submit-seal-flow",
                action="delete_submission_seal",
                table="submission.submission_seal",
                query="DELETE FROM submission.submission_seal WHERE submission_seal_id = %s",
                params=(int(submission_seal_id),),
            )
        else:
            _execute_sql(
                cur,
                command="seed-submit-seal-flow",
                action="delete_sealed_answer_by_submission",
                table="submission.sealed_answer",
                query="DELETE FROM submission.sealed_answer WHERE exam_submission_id = %s",
                params=(int(exam_submission_id),),
            )
            _execute_sql(
                cur,
                command="seed-submit-seal-flow",
                action="delete_submission_seal_by_submission",
                table="submission.submission_seal",
                query="DELETE FROM submission.submission_seal WHERE exam_submission_id = %s",
                params=(int(exam_submission_id),),
            )

        _execute_sql(
            cur,
            command="seed-submit-seal-flow",
            action="set_answer_state_draft",
            table="submission.answer_state",
            query="""
            UPDATE submission.answer_state
            SET
                answer_status = 'DRAFT',
                answer_text = %s,
                answer_length = %s,
                client_version = 1,
                server_version = 1,
                client_saved_at = now(),
                last_saved_at = now()
            WHERE exam_submission_id = %s
            """,
            params=(
                str(seeded_answer_text),
                len(str(seeded_answer_text)),
                int(exam_submission_id),
            ),
        )

        _execute_sql(
            cur,
            command="seed-submit-seal-flow",
            action="set_submission_draft",
            table="submission.exam_submission",
            query="""
            UPDATE submission.exam_submission
            SET
                submission_status = 'DRAFT',
                opened_at = coalesce(opened_at, now()),
                first_saved_at = coalesce(first_saved_at, now()),
                last_saved_at = now(),
                submitted_at = NULL,
                sealed_at = NULL,
                seal_reason = NULL,
                updated_at = now()
            WHERE exam_submission_id = %s
            """,
            params=(int(exam_submission_id),),
        )

    conn.commit()


def _seed_textbox(suffix: str) -> dict[str, Any]:
    prefix = f"ue2e-textbox-{suffix}"
    with open_maintenance_connection() as conn:
        principals = _ensure_auth_principals(conn, issue_tokens=False)
        owner = principals["owner"]
        non_owner = principals["non_owner"]

        owner_student_id = owner.get("student_id")
        if owner_student_id is None:
            raise RuntimeError("Canonical owner principal is missing student_id")

        _ensure_minimal_delivery_assignment_for_student(
            conn,
            student_id=int(owner_student_id),
            suffix=str(suffix),
            force_create=True,
        )

        seed = create_s2w7_textbox_sql_seed_graph(
            conn=conn,
            suffix=suffix,
            sealed_answer_sql="SELECT 1 AS value UNION ALL SELECT 2 AS value ORDER BY value",
            answer_state_sql="SELECT 999 AS value",
            expected_rows=[[1], [2]],
        )
        _retag_seed_records(conn, command="seed-textbox", seed=seed, prefix=prefix, suffix=suffix)

        exam_assignment_id = _assign_submission_owner_student(
            conn,
            exam_submission_id=int(seed["exam_submission_id"]),
            owner_student_id=int(owner_student_id),
        )

    return {
        "scenario": "textbox",
        "prefix": prefix,
        "exam_submission_id": int(seed["exam_submission_id"]),
        "exam_assignment_id": int(exam_assignment_id),
        "owner_student_id": int(owner["student_id"]),
        "owner_user_id": int(owner["user_id"]),
        "non_owner_student_id": int(non_owner["student_id"]),
        "non_owner_user_id": int(non_owner["user_id"]),
        "auth_mode": "bearer",
    }


def _seed_capture_failure(suffix: str) -> dict[str, Any]:
    prefix = f"ue2e-failure-{suffix}"
    with open_maintenance_connection() as conn:
        principals = _ensure_auth_principals(conn, issue_tokens=False)
        owner = principals["owner"]
        non_owner = principals["non_owner"]

        owner_student_id = owner.get("student_id")
        if owner_student_id is None:
            raise RuntimeError("Canonical owner principal is missing student_id")

        _ensure_minimal_delivery_assignment_for_student(
            conn,
            student_id=int(owner_student_id),
            suffix=str(suffix),
        )

        seed = create_s2w7_capture_seed_graph(
            conn=conn,
            suffix=suffix,
            profile_answer_language="OTHER",
            required_capture_type="POSTGRES_DATABASE_SNAPSHOT",
            capture_job_type="STUDENT_DATABASE_SNAPSHOT",
        )
        _retag_seed_records(conn, command="seed-capture-failure", seed=seed, prefix=prefix, suffix=suffix)
        _mark_capture_failed(conn, command="seed-capture-failure", capture_job_id=int(seed["capture_job_id"]))

        exam_assignment_id = _assign_submission_owner_student(
            conn,
            exam_submission_id=int(seed["exam_submission_id"]),
            owner_student_id=int(owner_student_id),
        )

    return {
        "scenario": "capture_failure",
        "prefix": prefix,
        "exam_submission_id": int(seed["exam_submission_id"]),
        "exam_assignment_id": int(exam_assignment_id),
        "owner_student_id": int(owner["student_id"]),
        "owner_user_id": int(owner["user_id"]),
        "non_owner_student_id": int(non_owner["student_id"]),
        "non_owner_user_id": int(non_owner["user_id"]),
        "auth_mode": "bearer",
    }


def _seed_submit_seal_flow(suffix: str) -> dict[str, Any]:
    prefix = f"ue2e-submit-seal-{suffix}"
    seeded_answer_text = "SELECT 42 AS value"

    with open_maintenance_connection() as conn:
        principals = _ensure_auth_principals(conn, issue_tokens=False)
        owner = principals["owner"]
        non_owner = principals["non_owner"]

        owner_student_id = owner.get("student_id")
        if owner_student_id is None:
            raise RuntimeError("Canonical owner principal is missing student_id")

        _ensure_minimal_delivery_assignment_for_student(
            conn,
            student_id=int(owner_student_id),
            suffix=str(suffix),
        )

        seed = create_s2w7_textbox_sql_seed_graph(
            conn=conn,
            suffix=suffix,
            sealed_answer_sql="SELECT 1 AS value UNION ALL SELECT 2 AS value ORDER BY value",
            answer_state_sql=seeded_answer_text,
            expected_rows=[[1], [2]],
        )
        _retag_seed_records(conn, command="seed-submit-seal-flow", seed=seed, prefix=prefix, suffix=suffix)

        with conn.cursor(row_factory=dict_row) as cur:
            _execute_sql(
                cur,
                command="seed-submit-seal-flow",
                action="bind_profile_exam_version",
                table="assessment.question_grading_profile",
                query="""
                UPDATE assessment.question_grading_profile qgp
                SET exam_version_id = gei.exam_version_id
                FROM delivery.generated_exam_instance gei
                WHERE qgp.question_grading_profile_id = %s
                  AND gei.generated_exam_instance_id = %s
                """,
                params=(
                    int(seed["question_grading_profile_id"]),
                    int(seed["generated_exam_instance_id"]),
                ),
            )
        conn.commit()

        exam_assignment_id = _assign_submission_owner_student(
            conn,
            exam_submission_id=int(seed["exam_submission_id"]),
            owner_student_id=int(owner_student_id),
        )

        _reset_seed_to_draft_submit_flow(
            conn,
            exam_session_id=int(seed["exam_session_id"]),
            exam_submission_id=int(seed["exam_submission_id"]),
            submission_seal_id=(int(seed["submission_seal_id"]) if seed.get("submission_seal_id") else None),
            grading_job_id=(int(seed["grading_job_id"]) if seed.get("grading_job_id") else None),
            seeded_answer_text=seeded_answer_text,
        )

    return {
        "scenario": "submit_seal_flow",
        "prefix": prefix,
        "exam_session_id": int(seed["exam_session_id"]),
        "exam_submission_id": int(seed["exam_submission_id"]),
        "exam_assignment_id": int(exam_assignment_id),
        "owner_student_id": int(owner["student_id"]),
        "owner_user_id": int(owner["user_id"]),
        "non_owner_student_id": int(non_owner["student_id"]),
        "non_owner_user_id": int(non_owner["user_id"]),
        "submission_status": "DRAFT",
        "seeded_answer_text": seeded_answer_text,
        "auth_mode": "bearer",
    }


def _enqueue_grading_job_for_submission(*, submission_id: int, prefix: str) -> dict[str, Any]:
    with open_maintenance_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            _execute_sql(
                cur,
                command="enqueue-grading-for-submission",
                action="select_submission_for_grading_enqueue",
                table="submission.exam_submission",
                query="""
                SELECT
                    sub.exam_submission_id,
                    sub.exam_session_id,
                    sub.generated_exam_instance_id,
                    ss.submission_seal_id
                FROM submission.exam_submission sub
                LEFT JOIN submission.submission_seal ss
                    ON ss.exam_submission_id = sub.exam_submission_id
                   AND ss.seal_status = 'SEALED'
                WHERE sub.exam_submission_id = %s
                LIMIT 1
                """,
                params=(int(submission_id),),
            )
            row = cur.fetchone()
            if row is None:
                raise RuntimeError(f"Submission not found for grading enqueue: {int(submission_id)}")

            submission_seal_id = row.get("submission_seal_id")
            if submission_seal_id is None:
                raise RuntimeError("Cannot enqueue grading job: submission is not sealed")

            _execute_sql(
                cur,
                command="enqueue-grading-for-submission",
                action="insert_grading_job",
                table="grading.grading_job",
                query="""
                INSERT INTO grading.grading_job (
                    exam_submission_id,
                    submission_seal_id,
                    exam_session_id,
                    generated_exam_instance_id,
                    grading_mode,
                    grading_status,
                    idempotency_key,
                    requested_at,
                    attempt_count,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    'AUTO',
                    'QUEUED',
                    %s,
                    now(),
                    0,
                    %s,
                    now(),
                    now()
                )
                RETURNING grading_job_id
                """,
                params=(
                    int(row["exam_submission_id"]),
                    int(submission_seal_id),
                    int(row["exam_session_id"]),
                    int(row["generated_exam_instance_id"]),
                    f"{prefix}-grading-job-{int(submission_id)}",
                    Jsonb({"source": prefix}),
                ),
            )
            job_row = cur.fetchone()
            if job_row is None:
                raise RuntimeError("Failed to enqueue grading job")

        conn.commit()

    return {
        "scenario": "enqueue_grading_for_submission",
        "prefix": prefix,
        "exam_submission_id": int(submission_id),
        "grading_job_id": int(job_row["grading_job_id"]),
    }


def _count_matching_accounts(conn, patterns: list[str]) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT count(DISTINCT u.user_id) AS matched
            FROM identity.app_user u
            LEFT JOIN identity.person p ON p.person_id = u.person_id
            LEFT JOIN identity.student_profile sp ON sp.person_id = u.person_id
            WHERE u.username ILIKE ANY(%s)
               OR coalesce(u.email_login, '') ILIKE ANY(%s)
               OR coalesce(sp.student_code, '') ILIKE ANY(%s)
               OR coalesce(p.full_name, '') ILIKE ANY(%s)
            """,
            (patterns, patterns, patterns, patterns),
        )
        row = cur.fetchone()
    return int(row["matched"] if row is not None else 0)


def _select_auth_junk_candidates(conn) -> list[dict[str, Any]]:
    canonical_usernames = [
        str(CANONICAL_PRINCIPALS["admin"]["username"]),
        str(CANONICAL_PRINCIPALS["owner"]["username"]),
        str(CANONICAL_PRINCIPALS["non_owner"]["username"]),
    ]
    username_patterns = [pattern for patterns in KNOWN_TEST_PREFIXES.values() for pattern in patterns]
    student_code_patterns = [
        "UE2E-%",
        "UE2E_%",
        "S2W-%",
        "S2W_%",
        "TEST-%",
        "TEST_%",
        "CODEX-%",
        "CODEX_%",
    ]

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                u.user_id,
                u.username,
                u.user_status,
                u.email_login,
                p.full_name,
                sp.student_id,
                sp.student_code
            FROM identity.app_user u
            LEFT JOIN identity.person p ON p.person_id = u.person_id
            LEFT JOIN identity.student_profile sp ON sp.person_id = u.person_id
            WHERE u.username <> ALL(%s)
              AND (
                u.username ILIKE ANY(%s)
                OR coalesce(u.email_login, '') ILIKE ANY(%s)
                OR coalesce(sp.student_code, '') ILIKE ANY(%s)
                OR coalesce(p.full_name, '') ILIKE ANY(%s)
              )
            ORDER BY u.user_id ASC
            """,
            (
                canonical_usernames,
                username_patterns,
                AUTH_JUNK_EMAIL_PATTERNS,
                student_code_patterns,
                AUTH_JUNK_FULL_NAME_PATTERNS,
            ),
        )
        rows = cur.fetchall()

    return [
        {
            "user_id": int(row["user_id"]),
            "username": str(row["username"]),
            "user_status": str(row["user_status"]),
            "email_login": (str(row["email_login"]) if row.get("email_login") else None),
            "full_name": (str(row["full_name"]) if row.get("full_name") else None),
            "student_id": (int(row["student_id"]) if row.get("student_id") is not None else None),
            "student_code": (str(row["student_code"]) if row.get("student_code") else None),
        }
        for row in rows
    ]


def _audit_auth_junk(conn) -> dict[str, Any]:
    prefix_counts: dict[str, int] = {}
    for key, patterns in KNOWN_TEST_PREFIXES.items():
        prefix_counts[key] = _count_matching_accounts(conn, patterns)

    canonical_usernames = [
        str(CANONICAL_PRINCIPALS["admin"]["username"]),
        str(CANONICAL_PRINCIPALS["owner"]["username"]),
        str(CANONICAL_PRINCIPALS["non_owner"]["username"]),
    ]

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) AS total_users FROM identity.app_user")
        total_row = cur.fetchone()

        cur.execute(
            """
            SELECT
                u.username,
                u.user_id,
                u.person_id,
                u.user_status,
                sp.student_id,
                sp.student_code,
                coalesce(array_agg(DISTINCT r.role_code) FILTER (WHERE r.role_code IS NOT NULL), ARRAY[]::text[]) AS roles
            FROM identity.app_user u
            LEFT JOIN identity.student_profile sp ON sp.person_id = u.person_id
            LEFT JOIN identity.user_role ur ON ur.user_id = u.user_id AND coalesce(ur.is_active, true) = true
            LEFT JOIN identity.role r ON r.role_id = ur.role_id
            WHERE u.username = ANY(%s)
            GROUP BY u.username, u.user_id, u.person_id, u.user_status, sp.student_id, sp.student_code
            ORDER BY u.username ASC
            """,
            (canonical_usernames,),
        )
        canonical_rows = cur.fetchall()

    canonical_map: dict[str, dict[str, Any]] = {}
    row_by_username = {str(row["username"]): row for row in canonical_rows}
    for principal in ("admin", "owner", "non_owner"):
        username = str(CANONICAL_PRINCIPALS[principal]["username"])
        row = row_by_username.get(username)
        if row is None:
            canonical_map[username] = {
                "exists": False,
                "user_id": None,
                "person_id": None,
                "student_id": None,
                "student_code": None,
                "roles": [],
                "user_status": None,
            }
            continue

        canonical_map[username] = {
            "exists": True,
            "user_id": int(row["user_id"]),
            "person_id": int(row["person_id"]),
            "student_id": (int(row["student_id"]) if row.get("student_id") is not None else None),
            "student_code": (str(row["student_code"]) if row.get("student_code") else None),
            "roles": [str(item) for item in (row.get("roles") or [])],
            "user_status": str(row["user_status"]),
        }

    junk_candidates = _select_auth_junk_candidates(conn)
    return {
        "scenario": "audit_auth_junk",
        "known_test_prefix_counts": prefix_counts,
        "canonical_accounts": canonical_map,
        "junk_candidate_count": len(junk_candidates),
        "junk_candidate_usernames": [item["username"] for item in junk_candidates[:50]],
        "total_app_users": int(total_row["total_users"] if total_row is not None else 0),
    }


def _cleanup_auth_junk(conn, *, apply: bool) -> dict[str, Any]:
    candidates = _select_auth_junk_candidates(conn)
    candidate_ids = [int(item["user_id"]) for item in candidates]

    already_disabled = sum(1 for item in candidates if str(item["user_status"]).upper() == "DISABLED")
    changed = 0
    if apply and candidate_ids:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                UPDATE identity.app_user
                SET user_status = 'DISABLED', updated_at = now()
                WHERE user_id = ANY(%s)
                  AND user_status <> 'DISABLED'
                """,
                (candidate_ids,),
            )
            changed = int(cur.rowcount or 0)
        conn.commit()

    return {
        "scenario": "cleanup_auth_junk",
        "dry_run": (not apply),
        "apply": bool(apply),
        "candidate_count": len(candidates),
        "already_disabled_count": int(already_disabled),
        "changed_count": int(changed),
        "counts_by_table": {
            "identity.app_user": int(changed),
        },
        "candidate_usernames": [item["username"] for item in candidates[:50]],
    }


def _schema_check(conn) -> dict[str, Any]:
    def _entry(*, schema: str, table: str, cleanup_strategy: str) -> dict[str, Any]:
        exists = _table_exists(conn, schema, table)
        metadata_json = _table_has_column(conn, schema, table, "metadata_json") if exists else False
        return {
            "exists": bool(exists),
            "metadata_json": bool(metadata_json),
            "cleanup_strategy": cleanup_strategy,
        }

    return {
        "scenario": "schema_check",
        "assessment.question_template": _entry(
            schema="assessment",
            table="question_template",
            cleanup_strategy="template_code_prefix",
        ),
        "delivery.generated_exam_question": _entry(
            schema="delivery",
            table="generated_exam_question",
            cleanup_strategy="metadata_or_question_code_prefix",
        ),
        "submission.submission_seal": _entry(
            schema="submission",
            table="submission_seal",
            cleanup_strategy="seal_idempotency_key_or_metadata",
        ),
        "grading.grading_job": _entry(
            schema="grading",
            table="grading_job",
            cleanup_strategy="idempotency_key_or_metadata_or_submission_link",
        ),
    }


def _seed_auth_principals(*, emit_tokens: bool, env: dict[str, str] | None = None) -> dict[str, Any]:
    validate_emit_request(emit_tokens=emit_tokens, env=(env or os.environ))

    with open_maintenance_connection() as conn:
        principals = _ensure_auth_principals(conn, issue_tokens=True)

    return build_seed_auth_payload(principals=principals, emit_tokens=emit_tokens)


def _cleanup_ue2e(conn, *, command: str, prefix: str) -> dict[str, int]:
    pattern = f"{prefix}%"
    template_code_pattern = "UE2E_QT_%"
    question_code_pattern = "UE2E_Q_%"

    for known_seed_prefix in ("ue2e-textbox-", "ue2e-failure-"):
        if prefix.startswith(known_seed_prefix):
            scoped_suffix = prefix[len(known_seed_prefix):].strip()
            if scoped_suffix:
                template_code_pattern = f"UE2E_QT_{scoped_suffix}%"
                question_code_pattern = f"UE2E_Q_{scoped_suffix}%"
            break

    has_submission_seal_metadata = _table_has_column(conn, "submission", "submission_seal", "metadata_json")
    has_exam_submission_metadata = _table_has_column(conn, "submission", "exam_submission", "metadata_json")
    has_grading_job_metadata = _table_has_column(conn, "grading", "grading_job", "metadata_json")
    has_capture_job_metadata = _table_has_column(conn, "capture", "capture_job", "metadata_json")
    has_profile_metadata = _table_has_column(conn, "assessment", "question_grading_profile", "metadata_json")
    has_generated_question_metadata = _table_has_column(conn, "delivery", "generated_exam_question", "metadata_json")
    has_template_metadata = _table_has_column(conn, "assessment", "question_template", "metadata_json")

    def _to_ids(rows, key):
        return [int(row[key]) for row in rows if row.get(key) is not None]

    with conn.cursor(row_factory=dict_row) as cur:
        seal_filters: list[str] = ["ss.seal_idempotency_key ILIKE %s"]
        seal_params: list[Any] = [pattern]
        if has_submission_seal_metadata:
            seal_filters.append("coalesce(ss.metadata_json ->> 'source', '') ILIKE %s")
            seal_params.append(pattern)
        _execute_sql(
            cur,
            command=command,
            action="select_submission_seals",
            table="submission.submission_seal",
            query=f"""
            SELECT ss.submission_seal_id, ss.exam_submission_id
            FROM submission.submission_seal ss
            WHERE {' OR '.join(seal_filters)}
            """,
            params=tuple(seal_params),
        )
        seal_rows = cur.fetchall()
        submission_ids = _to_ids(seal_rows, "exam_submission_id")
        seal_ids = _to_ids(seal_rows, "submission_seal_id")

        if has_exam_submission_metadata:
            _execute_sql(
                cur,
                command=command,
                action="select_exam_submissions",
                table="submission.exam_submission",
                query="""
                SELECT es.exam_submission_id
                FROM submission.exam_submission es
                WHERE coalesce(es.metadata_json ->> 'source', '') ILIKE %s
                """,
                params=(pattern,),
            )
            submission_rows = cur.fetchall()
            submission_ids.extend(_to_ids(submission_rows, "exam_submission_id"))

        submission_ids = sorted(set(submission_ids))

        grading_filters: list[str] = ["gj.idempotency_key ILIKE %s"]
        grading_params: list[Any] = [pattern]
        if submission_ids:
            grading_filters.append("gj.exam_submission_id = ANY(%s)")
            grading_params.append(submission_ids)
        if has_grading_job_metadata:
            grading_filters.append("coalesce(gj.metadata_json ->> 'source', '') ILIKE %s")
            grading_params.append(pattern)
        _execute_sql(
            cur,
            command=command,
            action="select_grading_jobs",
            table="grading.grading_job",
            query=f"""
            SELECT gj.grading_job_id
            FROM grading.grading_job gj
            WHERE {' OR '.join(grading_filters)}
            """,
            params=tuple(grading_params),
        )
        grading_job_ids = _to_ids(cur.fetchall(), "grading_job_id")

        capture_filters: list[str] = ["cj.idempotency_key ILIKE %s"]
        capture_params: list[Any] = [pattern]
        if submission_ids:
            capture_filters.append("cj.exam_submission_id = ANY(%s)")
            capture_params.append(submission_ids)
        if has_capture_job_metadata:
            capture_filters.append("coalesce(cj.metadata_json ->> 'source', '') ILIKE %s")
            capture_params.append(pattern)
        _execute_sql(
            cur,
            command=command,
            action="select_capture_jobs",
            table="capture.capture_job",
            query=f"""
            SELECT cj.capture_job_id
            FROM capture.capture_job cj
            WHERE {' OR '.join(capture_filters)}
            """,
            params=tuple(capture_params),
        )
        capture_job_ids = _to_ids(cur.fetchall(), "capture_job_id")

        if grading_job_ids:
            _execute_sql(
                cur,
                command=command,
                action="select_question_grading_tasks",
                table="grading.question_grading_task",
                query="""
                SELECT qgt.question_grading_task_id
                FROM grading.question_grading_task qgt
                WHERE qgt.grading_job_id = ANY(%s)
                """,
                params=(grading_job_ids,),
            )
            task_ids = _to_ids(cur.fetchall(), "question_grading_task_id")
        else:
            task_ids = []

        template_filters: list[str] = ["qt.template_code ILIKE %s"]
        template_params: list[Any] = [template_code_pattern]
        if has_template_metadata:
            template_filters.append("coalesce(qt.metadata_json ->> 'source', '') ILIKE %s")
            template_params.append(pattern)
        _execute_sql(
            cur,
            command=command,
            action="select_question_templates",
            table="assessment.question_template",
            query=f"""
            SELECT qt.question_template_id
            FROM assessment.question_template qt
            WHERE {' OR '.join(template_filters)}
            """,
            params=tuple(template_params),
        )
        template_ids = _to_ids(cur.fetchall(), "question_template_id")

        generated_filters: list[str] = ["geq.question_code ILIKE %s"]
        generated_params: list[Any] = [question_code_pattern]
        if template_ids:
            generated_filters.append("geq.question_template_id = ANY(%s)")
            generated_params.append(template_ids)
        if has_generated_question_metadata:
            generated_filters.append("coalesce(geq.metadata_json ->> 'source', '') ILIKE %s")
            generated_params.append(pattern)
        _execute_sql(
            cur,
            command=command,
            action="select_generated_exam_questions",
            table="delivery.generated_exam_question",
            query=f"""
            SELECT geq.generated_exam_question_id
            FROM delivery.generated_exam_question geq
            WHERE {' OR '.join(generated_filters)}
            """,
            params=tuple(generated_params),
        )
        generated_question_ids = _to_ids(cur.fetchall(), "generated_exam_question_id")

        profile_filters: list[str] = []
        profile_params: list[Any] = []
        if template_ids:
            profile_filters.append("qgp.question_template_id = ANY(%s)")
            profile_params.append(template_ids)
        if has_profile_metadata:
            profile_filters.append("coalesce(qgp.metadata_json ->> 'source', '') ILIKE %s")
            profile_params.append(pattern)
        if profile_filters:
            _execute_sql(
                cur,
                command=command,
                action="select_question_grading_profiles",
                table="assessment.question_grading_profile",
                query=f"""
                SELECT qgp.question_grading_profile_id
                FROM assessment.question_grading_profile qgp
                WHERE {' OR '.join(profile_filters)}
                """,
                params=tuple(profile_params),
            )
            profile_ids = _to_ids(cur.fetchall(), "question_grading_profile_id")
        else:
            profile_ids = []

        deleted: dict[str, int] = {}

        if grading_job_ids:
            _execute_sql(
                cur,
                command=command,
                action="delete_submission_score",
                table="grading.submission_score",
                query="DELETE FROM grading.submission_score WHERE grading_job_id = ANY(%s)",
                params=(grading_job_ids,),
            )
            deleted["submission_score"] = int(cur.rowcount or 0)

        if task_ids:
            _execute_sql(
                cur,
                command=command,
                action="delete_question_score",
                table="grading.question_score",
                query="DELETE FROM grading.question_score WHERE question_grading_task_id = ANY(%s)",
                params=(task_ids,),
            )
            deleted["question_score"] = int(cur.rowcount or 0)

            _execute_sql(
                cur,
                command=command,
                action="delete_expected_actual_comparison",
                table="grading.expected_actual_comparison",
                query="DELETE FROM grading.expected_actual_comparison WHERE question_grading_task_id = ANY(%s)",
                params=(task_ids,),
            )
            deleted["expected_actual_comparison"] = int(cur.rowcount or 0)

            _execute_sql(
                cur,
                command=command,
                action="delete_actual_result",
                table="grading.actual_result",
                query="DELETE FROM grading.actual_result WHERE question_grading_task_id = ANY(%s)",
                params=(task_ids,),
            )
            deleted["actual_result"] = int(cur.rowcount or 0)

        if grading_job_ids:
            _execute_sql(
                cur,
                command=command,
                action="delete_grading_event",
                table="grading.grading_event",
                query="DELETE FROM grading.grading_event WHERE grading_job_id = ANY(%s)",
                params=(grading_job_ids,),
            )
            deleted["grading_event"] = int(cur.rowcount or 0)

            _execute_sql(
                cur,
                command=command,
                action="delete_question_grading_task",
                table="grading.question_grading_task",
                query="DELETE FROM grading.question_grading_task WHERE grading_job_id = ANY(%s)",
                params=(grading_job_ids,),
            )
            deleted["question_grading_task"] = int(cur.rowcount or 0)

            _execute_sql(
                cur,
                command=command,
                action="delete_grading_run",
                table="grading.grading_run",
                query="DELETE FROM grading.grading_run WHERE grading_job_id = ANY(%s)",
                params=(grading_job_ids,),
            )
            deleted["grading_run"] = int(cur.rowcount or 0)

            _execute_sql(
                cur,
                command=command,
                action="delete_grading_job",
                table="grading.grading_job",
                query="DELETE FROM grading.grading_job WHERE grading_job_id = ANY(%s)",
                params=(grading_job_ids,),
            )
            deleted["grading_job"] = int(cur.rowcount or 0)

        if capture_job_ids:
            _execute_sql(
                cur,
                command=command,
                action="delete_capture_dataset_row",
                table="capture.capture_dataset_row",
                query="""
                DELETE FROM capture.capture_dataset_row
                WHERE capture_dataset_id IN (
                    SELECT capture_dataset_id
                    FROM capture.capture_dataset
                    WHERE capture_job_id = ANY(%s)
                )
                """,
                params=(capture_job_ids,),
            )
            deleted["capture_dataset_row"] = int(cur.rowcount or 0)

            _execute_sql(
                cur,
                command=command,
                action="delete_capture_dataset",
                table="capture.capture_dataset",
                query="DELETE FROM capture.capture_dataset WHERE capture_job_id = ANY(%s)",
                params=(capture_job_ids,),
            )
            deleted["capture_dataset"] = int(cur.rowcount or 0)

            _execute_sql(
                cur,
                command=command,
                action="delete_capture_artifact",
                table="capture.capture_artifact",
                query="DELETE FROM capture.capture_artifact WHERE capture_job_id = ANY(%s)",
                params=(capture_job_ids,),
            )
            deleted["capture_artifact"] = int(cur.rowcount or 0)

            _execute_sql(
                cur,
                command=command,
                action="delete_capture_job_event",
                table="capture.capture_job_event",
                query="DELETE FROM capture.capture_job_event WHERE capture_job_id = ANY(%s)",
                params=(capture_job_ids,),
            )
            deleted["capture_job_event"] = int(cur.rowcount or 0)

            _execute_sql(
                cur,
                command=command,
                action="delete_capture_job",
                table="capture.capture_job",
                query="DELETE FROM capture.capture_job WHERE capture_job_id = ANY(%s)",
                params=(capture_job_ids,),
            )
            deleted["capture_job"] = int(cur.rowcount or 0)

        if submission_ids:
            _execute_sql(
                cur,
                command=command,
                action="delete_submission_dispatch_outcome",
                table="submission.submission_dispatch_outcome",
                query="DELETE FROM submission.submission_dispatch_outcome WHERE exam_submission_id = ANY(%s)",
                params=(submission_ids,),
            )
            deleted["submission_dispatch_outcome"] = int(cur.rowcount or 0)

            _execute_sql(
                cur,
                command=command,
                action="delete_answer_save_item",
                table="submission.answer_save_item",
                query="""
                DELETE FROM submission.answer_save_item
                WHERE answer_save_batch_id IN (
                    SELECT answer_save_batch_id
                    FROM submission.answer_save_batch
                    WHERE exam_submission_id = ANY(%s)
                )
                """,
                params=(submission_ids,),
            )
            deleted["answer_save_item"] = int(cur.rowcount or 0)

            _execute_sql(
                cur,
                command=command,
                action="delete_answer_save_batch",
                table="submission.answer_save_batch",
                query="DELETE FROM submission.answer_save_batch WHERE exam_submission_id = ANY(%s)",
                params=(submission_ids,),
            )
            deleted["answer_save_batch"] = int(cur.rowcount or 0)

            _execute_sql(
                cur,
                command=command,
                action="delete_sealed_answer_by_submission",
                table="submission.sealed_answer",
                query="DELETE FROM submission.sealed_answer WHERE exam_submission_id = ANY(%s)",
                params=(submission_ids,),
            )
            deleted["sealed_answer_by_submission"] = int(cur.rowcount or 0)

            _execute_sql(
                cur,
                command=command,
                action="delete_answer_state",
                table="submission.answer_state",
                query="DELETE FROM submission.answer_state WHERE exam_submission_id = ANY(%s)",
                params=(submission_ids,),
            )
            deleted["answer_state"] = int(cur.rowcount or 0)

            _execute_sql(
                cur,
                command=command,
                action="delete_submission_seal_by_submission",
                table="submission.submission_seal",
                query="DELETE FROM submission.submission_seal WHERE exam_submission_id = ANY(%s)",
                params=(submission_ids,),
            )
            deleted["submission_seal_by_submission"] = int(cur.rowcount or 0)

            _execute_sql(
                cur,
                command=command,
                action="delete_exam_submission",
                table="submission.exam_submission",
                query="DELETE FROM submission.exam_submission WHERE exam_submission_id = ANY(%s)",
                params=(submission_ids,),
            )
            deleted["exam_submission"] = int(cur.rowcount or 0)

        if seal_ids:
            _execute_sql(
                cur,
                command=command,
                action="delete_sealed_answer_by_seal",
                table="submission.sealed_answer",
                query="DELETE FROM submission.sealed_answer WHERE submission_seal_id = ANY(%s)",
                params=(seal_ids,),
            )
            deleted["sealed_answer_by_seal"] = int(cur.rowcount or 0)

        if generated_question_ids:
            _execute_sql(
                cur,
                command=command,
                action="delete_sealed_answer_by_generated_question",
                table="submission.sealed_answer",
                query="DELETE FROM submission.sealed_answer WHERE generated_exam_question_id = ANY(%s)",
                params=(generated_question_ids,),
            )
            deleted["sealed_answer_by_generated_question"] = int(cur.rowcount or 0)

            _execute_sql(
                cur,
                command=command,
                action="delete_answer_state_by_generated_question",
                table="submission.answer_state",
                query="DELETE FROM submission.answer_state WHERE generated_exam_question_id = ANY(%s)",
                params=(generated_question_ids,),
            )
            deleted["answer_state_by_generated_question"] = int(cur.rowcount or 0)

            _execute_sql(
                cur,
                command=command,
                action="delete_generated_expected_answer",
                table="delivery.generated_expected_answer",
                query="DELETE FROM delivery.generated_expected_answer WHERE generated_exam_question_id = ANY(%s)",
                params=(generated_question_ids,),
            )
            deleted["generated_expected_answer"] = int(cur.rowcount or 0)

            _execute_sql(
                cur,
                command=command,
                action="delete_generated_exam_question",
                table="delivery.generated_exam_question",
                query="DELETE FROM delivery.generated_exam_question WHERE generated_exam_question_id = ANY(%s)",
                params=(generated_question_ids,),
            )
            deleted["generated_exam_question"] = int(cur.rowcount or 0)

        if profile_ids:
            _execute_sql(
                cur,
                command=command,
                action="delete_question_grading_profile",
                table="assessment.question_grading_profile",
                query="DELETE FROM assessment.question_grading_profile WHERE question_grading_profile_id = ANY(%s)",
                params=(profile_ids,),
            )
            deleted["question_grading_profile"] = int(cur.rowcount or 0)

        if template_ids:
            _execute_sql(
                cur,
                command=command,
                action="delete_question_template",
                table="assessment.question_template",
                query="DELETE FROM assessment.question_template WHERE question_template_id = ANY(%s)",
                params=(template_ids,),
            )
            deleted["question_template"] = int(cur.rowcount or 0)

    conn.commit()
    return deleted


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description="UE2E seed helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    seed_textbox = subparsers.add_parser("seed-textbox")
    seed_textbox.add_argument("--suffix", required=True)

    seed_capture_failure = subparsers.add_parser("seed-capture-failure")
    seed_capture_failure.add_argument("--suffix", required=True)

    seed_submit_seal_flow = subparsers.add_parser("seed-submit-seal-flow")
    seed_submit_seal_flow.add_argument("--suffix", required=True)

    enqueue_grading = subparsers.add_parser("enqueue-grading-for-submission")
    enqueue_grading.add_argument("--submission-id", type=int, required=True)
    enqueue_grading.add_argument("--prefix", required=True)

    cleanup = subparsers.add_parser("cleanup")
    cleanup.add_argument("--prefix", default="ue2e-")

    subparsers.add_parser("schema-check")

    subparsers.add_parser("audit-auth-junk")
    seed_auth_principals = subparsers.add_parser("seed-auth-principals")
    seed_auth_principals.add_argument("--emit-tokens", action="store_true")

    cleanup_auth_junk = subparsers.add_parser("cleanup-auth-junk")
    cleanup_auth_junk.add_argument("--apply", action="store_true")

    args = parser.parse_args()

    try:
        if args.command == "seed-textbox":
            _emit(_seed_textbox(str(args.suffix).strip()))
            return 0

        if args.command == "seed-capture-failure":
            _emit(_seed_capture_failure(str(args.suffix).strip()))
            return 0

        if args.command == "seed-submit-seal-flow":
            _emit(_seed_submit_seal_flow(str(args.suffix).strip()))
            return 0

        if args.command == "enqueue-grading-for-submission":
            _emit(
                _enqueue_grading_job_for_submission(
                    submission_id=int(args.submission_id),
                    prefix=str(args.prefix).strip(),
                )
            )
            return 0

        if args.command == "cleanup":
            prefix = str(args.prefix).strip() or "ue2e-"
            with open_maintenance_connection() as conn:
                deleted = _cleanup_ue2e(conn, command="cleanup", prefix=prefix)
            _emit(
                {
                    "scenario": "cleanup",
                    "prefix": prefix,
                    "deleted": deleted,
                }
            )
            return 0

        if args.command == "schema-check":
            with open_maintenance_connection() as conn:
                _emit(_schema_check(conn))
            return 0

        if args.command == "audit-auth-junk":
            with open_maintenance_connection() as conn:
                _emit(_audit_auth_junk(conn))
            return 0

        if args.command == "seed-auth-principals":
            _emit(_seed_auth_principals(emit_tokens=bool(args.emit_tokens), env=os.environ))
            return 0

        if args.command == "cleanup-auth-junk":
            with open_maintenance_connection() as conn:
                _emit(_cleanup_auth_junk(conn, apply=bool(args.apply)))
            return 0

        print(json.dumps({"error": "unsupported_command"}))
        return 2
    except SeedHelperStatementError as exc:
        print(
            json.dumps(
                {
                    "error": "seed_helper_failed",
                    "message": "database_statement_failed",
                    "context": exc.to_payload(),
                }
            )
        )
        return 1
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": "seed_helper_failed", "message": _sanitize_error_text(str(exc))}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
