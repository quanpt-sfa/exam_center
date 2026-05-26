"""Shared PostgreSQL helpers for S2W-7 end-to-end integration tests."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterable
import os

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


S2W7_PREFIX_PATTERNS: tuple[str, ...] = (
    "s2w7-%",
    "s2w7-textbox-%",
    "s2w7-capture-%",
)

S2W7_SESSION_CODE_PATTERNS: tuple[str, ...] = (
    "S2W7%",
)

S2W7_SITTING_CODE_PATTERNS: tuple[str, ...] = (
    "S2W7%",
)

S2W7_EXAM_CODE_PATTERNS: tuple[str, ...] = (
    "S2W7%",
)

S2W7_CLASS_CODE_PATTERNS: tuple[str, ...] = (
    "S2W7%",
)

S2W7_OFFERING_CODE_PATTERNS: tuple[str, ...] = (
    "S2W7%",
)

S2W7_COURSE_CODE_PATTERNS: tuple[str, ...] = (
    "S2W7%",
)

S2W7_TERM_CODE_PATTERNS: tuple[str, ...] = (
    "S2W7%",
)

S2W7_DEPARTMENT_CODE_PATTERNS: tuple[str, ...] = (
    "S2W7%",
)

S2W7_ASSIGNMENT_NOTE_PATTERNS: tuple[str, ...] = (
    "S2W7 bootstrap %",
)

S2W7_TEMPLATE_CODE_PATTERNS: tuple[str, ...] = (
    "S2W7%",
)

S2W7_QUESTION_CODE_PATTERNS: tuple[str, ...] = (
    "S2W7%",
)


def _bootstrap_variant(requires_capture_config: bool | None) -> str:
    if requires_capture_config is True:
        return "capture"
    if requires_capture_config is False:
        return "textbox"
    return "generic"


def _ensure_s2w7_bootstrap_student_principal(
    conn,
    *,
    username: str,
    student_code: str,
    full_name: str,
) -> dict[str, int]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                u.user_id,
                u.person_id,
                sp.student_id
            FROM identity.app_user u
            LEFT JOIN identity.student_profile sp
                ON sp.person_id = u.person_id
            WHERE lower(u.username) = lower(%s)
            LIMIT 1
            """,
            (str(username),),
        )
        existing_user = cur.fetchone()
        if existing_user is not None:
            person_id = int(existing_user["person_id"])
            user_id = int(existing_user["user_id"])
            student_id = existing_user["student_id"]
            if student_id is None:
                cur.execute(
                    """
                    INSERT INTO identity.student_profile (
                        person_id,
                        student_code,
                        program_id,
                        cohort,
                        entry_year,
                        student_status,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, NULL, NULL, extract(year from now())::integer, 'ACTIVE', now(), now())
                    RETURNING student_id
                    """,
                    (person_id, str(student_code)),
                )
                student_row = cur.fetchone()
                if student_row is None:
                    raise RuntimeError("Failed to insert S2W-7 bootstrap student_profile")
                student_id = int(student_row["student_id"])
            return {
                "person_id": person_id,
                "user_id": user_id,
                "student_id": int(student_id),
            }

        cur.execute(
            """
            SELECT
                sp.student_id,
                sp.person_id,
                u.user_id
            FROM identity.student_profile sp
            LEFT JOIN identity.app_user u
                ON u.person_id = sp.person_id
            WHERE sp.student_code = %s
            LIMIT 1
            """,
            (str(student_code),),
        )
        existing_student = cur.fetchone()
        if existing_student is not None:
            person_id = int(existing_student["person_id"])
            student_id = int(existing_student["student_id"])
            user_id = existing_student["user_id"]
            if user_id is None:
                cur.execute(
                    """
                    INSERT INTO identity.app_user (
                        person_id,
                        username,
                        email_login,
                        password_hash,
                        user_status,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, 'ACTIVE', now(), now())
                    RETURNING user_id
                    """,
                    (
                        person_id,
                        str(username),
                        f"{username}@local.test",
                        "s2w7-bootstrap-not-for-auth",
                    ),
                )
                user_row = cur.fetchone()
                if user_row is None:
                    raise RuntimeError("Failed to insert S2W-7 bootstrap app_user")
                user_id = int(user_row["user_id"])
            return {
                "person_id": person_id,
                "user_id": int(user_id),
                "student_id": student_id,
            }

        cur.execute(
            """
            INSERT INTO identity.person (
                full_name,
                date_of_birth,
                gender_code,
                national_id,
                person_status,
                created_at,
                updated_at
            )
            VALUES (%s, NULL, NULL, NULL, 'ACTIVE', now(), now())
            RETURNING person_id
            """,
            (str(full_name),),
        )
        person_row = cur.fetchone()
        if person_row is None:
            raise RuntimeError("Failed to insert S2W-7 bootstrap person")

        person_id = int(person_row["person_id"])
        cur.execute(
            """
            INSERT INTO identity.app_user (
                person_id,
                username,
                email_login,
                password_hash,
                user_status,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, 'ACTIVE', now(), now())
            RETURNING user_id
            """,
            (
                person_id,
                str(username),
                f"{username}@local.test",
                "s2w7-bootstrap-not-for-auth",
            ),
        )
        user_row = cur.fetchone()
        if user_row is None:
            raise RuntimeError("Failed to insert S2W-7 bootstrap app_user")

        cur.execute(
            """
            INSERT INTO identity.student_profile (
                person_id,
                student_code,
                program_id,
                cohort,
                entry_year,
                student_status,
                created_at,
                updated_at
            )
            VALUES (%s, %s, NULL, NULL, extract(year from now())::integer, 'ACTIVE', now(), now())
            RETURNING student_id
            """,
            (person_id, str(student_code)),
        )
        student_row = cur.fetchone()
        if student_row is None:
            raise RuntimeError("Failed to insert S2W-7 bootstrap student_profile")

    return {
        "person_id": person_id,
        "user_id": int(user_row["user_id"]),
        "student_id": int(student_row["student_id"]),
    }


def _ensure_s2w7_bootstrap_principals(conn) -> dict[str, int]:
    owner = _ensure_s2w7_bootstrap_student_principal(
        conn,
        username="s2w7_seed_owner",
        student_code="S2W7_SEED_OWNER",
        full_name="S2W7 Seed Owner",
    )
    non_owner = _ensure_s2w7_bootstrap_student_principal(
        conn,
        username="s2w7_seed_non_owner",
        student_code="S2W7_SEED_NON_OWNER",
        full_name="S2W7 Seed Non Owner",
    )
    return {
        "owner_user_id": int(owner["user_id"]),
        "owner_student_id": int(owner["student_id"]),
        "non_owner_user_id": int(non_owner["user_id"]),
        "non_owner_student_id": int(non_owner["student_id"]),
    }


