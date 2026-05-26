"""Repository layer for assessment authoring APIs."""

from __future__ import annotations

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.infrastructure.database.connection import open_connection


class AssessmentRepository:
    """SQL-only data access for assessment authoring."""

    def list_assessment_types(self, *, limit: int, offset: int) -> tuple[list[dict], int]:
        list_query = """
        SELECT
            assessment_type_id,
            type_code,
            type_name,
            description,
            is_active,
            created_at,
            updated_at
        FROM assessment.assessment_type
        ORDER BY assessment_type_id
        LIMIT %s OFFSET %s
        """
        count_query = "SELECT count(*)::bigint AS total FROM assessment.assessment_type"

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(list_query, (limit, offset))
                rows = cur.fetchall()
                cur.execute(count_query)
                total_row = cur.fetchone()

        total = int(total_row["total"]) if total_row else 0
        return rows, total

    def list_exams(self, *, limit: int, offset: int) -> tuple[list[dict], int]:
        list_query = """
        SELECT
            exam_id,
            class_section_id,
            assessment_type_id,
            exam_code,
            exam_name,
            description,
            exam_status,
            created_by,
            created_at,
            updated_at
        FROM assessment.exam
        ORDER BY exam_id DESC
        LIMIT %s OFFSET %s
        """
        count_query = "SELECT count(*)::bigint AS total FROM assessment.exam"

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(list_query, (limit, offset))
                rows = cur.fetchall()
                cur.execute(count_query)
                total_row = cur.fetchone()

        total = int(total_row["total"]) if total_row else 0
        return rows, total

    def create_exam(self, *, payload: dict, created_by: int) -> dict:
        query = """
        INSERT INTO assessment.exam (
            class_section_id,
            assessment_type_id,
            exam_code,
            exam_name,
            description,
            exam_status,
            created_by,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, now(), now())
        RETURNING
            exam_id,
            class_section_id,
            assessment_type_id,
            exam_code,
            exam_name,
            description,
            exam_status,
            created_by,
            created_at,
            updated_at
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(payload["class_section_id"]) if payload.get("class_section_id") is not None else None,
                        int(payload["assessment_type_id"]),
                        str(payload["exam_code"]).strip(),
                        str(payload["exam_name"]).strip(),
                        payload.get("description"),
                        str(payload.get("exam_status") or "DRAFT").strip().upper(),
                        created_by,
                    ),
                )
                row = cur.fetchone()
            conn.commit()

        if row is None:
            raise RuntimeError("Failed to create exam")
        return row

    def get_exam_by_id(self, exam_id: int) -> dict | None:
        query = """
        SELECT
            exam_id,
            class_section_id,
            assessment_type_id,
            exam_code,
            exam_name,
            description,
            exam_status,
            created_by,
            created_at,
            updated_at
        FROM assessment.exam
        WHERE exam_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (exam_id,))
                return cur.fetchone()

    def patch_exam(self, *, exam_id: int, payload: dict) -> dict | None:
        allowed = {
            "class_section_id": "class_section_id = %s",
            "assessment_type_id": "assessment_type_id = %s",
            "exam_code": "exam_code = %s",
            "exam_name": "exam_name = %s",
            "description": "description = %s",
            "exam_status": "exam_status = %s",
        }

        updates: list[str] = []
        values: list[object] = []

        for key, clause in allowed.items():
            if key not in payload:
                continue

            value = payload[key]
            if key in {"exam_code", "exam_status"} and value is not None:
                value = str(value).strip().upper()
            elif key == "exam_name" and value is not None:
                value = str(value).strip()
            elif key in {"class_section_id", "assessment_type_id"} and value is not None:
                value = int(value)

            updates.append(clause)
            values.append(value)

        if not updates:
            return self.get_exam_by_id(exam_id)

        values.append(exam_id)

        query = f"""
        UPDATE assessment.exam
        SET
            {", ".join(updates)},
            updated_at = now()
        WHERE exam_id = %s
        RETURNING
            exam_id,
            class_section_id,
            assessment_type_id,
            exam_code,
            exam_name,
            description,
            exam_status,
            created_by,
            created_at,
            updated_at
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, tuple(values))
                row = cur.fetchone()
            conn.commit()

        return row


    def create_exam_version(self, *, exam_id: int, payload: dict) -> dict:
        query = """
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
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now())
        RETURNING
            exam_version_id,
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
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        exam_id,
                        int(payload["version_no"]),
                        payload.get("version_label"),
                        int(payload["duration_seconds"]),
                        payload["total_score"],
                        bool(payload.get("shuffle_questions", False)),
                        bool(payload.get("shuffle_options", False)),
                        str(payload["randomization_mode"]).strip().upper(),
                        str(payload.get("status") or "DRAFT").strip().upper(),
                    ),
                )
                row = cur.fetchone()
            conn.commit()

        if row is None:
            raise RuntimeError("Failed to create exam version")
        return row

    def get_exam_version_by_id(self, version_id: int) -> dict | None:
        query = """
        SELECT
            exam_version_id,
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
        FROM assessment.exam_version
        WHERE exam_version_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (version_id,))
                return cur.fetchone()

    def patch_exam_version(self, *, version_id: int, payload: dict) -> dict | None:
        query = """
        UPDATE assessment.exam_version
        SET
            version_label = coalesce(%s, version_label),
            duration_seconds = coalesce(%s, duration_seconds),
            total_score = coalesce(%s, total_score),
            shuffle_questions = coalesce(%s, shuffle_questions),
            shuffle_options = coalesce(%s, shuffle_options),
            randomization_mode = coalesce(%s, randomization_mode),
            status = coalesce(%s, status),
            updated_at = now()
        WHERE exam_version_id = %s
        RETURNING
            exam_version_id,
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
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        payload.get("version_label"),
                        payload.get("duration_seconds"),
                        payload.get("total_score"),
                        payload.get("shuffle_questions"),
                        payload.get("shuffle_options"),
                        str(payload["randomization_mode"]).strip().upper()
                        if payload.get("randomization_mode") is not None
                        else None,
                        str(payload["status"]).strip().upper() if payload.get("status") is not None else None,
                        version_id,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        return row

    def publish_exam_version(self, *, version_id: int, published_by: int) -> dict | None:
        query = """
        UPDATE assessment.exam_version
        SET
            status = 'PUBLISHED',
            published_at = now(),
            published_by = %s,
            updated_at = now()
        WHERE exam_version_id = %s
        RETURNING
            exam_version_id,
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
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (published_by, version_id))
                row = cur.fetchone()
            conn.commit()
        return row

    def list_question_banks(self, *, limit: int, offset: int) -> tuple[list[dict], int]:
        list_query = """
        SELECT
            question_bank_id,
            course_id,
            bank_code,
            bank_name,
            description,
            owner_user_id,
            status,
            created_at,
            updated_at
        FROM assessment.question_bank
        ORDER BY question_bank_id DESC
        LIMIT %s OFFSET %s
        """
        count_query = "SELECT count(*)::bigint AS total FROM assessment.question_bank"

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(list_query, (limit, offset))
                rows = cur.fetchall()
                cur.execute(count_query)
                total_row = cur.fetchone()

        total = int(total_row["total"]) if total_row else 0
        return rows, total

    def create_question_bank(self, *, payload: dict, actor_user_id: int) -> dict:
        owner_user_id = payload.get("owner_user_id")
        if owner_user_id is None:
            owner_user_id = actor_user_id

        query = """
        INSERT INTO assessment.question_bank (
            course_id,
            bank_code,
            bank_name,
            description,
            owner_user_id,
            status,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, now(), now())
        RETURNING
            question_bank_id,
            course_id,
            bank_code,
            bank_name,
            description,
            owner_user_id,
            status,
            created_at,
            updated_at
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        payload.get("course_id"),
                        str(payload["bank_code"]).strip(),
                        str(payload["bank_name"]).strip(),
                        payload.get("description"),
                        owner_user_id,
                        str(payload.get("status") or "DRAFT").strip().upper(),
                    ),
                )
                row = cur.fetchone()
            conn.commit()

        if row is None:
            raise RuntimeError("Failed to create question bank")
        return row

    def list_questions(self, *, limit: int, offset: int) -> tuple[list[dict], int]:
        list_query = """
        SELECT
            question_template_id,
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
            created_by,
            created_at,
            updated_at
        FROM assessment.question_template
        ORDER BY question_template_id DESC
        LIMIT %s OFFSET %s
        """
        count_query = "SELECT count(*)::bigint AS total FROM assessment.question_template"

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(list_query, (limit, offset))
                rows = cur.fetchall()
                cur.execute(count_query)
                total_row = cur.fetchone()

        total = int(total_row["total"]) if total_row else 0
        return rows, total

    def create_question(self, *, payload: dict, created_by: int, conn=None) -> dict:
        query = """
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
            created_by,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now())
        RETURNING
            question_template_id,
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
            created_by,
            created_at,
            updated_at
        """

        if conn is not None:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        str(payload["template_code"]).strip(),
                        str(payload["question_type"]).strip().upper(),
                        payload.get("title"),
                        str(payload["template_text"]),
                        payload.get("topic_code"),
                        payload.get("skill_code"),
                        payload.get("difficulty_level"),
                        payload["default_score"],
                        str(payload["generator_type"]).strip().upper(),
                        payload.get("generator_version"),
                        str(payload.get("status") or "DRAFT").strip().upper(),
                        created_by,
                    ),
                )
                row = cur.fetchone()
        else:
            with open_connection() as db_conn:
                with db_conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        query,
                        (
                            str(payload["template_code"]).strip(),
                            str(payload["question_type"]).strip().upper(),
                            payload.get("title"),
                            str(payload["template_text"]),
                            payload.get("topic_code"),
                            payload.get("skill_code"),
                            payload.get("difficulty_level"),
                            payload["default_score"],
                            str(payload["generator_type"]).strip().upper(),
                            payload.get("generator_version"),
                            str(payload.get("status") or "DRAFT").strip().upper(),
                            created_by,
                        ),
                    )
                    row = cur.fetchone()
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to create question")

        return row

    def link_question_to_bank(self, *, question_template_id: int, question_bank_id: int, added_by: int) -> None:
        query = """
        INSERT INTO assessment.question_template_bank (
            question_bank_id,
            question_template_id,
            added_at,
            added_by,
            is_active
        )
        VALUES (%s, %s, now(), %s, true)
        ON CONFLICT (question_bank_id, question_template_id)
        DO UPDATE SET
            is_active = true,
            added_by = excluded.added_by,
            added_at = now()
        """
        with open_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (question_bank_id, question_template_id, added_by))
            conn.commit()

    def get_question_by_id(self, question_id: int, conn=None) -> dict | None:
        query = """
        SELECT
            question_template_id,
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
            created_by,
            created_at,
            updated_at
        FROM assessment.question_template
        WHERE question_template_id = %s
        LIMIT 1
        """
        if conn is not None:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (question_id,))
                return cur.fetchone()
        with open_connection() as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (question_id,))
                return cur.fetchone()

    def get_question_template_by_id(self, question_template_id: int, conn=None) -> dict | None:
        return self.get_question_by_id(int(question_template_id), conn=conn)

    def get_question_by_template_code(self, template_code: str, conn=None) -> dict | None:
        query = """
        SELECT
            question_template_id,
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
            created_by,
            created_at,
            updated_at
        FROM assessment.question_template
        WHERE template_code = %s
        LIMIT 1
        """
        if conn is not None:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (str(template_code).strip(),))
                return cur.fetchone()
        with open_connection() as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (str(template_code).strip(),))
                return cur.fetchone()

    def patch_question(self, *, question_id: int, payload: dict, conn=None) -> dict | None:
        query = """
        UPDATE assessment.question_template
        SET
            title = coalesce(%s, title),
            template_text = coalesce(%s, template_text),
            topic_code = coalesce(%s, topic_code),
            skill_code = coalesce(%s, skill_code),
            difficulty_level = coalesce(%s, difficulty_level),
            default_score = coalesce(%s, default_score),
            generator_type = coalesce(%s, generator_type),
            generator_version = coalesce(%s, generator_version),
            status = coalesce(%s, status),
            updated_at = now()
        WHERE question_template_id = %s
        RETURNING
            question_template_id,
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
            created_by,
            created_at,
            updated_at
        """

        if conn is not None:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        payload.get("title"),
                        payload.get("template_text"),
                        payload.get("topic_code"),
                        payload.get("skill_code"),
                        payload.get("difficulty_level"),
                        payload.get("default_score"),
                        str(payload["generator_type"]).strip().upper()
                        if payload.get("generator_type") is not None
                        else None,
                        payload.get("generator_version"),
                        str(payload["status"]).strip().upper() if payload.get("status") is not None else None,
                        question_id,
                    ),
                )
                row = cur.fetchone()
            return row

        with open_connection() as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        payload.get("title"),
                        payload.get("template_text"),
                        payload.get("topic_code"),
                        payload.get("skill_code"),
                        payload.get("difficulty_level"),
                        payload.get("default_score"),
                        str(payload["generator_type"]).strip().upper()
                        if payload.get("generator_type") is not None
                        else None,
                        payload.get("generator_version"),
                        str(payload["status"]).strip().upper() if payload.get("status") is not None else None,
                        question_id,
                    ),
                )
                row = cur.fetchone()
            db_conn.commit()

        return row

    def question_has_published_reference(self, question_id: int) -> bool:
        query = """
        SELECT EXISTS (
            SELECT 1
            FROM assessment.exam_blueprint_rule_question AS qbrq
            INNER JOIN assessment.exam_blueprint_rule AS qbr
                ON qbr.blueprint_rule_id = qbrq.blueprint_rule_id
            INNER JOIN assessment.exam_blueprint_section AS qbs
                ON qbs.blueprint_section_id = qbr.blueprint_section_id
            INNER JOIN assessment.exam_blueprint AS qb
                ON qb.blueprint_id = qbs.blueprint_id
            INNER JOIN assessment.exam_version AS ev
                ON ev.exam_version_id = qb.exam_version_id
            WHERE qbrq.question_template_id = %s
              AND ev.status = 'PUBLISHED'
        ) AS has_published
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (question_id,))
                row = cur.fetchone()
        return bool(row and row["has_published"])

    def create_expected_answer(self, *, question_id: int, payload: dict, actor_user_id: int, conn=None) -> dict:
        query = """
        INSERT INTO assessment.reference_solution (
            question_template_id,
            solution_type,
            solution_payload,
            solution_payload_json,
            artifact_ref,
            solution_hash,
            status,
            created_by,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now(), now())
        RETURNING
            reference_solution_id,
            question_template_id,
            solution_type,
            status,
            created_by,
            created_at
        """

        solution_payload_json = payload.get("solution_payload_json")
        payload_json = Jsonb(solution_payload_json) if solution_payload_json is not None else None

        if conn is not None:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        question_id,
                        str(payload["solution_type"]).strip().upper(),
                        payload.get("solution_payload"),
                        payload_json,
                        payload.get("artifact_ref"),
                        payload.get("solution_hash"),
                        str(payload.get("status") or "DRAFT").strip().upper(),
                        actor_user_id,
                    ),
                )
                row = cur.fetchone()
        else:
            with open_connection() as db_conn:
                with db_conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        query,
                        (
                            question_id,
                            str(payload["solution_type"]).strip().upper(),
                            payload.get("solution_payload"),
                            payload_json,
                            payload.get("artifact_ref"),
                            payload.get("solution_hash"),
                            str(payload.get("status") or "DRAFT").strip().upper(),
                            actor_user_id,
                        ),
                    )
                    row = cur.fetchone()
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to create expected answer")
        return row

    def question_has_active_expected_answer(self, question_id: int, conn=None) -> bool:
        query = """
        SELECT EXISTS (
            SELECT 1
            FROM assessment.reference_solution
            WHERE question_template_id = %s
              AND status IN ('DRAFT', 'ACTIVE')
            LIMIT 1
        ) AS exists_flag
        """
        if conn is not None:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(question_id),))
                row = cur.fetchone()
            return bool(row and row.get("exists_flag"))

        with open_connection() as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(question_id),))
                row = cur.fetchone()
        return bool(row and row.get("exists_flag"))

    def create_question_grading_profile(self, *, question_id: int, payload: dict) -> dict:
        query = """
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
            metadata_json,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now())
        RETURNING
            question_grading_profile_id,
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
            created_at,
            updated_at
        """

        metadata_json = payload.get("metadata_json")
        metadata_payload = Jsonb(metadata_json) if metadata_json is not None else Jsonb({})

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        question_id,
                        payload.get("exam_version_id"),
                        str(payload["input_source"]).strip().upper(),
                        str(payload.get("answer_language") or "NONE").strip().upper(),
                        bool(payload.get("requires_capture", False)),
                        str(payload["required_capture_type"]).strip().upper()
                        if payload.get("required_capture_type") is not None
                        else None,
                        payload.get("capture_profile_id"),
                        int(payload["grading_engine_id"]),
                        str(payload["comparison_method"]).strip().upper(),
                        payload.get("timeout_seconds"),
                        payload.get("max_score"),
                        str(payload.get("status") or "ACTIVE").strip().upper(),
                        metadata_payload,
                    ),
                )
                row = cur.fetchone()
            conn.commit()

        if row is None:
            raise RuntimeError("Failed to create question grading profile")
        return row