def _ensure_s2w7_bootstrap_class_section(conn) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT class_section_id
            FROM academic.class_section
            WHERE class_code = 'S2W7_BOOT_CLASS'
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if row is not None:
            return int(row["class_section_id"])

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
            VALUES ('S2W7_BOOT_DEP', 'S2W7 bootstrap department', NULL, 'ACTIVE', now(), now())
            RETURNING department_id
            """
        )
        department_row = cur.fetchone()
        if department_row is None:
            raise RuntimeError("Failed to insert S2W-7 bootstrap department")

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
            VALUES (%s, 'S2W7_BOOT_COURSE', 'S2W7 bootstrap course', 'GENERAL', 3, 'ACTIVE', now(), now())
            RETURNING course_id
            """,
            (int(department_row["department_id"]),),
        )
        course_row = cur.fetchone()
        if course_row is None:
            raise RuntimeError("Failed to insert S2W-7 bootstrap course")

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
            VALUES ('S2W7_BOOT_TERM', 'S2W7 bootstrap term', current_date - 30, current_date + 60, 'ACTIVE', now(), now())
            RETURNING term_id
            """
        )
        term_row = cur.fetchone()
        if term_row is None:
            raise RuntimeError("Failed to insert S2W-7 bootstrap term")

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
            VALUES (%s, %s, 'S2W7_BOOT_OFFER', NULL, 'ACTIVE', now(), now())
            RETURNING course_offering_id
            """,
            (int(course_row["course_id"]), int(term_row["term_id"])),
        )
        offering_row = cur.fetchone()
        if offering_row is None:
            raise RuntimeError("Failed to insert S2W-7 bootstrap course_offering")

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
            VALUES (%s, 'S2W7_BOOT_CLASS', 'S2W7 bootstrap class', 100, 'LAB', 'ACTIVE', now(), now())
            RETURNING class_section_id
            """,
            (int(offering_row["course_offering_id"]),),
        )
        class_row = cur.fetchone()
        if class_row is None:
            raise RuntimeError("Failed to insert S2W-7 bootstrap class_section")

    return int(class_row["class_section_id"])


def _ensure_s2w7_bootstrap_profile(
    conn,
    *,
    exam_version_id: int,
    created_by: int,
    requires_capture_config: bool | None,
) -> None:
    variant = _bootstrap_variant(requires_capture_config)
    template_code = f"S2W7_BOOT_{variant.upper()}_ELIGIBILITY_QT"
    metadata_source = f"s2w7-bootstrap-{variant}"

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT question_template_id
            FROM assessment.question_template
            WHERE template_code = %s
            LIMIT 1
            """,
            (template_code,),
        )
        template_row = cur.fetchone()
        if template_row is None:
            cur.execute(
                """
                INSERT INTO assessment.question_template (
                    template_code,
                    question_type,
                    title,
                    template_text,
                    topic_code,
                    skill_code,
                    difficulty_level,
                    default_score,
                    generator_type,
                    generator_version,
                    status,
                    created_by
                )
                VALUES (
                    %s,
                    'SQL_QUERY',
                    %s,
                    %s,
                    'TOPIC1',
                    'SKILL1',
                    'MEDIUM',
                    1.00,
                    'STATIC',
                    '1.0.0',
                    'ACTIVE',
                    %s
                )
                RETURNING question_template_id
                """,
                (
                    template_code,
                    f"S2W7 bootstrap {variant} eligibility template",
                    f"S2W7 bootstrap {variant} eligibility query.",
                    int(created_by),
                ),
            )
            template_row = cur.fetchone()
        if template_row is None:
            raise RuntimeError("Failed to ensure S2W-7 bootstrap question_template")

        grading_engine_id = _select_sql_engine_id(conn=conn)
        capture_profile_id: int | None = None
        input_source = 'SEALED_TEXT_ANSWER'
        answer_language = 'SQL'
        required_capture_type = None
        if requires_capture_config is True:
            capture_profile_id = ensure_s2w7_postgres_capture_profile(conn=conn)
            input_source = 'STUDENT_DATABASE_CAPTURE'
            answer_language = 'OTHER'
            required_capture_type = 'POSTGRES_DATABASE_SNAPSHOT'

        cur.execute(
            """
            SELECT question_grading_profile_id
            FROM assessment.question_grading_profile
            WHERE question_template_id = %s
              AND exam_version_id = %s
            LIMIT 1
            """,
            (int(template_row["question_template_id"]), int(exam_version_id)),
        )
        profile_row = cur.fetchone()
        metadata_json = Jsonb({"source": metadata_source})

        if profile_row is None:
            cur.execute(
                """
                INSERT INTO assessment.question_grading_profile (
                    question_template_id,
                    exam_version_id,
                    input_source,
                    answer_language,
                    requires_capture,
                    required_capture_type,
                    capture_profile_id,
                    grading_engine_id,
                    comparison_method,
                    timeout_seconds,
                    max_score,
                    status,
                    metadata_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'EXACT_RESULT_SET', 30, 1.00, 'ACTIVE', %s)
                """,
                (
                    int(template_row["question_template_id"]),
                    int(exam_version_id),
                    input_source,
                    answer_language,
                    bool(requires_capture_config),
                    required_capture_type,
                    capture_profile_id,
                    int(grading_engine_id),
                    metadata_json,
                ),
            )
        else:
            cur.execute(
                """
                UPDATE assessment.question_grading_profile
                SET
                    input_source = %s,
                    answer_language = %s,
                    requires_capture = %s,
                    required_capture_type = %s,
                    capture_profile_id = %s,
                    grading_engine_id = %s,
                    comparison_method = 'EXACT_RESULT_SET',
                    timeout_seconds = 30,
                    max_score = 1.00,
                    status = 'ACTIVE',
                    metadata_json = %s,
                    updated_at = now()
                WHERE question_grading_profile_id = %s
                """,
                (
                    input_source,
                    answer_language,
                    bool(requires_capture_config),
                    required_capture_type,
                    capture_profile_id,
                    int(grading_engine_id),
                    metadata_json,
                    int(profile_row["question_grading_profile_id"]),
                ),
            )


def _ensure_s2w7_base_delivery_graph(
    *,
    conn,
    requires_capture_config: bool | None,
) -> dict[str, int]:
    variant = _bootstrap_variant(requires_capture_config)
    principals = _ensure_s2w7_bootstrap_principals(conn)
    class_section_id = _ensure_s2w7_bootstrap_class_section(conn)
    exam_code = f"S2W7_BOOT_{variant.upper()}_EXAM"
    sitting_code = f"S2W7_BOOT_{variant.upper()}_SIT"
    assignment_note = f"S2W7 bootstrap {variant} assignment"

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT pg_advisory_xact_lock(hashtext(%s))
            """,
            (f"s2w7_base_delivery:{variant}",),
        )

        cur.execute(
            """
            SELECT
                ea.exam_assignment_id,
                sit.exam_version_id
            FROM delivery.exam_assignment ea
            JOIN delivery.exam_sitting sit
                ON sit.exam_sitting_id = ea.exam_sitting_id
            WHERE ea.note = %s
            LIMIT 1
            """,
            (assignment_note,),
        )
        existing = cur.fetchone()
        if existing is not None:
            _ensure_s2w7_bootstrap_profile(
                conn,
                exam_version_id=int(existing["exam_version_id"]),
                created_by=int(principals["owner_user_id"]),
                requires_capture_config=requires_capture_config,
            )
            conn.commit()
            return {
                "exam_assignment_id": int(existing["exam_assignment_id"]),
                "exam_version_id": int(existing["exam_version_id"]),
                "owner_student_id": int(principals["owner_student_id"]),
                "owner_user_id": int(principals["owner_user_id"]),
                "non_owner_user_id": int(principals["non_owner_user_id"]),
            }

        cur.execute(
            """
            SELECT assessment_type_id
            FROM assessment.assessment_type
            ORDER BY assessment_type_id ASC
            LIMIT 1
            """
        )
        assessment_type_row = cur.fetchone()
        if assessment_type_row is None:
            raise RuntimeError("Cannot bootstrap S2W-7 delivery graph: assessment.assessment_type is empty")

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
                exam_code,
                f"S2W7 bootstrap {variant} exam",
                int(principals["owner_user_id"]),
            ),
        )
        exam_row = cur.fetchone()
        if exam_row is None:
            raise RuntimeError("Failed to insert S2W-7 bootstrap exam")

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
                f"S2W7 bootstrap {variant} version",
                int(principals["owner_user_id"]),
            ),
        )
        version_row = cur.fetchone()
        if version_row is None:
            raise RuntimeError("Failed to insert S2W-7 bootstrap exam_version")

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
            VALUES (%s, %s, %s, now() - interval '30 minute', now() + interval '90 minute', 'READY', %s, now(), now())
            RETURNING exam_sitting_id
            """,
            (
                int(version_row["exam_version_id"]),
                sitting_code,
                f"S2W7 bootstrap {variant} sitting",
                int(principals["owner_user_id"]),
            ),
        )
        sitting_row = cur.fetchone()
        if sitting_row is None:
            raise RuntimeError("Failed to insert S2W-7 bootstrap exam_sitting")

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
                int(principals["owner_student_id"]),
                int(principals["owner_user_id"]),
                assignment_note,
            ),
        )
        assignment_row = cur.fetchone()
        if assignment_row is None:
            raise RuntimeError("Failed to insert S2W-7 bootstrap exam_assignment")

    _ensure_s2w7_bootstrap_profile(
        conn,
        exam_version_id=int(version_row["exam_version_id"]),
        created_by=int(principals["owner_user_id"]),
        requires_capture_config=requires_capture_config,
    )
    conn.commit()

    return {
        "exam_assignment_id": int(assignment_row["exam_assignment_id"]),
        "exam_version_id": int(version_row["exam_version_id"]),
        "owner_student_id": int(principals["owner_student_id"]),
        "owner_user_id": int(principals["owner_user_id"]),
        "non_owner_user_id": int(principals["non_owner_user_id"]),
    }


def build_runtime_conninfo() -> str:
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "exam_sys_dev")
    user = os.getenv("POSTGRES_USER", "exam_sys_app")
    password = os.getenv("POSTGRES_PASSWORD", os.getenv("PGPASSWORD", ""))
    sslmode = os.getenv("POSTGRES_SSLMODE", "prefer")
    timeout = os.getenv("POSTGRES_CONNECT_TIMEOUT", "3")

    params = {
        "host": str(host),
        "port": str(port),
        "dbname": str(database),
        "user": str(user),
        "sslmode": str(sslmode),
        "connect_timeout": str(timeout),
    }
    if str(password).strip():
        params["password"] = str(password)
    return make_conninfo("", **params)


def build_maintenance_conninfo() -> str:
    host = os.getenv("POSTGRES_MAINTENANCE_HOST") or os.getenv("POSTGRES_HOST") or "localhost"
    port = os.getenv("POSTGRES_MAINTENANCE_PORT") or os.getenv("POSTGRES_PORT") or "5432"
    database = os.getenv("POSTGRES_MAINTENANCE_DB") or os.getenv("POSTGRES_DB") or "exam_sys_dev"
    user = os.getenv("POSTGRES_MAINTENANCE_USER") or os.getenv("PGUSER") or "postgres"
    password = (
        os.getenv("POSTGRES_MAINTENANCE_PASSWORD")
        or os.getenv("PGPASSWORD")
        or os.getenv("POSTGRES_PASSWORD")
        or ""
    )
    sslmode = os.getenv("POSTGRES_MAINTENANCE_SSLMODE") or os.getenv("POSTGRES_SSLMODE") or "prefer"
    timeout = os.getenv("POSTGRES_CONNECT_TIMEOUT", "3")

    params = {
        "host": str(host),
        "port": str(port),
        "dbname": str(database),
        "user": str(user),
        "sslmode": str(sslmode),
        "connect_timeout": str(timeout),
    }
    if str(password).strip():
        params["password"] = str(password)
    return make_conninfo("", **params)


@contextmanager
def open_runtime_connection():
    conn = psycopg.connect(build_runtime_conninfo(), autocommit=False)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def open_maintenance_connection():
    conn = psycopg.connect(build_maintenance_conninfo(), autocommit=False)
    try:
        yield conn
    finally:
        conn.close()


def runtime_user_name() -> str:
    return str(os.getenv("POSTGRES_USER") or "<unset>").strip() or "<unset>"


def maintenance_user_name() -> str:
    return str(os.getenv("POSTGRES_MAINTENANCE_USER") or os.getenv("PGUSER") or "postgres").strip()


def _to_int_set(values: Iterable[Any]) -> set[int]:
    result: set[int] = set()
    for value in values:
        if value is None:
            continue
        result.add(int(value))
    return result


def _delete_where_any(cur, *, table: str, column: str, ids: list[int]) -> int:
    if not ids:
        return 0
    cur.execute(
        f"DELETE FROM {table} WHERE {column} = ANY(%s)",
        (ids,),
    )
    return max(int(cur.rowcount or 0), 0)


def _find_unused_session_instance_pair(
    *,
    conn,
    requires_capture_config: bool | None = None,
) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                sess.exam_session_id,
                gei.generated_exam_instance_id,
                gei.exam_version_id
            FROM delivery.exam_session sess
            JOIN delivery.generated_exam_instance gei
                ON gei.exam_session_id = sess.exam_session_id
            LEFT JOIN submission.exam_submission es
                ON es.exam_session_id = sess.exam_session_id
                OR es.generated_exam_instance_id = gei.generated_exam_instance_id
            WHERE es.exam_submission_id IS NULL
              AND (
                    %s::boolean IS NULL
                    OR (
                        %s = true
                        AND EXISTS (
                            SELECT 1
                            FROM assessment.v_question_grading_profile_summary qgps
                            WHERE qgps.exam_version_id = gei.exam_version_id
                              AND qgps.status = 'ACTIVE'
                              AND qgps.requires_capture = true
                            LIMIT 1
                        )
                    )
                    OR (
                        %s = false
                        AND NOT EXISTS (
                            SELECT 1
                            FROM assessment.v_question_grading_profile_summary qgps
                            WHERE qgps.exam_version_id = gei.exam_version_id
                              AND qgps.status = 'ACTIVE'
                              AND qgps.requires_capture = true
                            LIMIT 1
                        )
                    )
                )
            ORDER BY gei.generated_exam_instance_id DESC
            LIMIT 1
            """,
            (requires_capture_config, requires_capture_config, requires_capture_config),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return {
        "exam_session_id": int(row["exam_session_id"]),
        "generated_exam_instance_id": int(row["generated_exam_instance_id"]),
        "exam_version_id": int(row["exam_version_id"]),
    }


def _create_session_instance_pair(
    *,
    conn,
    suffix: str,
    requires_capture_config: bool | None = None,
) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                ea.exam_assignment_id,
                sit.exam_version_id
            FROM delivery.exam_assignment ea
            JOIN delivery.exam_sitting sit
                ON sit.exam_sitting_id = ea.exam_sitting_id
            WHERE (
                %s::boolean IS NULL
                OR (
                    %s = true
                    AND EXISTS (
                        SELECT 1
                        FROM assessment.v_question_grading_profile_summary qgps
                        WHERE qgps.exam_version_id = sit.exam_version_id
                          AND qgps.status = 'ACTIVE'
                          AND qgps.requires_capture = true
                        LIMIT 1
                    )
                )
                OR (
                    %s = false
                    AND NOT EXISTS (
                        SELECT 1
                        FROM assessment.v_question_grading_profile_summary qgps
                        WHERE qgps.exam_version_id = sit.exam_version_id
                          AND qgps.status = 'ACTIVE'
                          AND qgps.requires_capture = true
                        LIMIT 1
                    )
                )
            )
            ORDER BY ea.exam_assignment_id DESC
            LIMIT 1
            """,
            (requires_capture_config, requires_capture_config, requires_capture_config),
        )
        base = cur.fetchone()
        if base is None:
            ensured = _ensure_s2w7_base_delivery_graph(
                conn=conn,
                requires_capture_config=requires_capture_config,
            )
            base = {
                "exam_assignment_id": int(ensured["exam_assignment_id"]),
                "exam_version_id": int(ensured["exam_version_id"]),
            }

        # Serialize session_no allocation per exam_assignment_id to avoid
        # duplicate (exam_assignment_id, session_no) under parallel E2E workers.
        cur.execute(
            """
            SELECT pg_advisory_xact_lock(hashtext(%s))
            """,
            (f"s2w7_exam_session:{int(base['exam_assignment_id'])}",),
        )

        cur.execute(
            """
            SELECT coalesce(max(sess.session_no), 0) + 1 AS next_session_no
            FROM delivery.exam_session sess
            WHERE sess.exam_assignment_id = %s
            """,
            (int(base["exam_assignment_id"]),),
        )
        next_session_row = cur.fetchone()
        if next_session_row is None:
            raise RuntimeError("Failed to allocate next session_no for S2W-7 session creation")
        next_session_no = int(next_session_row["next_session_no"])

        cur.execute(
            """
            INSERT INTO delivery.exam_session (
                exam_assignment_id,
                session_code,
                session_no,
                session_status,
                time_limit_seconds,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, 'ENDED', 3600, now(), now())
            RETURNING exam_session_id
            """,
            (
                int(base["exam_assignment_id"]),
                f"S2W7_SESSION_{suffix}",
                int(next_session_no),
            ),
        )
        session_row = cur.fetchone()
        if session_row is None:
            return None

        cur.execute(
            """
            INSERT INTO delivery.generated_exam_instance (
                exam_session_id,
                exam_version_id,
                generation_mode,
                generation_status,
                generated_at,
                created_at,
                updated_at,
                metadata_json
            )
            VALUES (%s, %s, 'FIXED', 'GENERATED', now(), now(), now(), %s::jsonb)
            RETURNING generated_exam_instance_id
            """,
            (
                int(session_row["exam_session_id"]),
                int(base["exam_version_id"]),
                '{"source":"s2w7-harness"}',
            ),
        )
        instance_row = cur.fetchone()
        if instance_row is None:
            return None

    conn.commit()
    return {
        "exam_session_id": int(session_row["exam_session_id"]),
        "generated_exam_instance_id": int(instance_row["generated_exam_instance_id"]),
        "exam_version_id": int(base["exam_version_id"]),
        "created_session_instance": True,
    }


def create_s2w7_harness_seed_rows(*, conn, suffix: str) -> dict[str, int | bool | str]:
    pair = _find_unused_session_instance_pair(conn=conn)
    created_session_instance = False
    if pair is None:
        created = _create_session_instance_pair(conn=conn, suffix=suffix)
        if created is None:
            raise RuntimeError("No eligible exam_session/generated_exam_instance pair for S2W-7 harness seed")
        pair = {
            "exam_session_id": int(created["exam_session_id"]),
            "generated_exam_instance_id": int(created["generated_exam_instance_id"]),
        }
        created_session_instance = True

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO submission.exam_submission (
                exam_session_id,
                generated_exam_instance_id,
                submission_status,
                submitted_at,
                sealed_at,
                seal_reason,
                created_at,
                updated_at,
                metadata_json
            )
            VALUES (%s, %s, 'SUBMITTED', now(), now(), 'STUDENT_SUBMIT', now(), now(), %s::jsonb)
            RETURNING exam_submission_id
            """,
            (
                int(pair["exam_session_id"]),
                int(pair["generated_exam_instance_id"]),
                '{"source":"s2w7-harness"}',
            ),
        )
        submission_row = cur.fetchone()
        if submission_row is None:
            raise RuntimeError("Failed to insert S2W-7 harness submission seed")

        cur.execute(
            """
            INSERT INTO submission.submission_seal (
                exam_submission_id,
                seal_idempotency_key,
                seal_status,
                seal_reason,
                sealed_at,
                server_time_at_seal,
                answer_count,
                submission_hash,
                metadata_json
            )
            VALUES (%s, %s, 'SEALED', 'STUDENT_SUBMIT', now(), now(), 0, NULL, %s::jsonb)
            RETURNING submission_seal_id
            """,
            (
                int(submission_row["exam_submission_id"]),
                f"s2w7-{suffix}-seal",
                '{"source":"s2w7-harness"}',
            ),
        )
        seal_row = cur.fetchone()
        if seal_row is None:
            raise RuntimeError("Failed to insert S2W-7 harness submission_seal seed")

        cur.execute(
            """
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
            VALUES (%s, %s, %s, %s, 'AUTO', 'QUEUED', %s, now(), 0, %s::jsonb, now(), now())
            RETURNING grading_job_id
            """,
            (
                int(submission_row["exam_submission_id"]),
                int(seal_row["submission_seal_id"]),
                int(pair["exam_session_id"]),
                int(pair["generated_exam_instance_id"]),
                f"s2w7-textbox-{suffix}",
                '{"source":"s2w7-harness"}',
            ),
        )
        job_row = cur.fetchone()
        if job_row is None:
            raise RuntimeError("Failed to insert S2W-7 harness grading_job seed")

        cur.execute(
            """
            INSERT INTO grading.grading_run (
                grading_job_id,
                run_no,
                run_status,
                started_at,
                worker_id,
                metadata_json
            )
            VALUES (%s, 1, 'RUNNING', now(), %s, %s::jsonb)
            RETURNING grading_run_id
            """,
            (
                int(job_row["grading_job_id"]),
                f"s2w7-worker-{suffix}",
                '{"source":"s2w7-harness"}',
            ),
        )
        run_row = cur.fetchone()
        if run_row is None:
            raise RuntimeError("Failed to insert S2W-7 harness grading_run seed")

        cur.execute(
            """
            INSERT INTO grading.grading_event (
                grading_job_id,
                grading_run_id,
                question_grading_task_id,
                event_type,
                event_at,
                actor_user_id,
                worker_id,
                event_payload_json,
                created_at
            )
            VALUES (%s, %s, NULL, 'JOB_STARTED', now(), NULL, %s, %s::jsonb, now())
            RETURNING grading_event_id
            """,
            (
                int(job_row["grading_job_id"]),
                int(run_row["grading_run_id"]),
                f"s2w7-worker-{suffix}",
                '{"source":"s2w7-harness"}',
            ),
        )
        event_row = cur.fetchone()
        if event_row is None:
            raise RuntimeError("Failed to insert S2W-7 harness grading_event seed")

        cur.execute(
            """
            INSERT INTO capture.capture_job (
                exam_submission_id,
                submission_seal_id,
                exam_session_id,
                generated_exam_instance_id,
                idempotency_key,
                capture_type,
                capture_status,
                requested_at,
                attempt_count,
                metadata_json
            )
            VALUES (%s, %s, %s, %s, %s, 'OTHER', 'QUEUED', now(), 0, %s::jsonb)
            RETURNING capture_job_id
            """,
            (
                int(submission_row["exam_submission_id"]),
                int(seal_row["submission_seal_id"]),
                int(pair["exam_session_id"]),
                int(pair["generated_exam_instance_id"]),
                f"s2w7-capture-{suffix}",
                '{"source":"s2w7-harness"}',
            ),
        )
        capture_row = cur.fetchone()
        if capture_row is None:
            raise RuntimeError("Failed to insert S2W-7 harness capture_job seed")

    conn.commit()

    return {
        "suffix": suffix,
        "exam_submission_id": int(submission_row["exam_submission_id"]),
        "submission_seal_id": int(seal_row["submission_seal_id"]),
        "grading_job_id": int(job_row["grading_job_id"]),
        "grading_run_id": int(run_row["grading_run_id"]),
        "grading_event_id": int(event_row["grading_event_id"]),
        "capture_job_id": int(capture_row["capture_job_id"]),
        "exam_session_id": int(pair["exam_session_id"]),
        "generated_exam_instance_id": int(pair["generated_exam_instance_id"]),
        "created_session_instance": bool(created_session_instance),
    }


def _select_seed_user_id(*, conn) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT user_id FROM identity.app_user ORDER BY user_id ASC LIMIT 1")
        row = cur.fetchone()
    if row is None:
        raise RuntimeError("No identity.app_user seed found for S2W-7")
    return int(row["user_id"])


def _select_sql_engine_id(*, conn) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT grading_engine_id
            FROM grading.grading_engine
            WHERE engine_code = 'SQL_RESULT_COMPARATOR'
            ORDER BY grading_engine_id ASC
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if row is None:
            cur.execute("SELECT grading_engine_id FROM grading.grading_engine ORDER BY grading_engine_id ASC LIMIT 1")
            row = cur.fetchone()
    if row is None:
        raise RuntimeError("No grading engine found for S2W-7")
    return int(row["grading_engine_id"])


def _select_student_users_for_session(*, conn, exam_session_id: int) -> dict[str, int | None]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT ea.student_id
            FROM delivery.exam_session sess
            JOIN delivery.exam_assignment ea
                ON ea.exam_assignment_id = sess.exam_assignment_id
            WHERE sess.exam_session_id = %s
            LIMIT 1
            """,
            (int(exam_session_id),),
        )
        owner_row = cur.fetchone()
        if owner_row is None:
            return {
                "owner_student_id": None,
                "owner_user_id": None,
                "non_owner_user_id": None,
            }

        owner_student_id = int(owner_row["student_id"])

        cur.execute(
            """
            SELECT u.user_id
            FROM identity.student_profile sp
            JOIN identity.app_user u
                ON u.person_id = sp.person_id
            WHERE sp.student_id = %s
            ORDER BY u.user_id ASC
            LIMIT 1
            """,
            (owner_student_id,),
        )
        owner_user_row = cur.fetchone()

        cur.execute(
            """
            SELECT u.user_id
            FROM identity.student_profile sp
            JOIN identity.app_user u
                ON u.person_id = sp.person_id
            WHERE sp.student_id <> %s
            ORDER BY u.user_id ASC
            LIMIT 1
            """,
            (owner_student_id,),
        )
        non_owner_user_row = cur.fetchone()

    return {
        "owner_student_id": owner_student_id,
        "owner_user_id": int(owner_user_row["user_id"]) if owner_user_row is not None else None,
        "non_owner_user_id": int(non_owner_user_row["user_id"]) if non_owner_user_row is not None else None,
    }


def _expected_result_payload(rows: list[list[Any]]) -> dict[str, Any]:
    normalized_rows: list[list[Any]] = []
    for row in rows:
        normalized_rows.append(list(row))
    return {
        "columns": ["value"],
        "rows": normalized_rows,
        "row_count": len(normalized_rows),
        "truncated": False,
        "normalization_version": "s2w4_4_v1",
    }


def create_s2w7_textbox_sql_seed_graph(
    *,
    conn,
    suffix: str,
    sealed_answer_sql: str,
    answer_state_sql: str,
    expected_rows: list[list[Any]],
) -> dict[str, Any]:
    prefix = f"s2w7-textbox-{suffix}"
    created = _create_session_instance_pair(
        conn=conn,
        suffix=suffix,
        requires_capture_config=False,
    )
    if created is None:
        raise RuntimeError("No eligible exam_session/generated_exam_instance pair for S2W-7 TEXTBOX_SQL seed")
    pair = {
        "exam_session_id": int(created["exam_session_id"]),
        "generated_exam_instance_id": int(created["generated_exam_instance_id"]),
    }
    created_session_instance = True

    created_by = _select_seed_user_id(conn=conn)
    grading_engine_id = _select_sql_engine_id(conn=conn)
    user_map = _select_student_users_for_session(conn=conn, exam_session_id=int(pair["exam_session_id"]))

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO assessment.question_template (
                template_code,
                question_type,
                title,
                template_text,
                topic_code,
                skill_code,
                difficulty_level,
                default_score,
                generator_type,
                generator_version,
                status,
                created_by
            )
            VALUES (
                %s,
                'SQL_QUERY',
                %s,
                %s,
                'TOPIC1',
                'SKILL1',
                'MEDIUM',
                10.00,
                'PARAMETERIZED',
                '1.0.0',
                'ACTIVE',
                %s
            )
            RETURNING question_template_id
            """,
            (
                f"S2W7_TB_QT_{suffix}",
                f"S2W7 textbox template {suffix}",
                "Write SQL that returns deterministic output.",
                int(created_by),
            ),
        )
        template_row = cur.fetchone()
        if template_row is None:
            raise RuntimeError("Failed to insert S2W-7 question_template")

        cur.execute(
            """
            SELECT coalesce(max(question_order), 0) + 1 AS next_question_order
            FROM delivery.generated_exam_question
            WHERE generated_exam_instance_id = %s
            """,
            (int(pair["generated_exam_instance_id"]),),
        )
        order_row = cur.fetchone()
        next_question_order = int(order_row["next_question_order"]) if order_row is not None else 1

        cur.execute(
            """
            INSERT INTO delivery.generated_exam_question (
                generated_exam_instance_id,
                question_template_id,
                question_order,
                question_code,
                question_type,
                rendered_question_text,
                score,
                metadata_json
            )
            VALUES (%s, %s, %s, %s, 'SQL_QUERY', %s, %s, %s)
            RETURNING generated_exam_question_id
            """,
            (
                int(pair["generated_exam_instance_id"]),
                int(template_row["question_template_id"]),
                int(next_question_order),
                f"S2W7_TB_Q_{suffix}",
                f"S2W7 textbox SQL question {suffix}",
                "10.00",
                Jsonb({"source": prefix}),
            ),
        )
        question_row = cur.fetchone()
        if question_row is None:
            raise RuntimeError("Failed to insert S2W-7 generated_exam_question")

        cur.execute(
            """
            INSERT INTO delivery.generated_expected_answer (
                generated_exam_question_id,
                answer_order,
                solution_type,
                expected_payload,
                expected_payload_json,
                expected_hash,
                created_by,
                metadata_json
            )
            VALUES (%s, 1, 'SQL_RESULT', NULL, %s, NULL, %s, %s)
            RETURNING generated_expected_answer_id
            """,
            (
                int(question_row["generated_exam_question_id"]),
                Jsonb(_expected_result_payload(expected_rows)),
                int(created_by),
                Jsonb({"source": prefix}),
            ),
        )
        expected_row = cur.fetchone()
        if expected_row is None:
            raise RuntimeError("Failed to insert S2W-7 generated_expected_answer")

        cur.execute(
            """
            INSERT INTO submission.exam_submission (
                exam_session_id,
                generated_exam_instance_id,
                submission_status,
                submitted_at,
                sealed_at,
                seal_reason,
                created_at,
                updated_at,
                metadata_json
            )
            VALUES (%s, %s, 'SUBMITTED', now(), now(), 'STUDENT_SUBMIT', now(), now(), %s)
            RETURNING exam_submission_id
            """,
            (
                int(pair["exam_session_id"]),
                int(pair["generated_exam_instance_id"]),
                Jsonb({"source": prefix}),
            ),
        )
        submission_row = cur.fetchone()
        if submission_row is None:
            raise RuntimeError("Failed to insert S2W-7 exam_submission")

        cur.execute(
            """
            INSERT INTO submission.submission_seal (
                exam_submission_id,
                seal_idempotency_key,
                seal_status,
                seal_reason,
                sealed_at,
                server_time_at_seal,
                answer_count,
                submission_hash,
                metadata_json
            )
            VALUES (%s, %s, 'SEALED', 'STUDENT_SUBMIT', now(), now(), 1, NULL, %s)
            RETURNING submission_seal_id
            """,
            (
                int(submission_row["exam_submission_id"]),
                f"{prefix}-seal",
                Jsonb({"source": prefix}),
            ),
        )
        seal_row = cur.fetchone()
        if seal_row is None:
            raise RuntimeError("Failed to insert S2W-7 submission_seal")

        cur.execute(
            """
            INSERT INTO submission.answer_state (
                exam_submission_id,
                generated_exam_question_id,
                answer_type,
                answer_text,
                answer_hash,
                answer_length,
                client_version,
                server_version,
                client_saved_at,
                last_saved_at,
                answer_status,
                metadata_json
            )
            VALUES (
                %s,
                %s,
                'SQL_TEXT',
                %s,
                repeat('f', 64),
                %s,
                1,
                1,
                now(),
                now(),
                'SEALED',
                %s
            )
            RETURNING answer_state_id
            """,
            (
                int(submission_row["exam_submission_id"]),
                int(question_row["generated_exam_question_id"]),
                str(answer_state_sql),
                len(str(answer_state_sql)),
                Jsonb({"source": prefix}),
            ),
        )
        answer_state_row = cur.fetchone()
        if answer_state_row is None:
            raise RuntimeError("Failed to insert S2W-7 answer_state")

        cur.execute(
            """
            INSERT INTO submission.sealed_answer (
                submission_seal_id,
                exam_submission_id,
                generated_exam_question_id,
                answer_state_id,
                answer_type,
                answer_text,
                answer_hash,
                answer_length,
                sealed_at,
                metadata_json
            )
            VALUES (%s, %s, %s, %s, 'SQL_TEXT', %s, repeat('d', 64), %s, now(), %s)
            RETURNING sealed_answer_id
            """,
            (
                int(seal_row["submission_seal_id"]),
                int(submission_row["exam_submission_id"]),
                int(question_row["generated_exam_question_id"]),
                int(answer_state_row["answer_state_id"]),
                str(sealed_answer_sql),
                len(str(sealed_answer_sql)),
                Jsonb({"source": prefix}),
            ),
        )
        sealed_row = cur.fetchone()
        if sealed_row is None:
            raise RuntimeError("Failed to insert S2W-7 sealed_answer")

        cur.execute(
            """
            INSERT INTO assessment.question_grading_profile (
                question_template_id,
                exam_version_id,
                input_source,
                answer_language,
                requires_capture,
                required_capture_type,
                capture_profile_id,
                grading_engine_id,
                comparison_method,
                timeout_seconds,
                max_score,
                status,
                metadata_json
            )
            VALUES (
                %s,
                NULL,
                'SEALED_TEXT_ANSWER',
                'SQL',
                false,
                NULL,
                NULL,
                %s,
                'EXACT_RESULT_SET',
                30,
                10.00,
                'ACTIVE',
                %s
            )
            RETURNING question_grading_profile_id
            """,
            (
                int(template_row["question_template_id"]),
                int(grading_engine_id),
                Jsonb({"source": prefix}),
            ),
        )
        profile_row = cur.fetchone()
        if profile_row is None:
            raise RuntimeError("Failed to insert S2W-7 question_grading_profile")

        cur.execute(
            """
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
                '1970-01-01 00:00:00+00'::timestamptz,
                0,
                %s,
                now(),
                now()
            )
            RETURNING grading_job_id
            """,
            (
                int(submission_row["exam_submission_id"]),
                int(seal_row["submission_seal_id"]),
                int(pair["exam_session_id"]),
                int(pair["generated_exam_instance_id"]),
                prefix,
                Jsonb({"source": prefix}),
            ),
        )
        job_row = cur.fetchone()
        if job_row is None:
            raise RuntimeError("Failed to insert S2W-7 queued grading_job")

    conn.commit()

    return {
        "suffix": suffix,
        "prefix": prefix,
        "exam_session_id": int(pair["exam_session_id"]),
        "generated_exam_instance_id": int(pair["generated_exam_instance_id"]),
        "created_session_instance": bool(created_session_instance),
        "question_template_id": int(template_row["question_template_id"]),
        "generated_exam_question_id": int(question_row["generated_exam_question_id"]),
        "generated_expected_answer_id": int(expected_row["generated_expected_answer_id"]),
        "question_grading_profile_id": int(profile_row["question_grading_profile_id"]),
        "exam_submission_id": int(submission_row["exam_submission_id"]),
        "submission_seal_id": int(seal_row["submission_seal_id"]),
        "answer_state_id": int(answer_state_row["answer_state_id"]),
        "sealed_answer_id": int(sealed_row["sealed_answer_id"]),
        "grading_job_id": int(job_row["grading_job_id"]),
        "grading_engine_id": int(grading_engine_id),
        "owner_student_id": user_map["owner_student_id"],
        "owner_user_id": user_map["owner_user_id"],
        "non_owner_user_id": user_map["non_owner_user_id"],
    }


def ensure_s2w7_postgres_capture_profile(*, conn) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO capture.capture_profile (
                profile_code,
                profile_name,
                source_type,
                source_location_mode,
                default_capture_timing,
                requires_agent,
                description,
                status,
                metadata_json
            )
            VALUES (
                'S2W7_TEST_POSTGRES_CAPTURE_PROFILE',
                'S2W-7 Test PostgreSQL Capture Profile',
                'POSTGRES_DATABASE',
                'SERVER_HOSTED',
                'AFTER_SEAL',
                false,
                'Deterministic PostgreSQL capture profile for S2W-7 integration tests.',
                'ACTIVE',
                '{"source":"s2w7-capture-profile"}'::jsonb
            )
            ON CONFLICT (profile_code)
            DO UPDATE
            SET
                profile_name = EXCLUDED.profile_name,
                source_type = EXCLUDED.source_type,
                source_location_mode = EXCLUDED.source_location_mode,
                default_capture_timing = EXCLUDED.default_capture_timing,
                requires_agent = EXCLUDED.requires_agent,
                description = EXCLUDED.description,
                status = EXCLUDED.status,
                metadata_json = EXCLUDED.metadata_json,
                updated_at = now()
            RETURNING capture_profile_id
            """
        )
        row = cur.fetchone()
    conn.commit()
    if row is None:
        raise RuntimeError("Failed to ensure S2W-7 POSTGRES capture profile")
    return int(row["capture_profile_id"])


def create_s2w7_capture_seed_graph(
    *,
    conn,
    suffix: str,
    profile_answer_language: str = "OTHER",
    required_capture_type: str = "POSTGRES_DATABASE_SNAPSHOT",
    capture_job_type: str = "STUDENT_DATABASE_SNAPSHOT",
) -> dict[str, Any]:
    prefix = f"s2w7-capture-{suffix}"
    pair = _find_unused_session_instance_pair(conn=conn, requires_capture_config=True)
    created_session_instance = False
    if pair is None:
        created = _create_session_instance_pair(
            conn=conn,
            suffix=suffix,
            requires_capture_config=True,
        )
        if created is None:
            raise RuntimeError("No eligible exam_session/generated_exam_instance pair for S2W-7 capture seed")
        pair = {
            "exam_session_id": int(created["exam_session_id"]),
            "generated_exam_instance_id": int(created["generated_exam_instance_id"]),
            "exam_version_id": int(created["exam_version_id"]),
        }
        created_session_instance = True

    created_by = _select_seed_user_id(conn=conn)
    grading_engine_id = _select_sql_engine_id(conn=conn)
    capture_profile_id = ensure_s2w7_postgres_capture_profile(conn=conn)
    user_map = _select_student_users_for_session(conn=conn, exam_session_id=int(pair["exam_session_id"]))

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO assessment.question_template (
                template_code,
                question_type,
                title,
                template_text,
                topic_code,
                skill_code,
                difficulty_level,
                default_score,
                generator_type,
                generator_version,
                status,
                created_by
            )
            VALUES (
                %s,
                'SQL_QUERY',
                %s,
                %s,
                'TOPIC1',
                'SKILL1',
                'MEDIUM',
                10.00,
                'PARAMETERIZED',
                '1.0.0',
                'ACTIVE',
                %s
            )
            RETURNING question_template_id
            """,
            (
                f"S2W7_CP_QT_{suffix}",
                f"S2W7 capture template {suffix}",
                "Capture-routed question for S2W-7 integration.",
                int(created_by),
            ),
        )
        template_row = cur.fetchone()
        if template_row is None:
            raise RuntimeError("Failed to insert S2W-7 capture question_template")

        cur.execute(
            """
            SELECT coalesce(max(question_order), 0) + 1 AS next_question_order
            FROM delivery.generated_exam_question
            WHERE generated_exam_instance_id = %s
            """,
            (int(pair["generated_exam_instance_id"]),),
        )
        order_row = cur.fetchone()
        next_question_order = int(order_row["next_question_order"]) if order_row is not None else 1

        cur.execute(
            """
            INSERT INTO delivery.generated_exam_question (
                generated_exam_instance_id,
                question_template_id,
                question_order,
                question_code,
                question_type,
                rendered_question_text,
                score,
                metadata_json
            )
            VALUES (%s, %s, %s, %s, 'SQL_QUERY', %s, %s, %s)
            RETURNING generated_exam_question_id
            """,
            (
                int(pair["generated_exam_instance_id"]),
                int(template_row["question_template_id"]),
                int(next_question_order),
                f"S2W7_CP_Q_{suffix}",
                f"S2W7 capture question {suffix}",
                "10.00",
                Jsonb({"source": prefix}),
            ),
        )
        question_row = cur.fetchone()
        if question_row is None:
            raise RuntimeError("Failed to insert S2W-7 capture generated_exam_question")

        cur.execute(
            """
            INSERT INTO delivery.generated_expected_answer (
                generated_exam_question_id,
                answer_order,
                solution_type,
                expected_payload,
                expected_payload_json,
                expected_hash,
                created_by,
                metadata_json
            )
            VALUES (%s, 1, 'SQL_RESULT', NULL, %s, NULL, %s, %s)
            RETURNING generated_expected_answer_id
            """,
            (
                int(question_row["generated_exam_question_id"]),
                Jsonb({"columns": ["value"], "rows": [[1]], "row_count": 1, "truncated": False}),
                int(created_by),
                Jsonb({"source": prefix}),
            ),
        )
        expected_row = cur.fetchone()
        if expected_row is None:
            raise RuntimeError("Failed to insert S2W-7 capture expected answer")

        cur.execute(
            """
            INSERT INTO submission.exam_submission (
                exam_session_id,
                generated_exam_instance_id,
                submission_status,
                submitted_at,
                sealed_at,
                seal_reason,
                created_at,
                updated_at,
                metadata_json
            )
            VALUES (%s, %s, 'SUBMITTED', now(), now(), 'STUDENT_SUBMIT', now(), now(), %s)
            RETURNING exam_submission_id
            """,
            (
                int(pair["exam_session_id"]),
                int(pair["generated_exam_instance_id"]),
                Jsonb({"source": prefix}),
            ),
        )
        submission_row = cur.fetchone()
        if submission_row is None:
            raise RuntimeError("Failed to insert S2W-7 capture exam_submission")

        cur.execute(
            """
            INSERT INTO submission.submission_seal (
                exam_submission_id,
                seal_idempotency_key,
                seal_status,
                seal_reason,
                sealed_at,
                server_time_at_seal,
                answer_count,
                submission_hash,
                metadata_json
            )
            VALUES (%s, %s, 'SEALED', 'STUDENT_SUBMIT', now(), now(), 1, NULL, %s)
            RETURNING submission_seal_id
            """,
            (
                int(submission_row["exam_submission_id"]),
                f"{prefix}-seal",
                Jsonb({"source": prefix}),
            ),
        )
        seal_row = cur.fetchone()
        if seal_row is None:
            raise RuntimeError("Failed to insert S2W-7 capture submission_seal")

        cur.execute(
            """
            INSERT INTO submission.answer_state (
                exam_submission_id,
                generated_exam_question_id,
                answer_type,
                answer_text,
                answer_hash,
                answer_length,
                client_version,
                server_version,
                client_saved_at,
                last_saved_at,
                answer_status,
                metadata_json
            )
            VALUES (
                %s,
                %s,
                'SQL_TEXT',
                %s,
                repeat('f', 64),
                %s,
                1,
                1,
                now(),
                now(),
                'SEALED',
                %s
            )
            RETURNING answer_state_id
            """,
            (
                int(submission_row["exam_submission_id"]),
                int(question_row["generated_exam_question_id"]),
                "SELECT 42 AS value",
                len("SELECT 42 AS value"),
                Jsonb({"source": prefix}),
            ),
        )
        answer_state_row = cur.fetchone()
        if answer_state_row is None:
            raise RuntimeError("Failed to insert S2W-7 capture answer_state")

        cur.execute(
            """
            INSERT INTO submission.sealed_answer (
                submission_seal_id,
                exam_submission_id,
                generated_exam_question_id,
                answer_state_id,
                answer_type,
                answer_text,
                answer_hash,
                answer_length,
                sealed_at,
                metadata_json
            )
            VALUES (%s, %s, %s, %s, 'SQL_TEXT', %s, repeat('d', 64), %s, now(), %s)
            RETURNING sealed_answer_id
            """,
            (
                int(seal_row["submission_seal_id"]),
                int(submission_row["exam_submission_id"]),
                int(question_row["generated_exam_question_id"]),
                int(answer_state_row["answer_state_id"]),
                "SELECT 1 AS value",
                len("SELECT 1 AS value"),
                Jsonb({"source": prefix}),
            ),
        )
        sealed_row = cur.fetchone()
        if sealed_row is None:
            raise RuntimeError("Failed to insert S2W-7 capture sealed_answer")

        cur.execute(
            """
            INSERT INTO assessment.question_grading_profile (
                question_template_id,
                exam_version_id,
                input_source,
                answer_language,
                requires_capture,
                required_capture_type,
                capture_profile_id,
                grading_engine_id,
                comparison_method,
                timeout_seconds,
                max_score,
                status,
                metadata_json
            )
            VALUES (
                %s,
                %s,
                'STUDENT_DATABASE_CAPTURE',
                %s,
                true,
                %s,
                %s,
                %s,
                'CUSTOM',
                30,
                NULL,
                'ACTIVE',
                %s
            )
            RETURNING question_grading_profile_id
            """,
            (
                int(template_row["question_template_id"]),
                int(pair["exam_version_id"]),
                str(profile_answer_language),
                str(required_capture_type),
                int(capture_profile_id),
                int(grading_engine_id),
                Jsonb({"source": prefix}),
            ),
        )
        profile_row = cur.fetchone()
        if profile_row is None:
            raise RuntimeError("Failed to insert S2W-7 capture question_grading_profile")

        cur.execute(
            """
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
                '1970-01-01 00:00:00+00'::timestamptz,
                0,
                %s,
                now(),
                now()
            )
            RETURNING grading_job_id
            """,
            (
                int(submission_row["exam_submission_id"]),
                int(seal_row["submission_seal_id"]),
                int(pair["exam_session_id"]),
                int(pair["generated_exam_instance_id"]),
                prefix,
                Jsonb({"source": prefix}),
            ),
        )
        grading_job_row = cur.fetchone()
        if grading_job_row is None:
            raise RuntimeError("Failed to insert S2W-7 capture grading_job")

        cur.execute(
            """
            INSERT INTO capture.capture_job (
                exam_submission_id,
                submission_seal_id,
                exam_session_id,
                generated_exam_instance_id,
                idempotency_key,
                capture_type,
                capture_status,
                requested_at,
                attempt_count,
                metadata_json
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                'QUEUED',
                '1970-01-01 00:00:00+00'::timestamptz,
                0,
                %s
            )
            RETURNING capture_job_id
            """,
            (
                int(submission_row["exam_submission_id"]),
                int(seal_row["submission_seal_id"]),
                int(pair["exam_session_id"]),
                int(pair["generated_exam_instance_id"]),
                prefix,
                str(capture_job_type),
                Jsonb({"source": prefix}),
            ),
        )
        capture_job_row = cur.fetchone()
        if capture_job_row is None:
            raise RuntimeError("Failed to insert S2W-7 capture job")

    conn.commit()

    return {
        "suffix": suffix,
        "prefix": prefix,
        "exam_session_id": int(pair["exam_session_id"]),
        "generated_exam_instance_id": int(pair["generated_exam_instance_id"]),
        "exam_version_id": int(pair["exam_version_id"]),
        "created_session_instance": bool(created_session_instance),
        "question_template_id": int(template_row["question_template_id"]),
        "generated_exam_question_id": int(question_row["generated_exam_question_id"]),
        "generated_expected_answer_id": int(expected_row["generated_expected_answer_id"]),
        "question_grading_profile_id": int(profile_row["question_grading_profile_id"]),
        "exam_submission_id": int(submission_row["exam_submission_id"]),
        "submission_seal_id": int(seal_row["submission_seal_id"]),
        "answer_state_id": int(answer_state_row["answer_state_id"]),
        "sealed_answer_id": int(sealed_row["sealed_answer_id"]),
        "grading_job_id": int(grading_job_row["grading_job_id"]),
        "capture_job_id": int(capture_job_row["capture_job_id"]),
        "capture_profile_id": int(capture_profile_id),
        "required_capture_type": str(required_capture_type),
        "capture_job_type": str(capture_job_type),
        "profile_answer_language": str(profile_answer_language),
        "owner_student_id": user_map["owner_student_id"],
        "owner_user_id": user_map["owner_user_id"],
        "non_owner_user_id": user_map["non_owner_user_id"],
    }


def cleanup_s2w7_prefixed_rows(
    *,
    conn,
    prefix_patterns: Iterable[str] | None = None,
) -> dict[str, int]:
    patterns = [str(item) for item in (prefix_patterns or S2W7_PREFIX_PATTERNS)]

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT grading_job_id, exam_submission_id
            FROM grading.grading_job
            WHERE idempotency_key ILIKE ANY(%s)
               OR coalesce(metadata_json ->> 'source', '') ILIKE ANY(%s)
            """,
            (patterns, patterns),
        )
        grading_rows = cur.fetchall()

        cur.execute(
            """
            SELECT capture_job_id, exam_submission_id
            FROM capture.capture_job
            WHERE idempotency_key ILIKE ANY(%s)
               OR coalesce(metadata_json ->> 'source', '') ILIKE ANY(%s)
            """,
            (patterns, patterns),
        )
        capture_rows = cur.fetchall()

        cur.execute(
            """
            SELECT submission_seal_id, exam_submission_id
            FROM submission.submission_seal
            WHERE seal_idempotency_key ILIKE ANY(%s)
               OR coalesce(metadata_json ->> 'source', '') ILIKE ANY(%s)
            """,
            (patterns, patterns),
        )
        seal_rows = cur.fetchall()

        cur.execute(
            """
            SELECT exam_submission_id, exam_session_id, generated_exam_instance_id
            FROM submission.exam_submission
            WHERE coalesce(metadata_json ->> 'source', '') ILIKE ANY(%s)
            """,
            (patterns,),
        )
        submission_rows = cur.fetchall()

        cur.execute(
            """
            SELECT exam_session_id
            FROM delivery.exam_session
            WHERE session_code ILIKE ANY(%s)
            """,
            (list(S2W7_SESSION_CODE_PATTERNS),),
        )
        session_rows = cur.fetchall()

        cur.execute(
            """
            SELECT exam_assignment_id, exam_sitting_id
            FROM delivery.exam_assignment
            WHERE coalesce(note, '') ILIKE ANY(%s)
            """,
            (list(S2W7_ASSIGNMENT_NOTE_PATTERNS),),
        )
        assignment_rows = cur.fetchall()

        cur.execute(
            """
            SELECT exam_sitting_id, exam_version_id
            FROM delivery.exam_sitting
            WHERE sitting_code ILIKE ANY(%s)
            """,
            (list(S2W7_SITTING_CODE_PATTERNS),),
        )
        sitting_rows = cur.fetchall()

        cur.execute(
            """
            SELECT exam_id, class_section_id
            FROM assessment.exam
            WHERE exam_code ILIKE ANY(%s)
            """,
            (list(S2W7_EXAM_CODE_PATTERNS),),
        )
        exam_rows = cur.fetchall()

        cur.execute(
            """
            SELECT class_section_id, course_offering_id
            FROM academic.class_section
            WHERE class_code ILIKE ANY(%s)
            """,
            (list(S2W7_CLASS_CODE_PATTERNS),),
        )
        class_rows = cur.fetchall()

        cur.execute(
            """
            SELECT course_offering_id, course_id, term_id
            FROM academic.course_offering
            WHERE offering_code ILIKE ANY(%s)
            """,
            (list(S2W7_OFFERING_CODE_PATTERNS),),
        )
        offering_rows = cur.fetchall()

        cur.execute(
            """
            SELECT course_id, department_id
            FROM academic.course
            WHERE course_code ILIKE ANY(%s)
            """,
            (list(S2W7_COURSE_CODE_PATTERNS),),
        )
        course_rows = cur.fetchall()

        cur.execute(
            """
            SELECT term_id
            FROM academic.term
            WHERE term_code ILIKE ANY(%s)
            """,
            (list(S2W7_TERM_CODE_PATTERNS),),
        )
        term_rows = cur.fetchall()

        cur.execute(
            """
            SELECT department_id
            FROM academic.department
            WHERE department_code ILIKE ANY(%s)
            """,
            (list(S2W7_DEPARTMENT_CODE_PATTERNS),),
        )
        department_rows = cur.fetchall()

        cur.execute(
            """
            SELECT question_grading_profile_id
            FROM assessment.question_grading_profile
            WHERE coalesce(metadata_json ->> 'source', '') ILIKE ANY(%s)
            """,
            (patterns,),
        )
        profile_rows = cur.fetchall()

        cur.execute(
            """
            SELECT question_template_id
            FROM assessment.question_template
            WHERE template_code ILIKE ANY(%s)
            """,
            (list(S2W7_TEMPLATE_CODE_PATTERNS),),
        )
        template_rows = cur.fetchall()

        cur.execute(
            """
            SELECT generated_exam_question_id
            FROM delivery.generated_exam_question
            WHERE question_code ILIKE ANY(%s)
               OR coalesce(metadata_json ->> 'source', '') ILIKE ANY(%s)
            """,
            (list(S2W7_QUESTION_CODE_PATTERNS), patterns),
        )
        generated_question_rows = cur.fetchall()

        grading_job_ids = _to_int_set(row["grading_job_id"] for row in grading_rows)
        capture_job_ids = _to_int_set(row["capture_job_id"] for row in capture_rows)
        submission_seal_ids = _to_int_set(row["submission_seal_id"] for row in seal_rows)

        exam_submission_ids = _to_int_set(row["exam_submission_id"] for row in submission_rows)
        exam_submission_ids.update(_to_int_set(row["exam_submission_id"] for row in grading_rows))
        exam_submission_ids.update(_to_int_set(row["exam_submission_id"] for row in capture_rows))
        exam_submission_ids.update(_to_int_set(row["exam_submission_id"] for row in seal_rows))

        session_ids = _to_int_set(row["exam_session_id"] for row in session_rows)
        session_ids.update(_to_int_set(row["exam_session_id"] for row in submission_rows))
        exam_assignment_ids = _to_int_set(row["exam_assignment_id"] for row in assignment_rows)
        exam_sitting_ids = _to_int_set(row["exam_sitting_id"] for row in assignment_rows)
        exam_sitting_ids.update(_to_int_set(row["exam_sitting_id"] for row in sitting_rows))
        exam_version_ids = _to_int_set(row["exam_version_id"] for row in sitting_rows)
        exam_ids = _to_int_set(row["exam_id"] for row in exam_rows)
        class_section_ids = _to_int_set(row["class_section_id"] for row in exam_rows)
        class_section_ids.update(_to_int_set(row["class_section_id"] for row in class_rows))
        course_offering_ids = _to_int_set(row["course_offering_id"] for row in class_rows)
        course_offering_ids.update(_to_int_set(row["course_offering_id"] for row in offering_rows))
        course_ids = _to_int_set(row["course_id"] for row in offering_rows)
        course_ids.update(_to_int_set(row["course_id"] for row in course_rows))
        term_ids = _to_int_set(row["term_id"] for row in offering_rows)
        term_ids.update(_to_int_set(row["term_id"] for row in term_rows))
        department_ids = _to_int_set(row["department_id"] for row in course_rows)
        department_ids.update(_to_int_set(row["department_id"] for row in department_rows))
        generated_instance_ids: set[int] = set()
        if session_ids:
            cur.execute(
                """
                SELECT generated_exam_instance_id
                FROM delivery.generated_exam_instance
                WHERE exam_session_id = ANY(%s)
                """,
                (list(session_ids),),
            )
            generated_instance_ids = _to_int_set(
                row["generated_exam_instance_id"] for row in cur.fetchall()
            )
        generated_instance_ids.update(
            _to_int_set(row["generated_exam_instance_id"] for row in submission_rows)
        )

        if generated_instance_ids:
            cur.execute(
                """
                SELECT exam_submission_id
                FROM submission.exam_submission
                WHERE generated_exam_instance_id = ANY(%s)
                """,
                (list(generated_instance_ids),),
            )
            exam_submission_ids.update(
                _to_int_set(row["exam_submission_id"] for row in cur.fetchall())
            )
        if session_ids:
            cur.execute(
                """
                SELECT exam_submission_id
                FROM submission.exam_submission
                WHERE exam_session_id = ANY(%s)
                """,
                (list(session_ids),),
            )
            exam_submission_ids.update(
                _to_int_set(row["exam_submission_id"] for row in cur.fetchall())
            )

        question_profile_ids = _to_int_set(row["question_grading_profile_id"] for row in profile_rows)
        question_template_ids = _to_int_set(row["question_template_id"] for row in template_rows)
        generated_question_ids = _to_int_set(
            row["generated_exam_question_id"] for row in generated_question_rows
        )
        if generated_instance_ids:
            cur.execute(
                """
                SELECT generated_exam_question_id
                FROM delivery.generated_exam_question
                WHERE generated_exam_instance_id = ANY(%s)
                """,
                (list(generated_instance_ids),),
            )
            generated_question_ids.update(
                _to_int_set(row["generated_exam_question_id"] for row in cur.fetchall())
            )

        if exam_submission_ids:
            cur.execute(
                """
                SELECT grading_job_id, exam_submission_id
                FROM grading.grading_job
                WHERE exam_submission_id = ANY(%s)
                """,
                (list(exam_submission_ids),),
            )
            linked_grading_rows = cur.fetchall()
            grading_job_ids.update(_to_int_set(row["grading_job_id"] for row in linked_grading_rows))
            exam_submission_ids.update(_to_int_set(row["exam_submission_id"] for row in linked_grading_rows))

        if submission_seal_ids:
            cur.execute(
                """
                SELECT grading_job_id, exam_submission_id
                FROM grading.grading_job
                WHERE submission_seal_id = ANY(%s)
                """,
                (list(submission_seal_ids),),
            )
            seal_linked_grading_rows = cur.fetchall()
            grading_job_ids.update(_to_int_set(row["grading_job_id"] for row in seal_linked_grading_rows))
            exam_submission_ids.update(_to_int_set(row["exam_submission_id"] for row in seal_linked_grading_rows))

        task_ids: list[int] = []
        if grading_job_ids:
            cur.execute(
                """
                SELECT question_grading_task_id
                FROM grading.question_grading_task
                WHERE grading_job_id = ANY(%s)
                """,
                (list(grading_job_ids),),
            )
            task_ids = [int(row["question_grading_task_id"]) for row in cur.fetchall()]

        deleted_submission_scores = _delete_where_any(
            cur,
            table="grading.submission_score",
            column="grading_job_id",
            ids=list(grading_job_ids),
        )

        deleted_question_scores = _delete_where_any(
            cur,
            table="grading.question_score",
            column="question_grading_task_id",
            ids=task_ids,
        )
        deleted_comparisons = _delete_where_any(
            cur,
            table="grading.expected_actual_comparison",
            column="question_grading_task_id",
            ids=task_ids,
        )
        deleted_actual_results = _delete_where_any(
            cur,
            table="grading.actual_result",
            column="question_grading_task_id",
            ids=task_ids,
        )

        deleted_grading_events = _delete_where_any(
            cur,
            table="grading.grading_event",
            column="grading_job_id",
            ids=list(grading_job_ids),
        )
        deleted_grading_tasks = _delete_where_any(
            cur,
            table="grading.question_grading_task",
            column="grading_job_id",
            ids=list(grading_job_ids),
        )
        deleted_grading_runs = _delete_where_any(
            cur,
            table="grading.grading_run",
            column="grading_job_id",
            ids=list(grading_job_ids),
        )
        deleted_grading_jobs = _delete_where_any(
            cur,
            table="grading.grading_job",
            column="grading_job_id",
            ids=list(grading_job_ids),
        )

        deleted_capture_dataset_rows = 0
        if capture_job_ids:
            cur.execute(
                """
                DELETE FROM capture.capture_dataset_row
                WHERE capture_dataset_id IN (
                    SELECT capture_dataset_id
                    FROM capture.capture_dataset
                    WHERE capture_job_id = ANY(%s)
                )
                """,
                (list(capture_job_ids),),
            )
            deleted_capture_dataset_rows = max(int(cur.rowcount or 0), 0)

        deleted_capture_datasets = _delete_where_any(
            cur,
            table="capture.capture_dataset",
            column="capture_job_id",
            ids=list(capture_job_ids),
        )
        deleted_capture_artifacts = _delete_where_any(
            cur,
            table="capture.capture_artifact",
            column="capture_job_id",
            ids=list(capture_job_ids),
        )
        deleted_capture_events = _delete_where_any(
            cur,
            table="capture.capture_job_event",
            column="capture_job_id",
            ids=list(capture_job_ids),
        )
        deleted_capture_jobs = _delete_where_any(
            cur,
            table="capture.capture_job",
            column="capture_job_id",
            ids=list(capture_job_ids),
        )

        deleted_sealed_answers_by_seal = _delete_where_any(
            cur,
            table="submission.sealed_answer",
            column="submission_seal_id",
            ids=list(submission_seal_ids),
        )
        deleted_sealed_answers_by_submission = _delete_where_any(
            cur,
            table="submission.sealed_answer",
            column="exam_submission_id",
            ids=list(exam_submission_ids),
        )

        answer_save_batch_ids: set[int] = set()
        if exam_submission_ids:
            cur.execute(
                """
                SELECT answer_save_batch_id
                FROM submission.answer_save_batch
                WHERE exam_submission_id = ANY(%s)
                """,
                (list(exam_submission_ids),),
            )
            answer_save_batch_ids = _to_int_set(row["answer_save_batch_id"] for row in cur.fetchall())

        deleted_answer_save_items = _delete_where_any(
            cur,
            table="submission.answer_save_item",
            column="answer_save_batch_id",
            ids=list(answer_save_batch_ids),
        )
        deleted_answer_save_batches = _delete_where_any(
            cur,
            table="submission.answer_save_batch",
            column="exam_submission_id",
            ids=list(exam_submission_ids),
        )
        deleted_answer_conflicts = _delete_where_any(
            cur,
            table="submission.answer_conflict",
            column="exam_submission_id",
            ids=list(exam_submission_ids),
        )

        deleted_answer_states = _delete_where_any(
            cur,
            table="submission.answer_state",
            column="exam_submission_id",
            ids=list(exam_submission_ids),
        )

        deleted_submission_seals_by_id = _delete_where_any(
            cur,
            table="submission.submission_seal",
            column="submission_seal_id",
            ids=list(submission_seal_ids),
        )
        deleted_submission_seals_by_submission = _delete_where_any(
            cur,
            table="submission.submission_seal",
            column="exam_submission_id",
            ids=list(exam_submission_ids),
        )

        deleted_submission_dispatch_outcomes = _delete_where_any(
            cur,
            table="submission.submission_dispatch_outcome",
            column="exam_submission_id",
            ids=list(exam_submission_ids),
        )

        deleted_submissions = _delete_where_any(
            cur,
            table="submission.exam_submission",
            column="exam_submission_id",
            ids=list(exam_submission_ids),
        )

        deleted_question_profiles = _delete_where_any(
            cur,
            table="assessment.question_grading_profile",
            column="question_grading_profile_id",
            ids=list(question_profile_ids),
        )

        deleted_generated_expected_answers = 0
        if generated_question_ids:
            deleted_sealed_answers_by_question = _delete_where_any(
                cur,
                table="submission.sealed_answer",
                column="generated_exam_question_id",
                ids=list(generated_question_ids),
            )
            deleted_answer_states_by_question = _delete_where_any(
                cur,
                table="submission.answer_state",
                column="generated_exam_question_id",
                ids=list(generated_question_ids),
            )
            deleted_answer_conflicts_by_question = _delete_where_any(
                cur,
                table="submission.answer_conflict",
                column="generated_exam_question_id",
                ids=list(generated_question_ids),
            )
            cur.execute(
                """
                DELETE FROM delivery.generated_expected_answer
                WHERE generated_exam_question_id = ANY(%s)
                """,
                (list(generated_question_ids),),
            )
            deleted_generated_expected_answers = max(int(cur.rowcount or 0), 0)
        else:
            deleted_sealed_answers_by_question = 0
            deleted_answer_states_by_question = 0
            deleted_answer_conflicts_by_question = 0

        deleted_generated_questions = _delete_where_any(
            cur,
            table="delivery.generated_exam_question",
            column="generated_exam_question_id",
            ids=list(generated_question_ids),
        )

        deleted_generated_instances = _delete_where_any(
            cur,
            table="delivery.generated_exam_instance",
            column="generated_exam_instance_id",
            ids=list(generated_instance_ids),
        )
        deleted_sessions = _delete_where_any(
            cur,
            table="delivery.exam_session",
            column="exam_session_id",
            ids=list(session_ids),
        )

        deleted_exam_assignments = _delete_where_any(
            cur,
            table="delivery.exam_assignment",
            column="exam_assignment_id",
            ids=list(exam_assignment_ids),
        )
        deleted_exam_sittings = _delete_where_any(
            cur,
            table="delivery.exam_sitting",
            column="exam_sitting_id",
            ids=list(exam_sitting_ids),
        )
        deleted_exam_versions = _delete_where_any(
            cur,
            table="assessment.exam_version",
            column="exam_version_id",
            ids=list(exam_version_ids),
        )
        deleted_exams = _delete_where_any(
            cur,
            table="assessment.exam",
            column="exam_id",
            ids=list(exam_ids),
        )
        deleted_class_sections = _delete_where_any(
            cur,
            table="academic.class_section",
            column="class_section_id",
            ids=list(class_section_ids),
        )
        deleted_course_offerings = _delete_where_any(
            cur,
            table="academic.course_offering",
            column="course_offering_id",
            ids=list(course_offering_ids),
        )
        deleted_courses = _delete_where_any(
            cur,
            table="academic.course",
            column="course_id",
            ids=list(course_ids),
        )
        deleted_terms = _delete_where_any(
            cur,
            table="academic.term",
            column="term_id",
            ids=list(term_ids),
        )
        deleted_departments = _delete_where_any(
            cur,
            table="academic.department",
            column="department_id",
            ids=list(department_ids),
        )

        deleted_question_templates = _delete_where_any(
            cur,
            table="assessment.question_template",
            column="question_template_id",
            ids=list(question_template_ids),
        )

    conn.commit()

    return {
        "deleted_submission_scores": deleted_submission_scores,
        "deleted_question_scores": deleted_question_scores,
        "deleted_comparisons": deleted_comparisons,
        "deleted_actual_results": deleted_actual_results,
        "deleted_grading_tasks": deleted_grading_tasks,
        "deleted_grading_runs": deleted_grading_runs,
        "deleted_grading_events": deleted_grading_events,
        "deleted_grading_jobs": deleted_grading_jobs,
        "deleted_capture_dataset_rows": deleted_capture_dataset_rows,
        "deleted_capture_datasets": deleted_capture_datasets,
        "deleted_capture_artifacts": deleted_capture_artifacts,
        "deleted_capture_events": deleted_capture_events,
        "deleted_capture_jobs": deleted_capture_jobs,
        "deleted_sealed_answers": (
            deleted_sealed_answers_by_seal
            + deleted_sealed_answers_by_submission
            + deleted_sealed_answers_by_question
        ),
        "deleted_answer_save_items": deleted_answer_save_items,
        "deleted_answer_save_batches": deleted_answer_save_batches,
        "deleted_answer_conflicts": deleted_answer_conflicts + deleted_answer_conflicts_by_question,
        "deleted_answer_states": deleted_answer_states + deleted_answer_states_by_question,
        "deleted_submission_seals": deleted_submission_seals_by_id + deleted_submission_seals_by_submission,
        "deleted_submission_dispatch_outcomes": deleted_submission_dispatch_outcomes,
        "deleted_submissions": deleted_submissions,
        "deleted_generated_expected_answers": deleted_generated_expected_answers,
        "deleted_generated_questions": deleted_generated_questions,
        "deleted_generated_instances": deleted_generated_instances,
        "deleted_sessions": deleted_sessions,
        "deleted_exam_assignments": deleted_exam_assignments,
        "deleted_exam_sittings": deleted_exam_sittings,
        "deleted_exam_versions": deleted_exam_versions,
        "deleted_exams": deleted_exams,
        "deleted_class_sections": deleted_class_sections,
        "deleted_course_offerings": deleted_course_offerings,
        "deleted_courses": deleted_courses,
        "deleted_terms": deleted_terms,
        "deleted_departments": deleted_departments,
        "deleted_question_profiles": deleted_question_profiles,
        "deleted_question_templates": deleted_question_templates,
    }
