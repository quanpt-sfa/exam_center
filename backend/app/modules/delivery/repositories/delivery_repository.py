"""Repository layer for delivery runtime APIs."""

from __future__ import annotations

import json
from hashlib import md5
from hashlib import sha256
from datetime import datetime, timedelta, timezone

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.infrastructure.storage.answer_files import (
    allowed_mimes_for_extension,
    get_answer_file_max_bytes,
    normalized_allowed_extensions,
    normalized_allowed_mimes,
)
from app.infrastructure.database.connection import open_connection


class DeliveryRepository:
    """SQL-only data access for delivery APIs."""

    _ROOM_CLOSEABLE_ROOM_STATUSES = ("OPEN", "READY")
    _ROOM_CLOSE_SAFE_ASSIGNMENT_STATUSES = ("CHECKED_IN", "ABSENT", "COMPLETED", "RESCHEDULED", "CANCELLED", "VOIDED")
    _ROOM_CLOSE_ACTIVE_SESSION_STATUSES = ("READY_TO_START", "IN_PROGRESS", "PAUSED")
    _ROOM_CLOSE_PENDING_SUBMISSION_SESSION_STATUSES = (
        "IN_PROGRESS",
        "PAUSED",
        "INTERRUPTED",
        "ENDED",
        "EXPIRED",
        "SUBMITTED",
        "FORCE_CLOSED",
    )
    _ROOM_CLOSE_TERMINAL_SUBMISSION_STATUSES = ("SUBMITTED", "AUTO_SUBMITTED", "FORCE_SEALED", "EXPIRED_SEALED", "VOIDED")
    _TEXT_MANUAL_RANDOMIZATION_MODES = {"PARAMETERIZED", "HYBRID", "RANDOM_FROM_BANK"}
    _VARIANT_PARAMETER_FORBIDDEN_KEYS = {
        "answer_key",
        "answer_keys",
        "api_key",
        "bearer_token",
        "content_path",
        "expected_answer_text",
        "expected_answer_json",
        "expected_hash",
        "correct_answer",
        "correct_option",
        "correct_option_id",
        "correct_option_ids",
        "correct_options",
        "expected_answer",
        "expected_payload",
        "expected_payload_json",
        "generated_expected_answer",
        "hidden_test",
        "hidden_tests",
        "hidden_test_cases",
        "internal_storage_key",
        "internal_seed",
        "local_file_path",
        "local_path",
        "file_path",
        "database_dsn",
        "postgres_dsn",
        "random_seed",
        "rubric",
        "rubric_id",
        "rubric_json",
        "secret",
        "seed",
        "solution",
        "solution_type",
        "storage_ref",
        "storage_relative_path",
        "storage_uri",
        "stored_filename",
        "token",
    }

    @staticmethod
    def _rendered_question_hash(*, rendered_question_text: str, rendered_question_payload: dict) -> str:
        payload_text = json.dumps(rendered_question_payload, sort_keys=True, ensure_ascii=False)
        return md5(f"{rendered_question_text}|{payload_text}".encode("utf-8")).hexdigest()

    @staticmethod
    def _seed_hash(*, exam_session_id: int, exam_version_id: int) -> str:
        return sha256(f"mvq2|{int(exam_session_id)}|{int(exam_version_id)}".encode("utf-8")).hexdigest()

    @staticmethod
    def _coerce_positive_int(value: object | None, *, default: int) -> int:
        try:
            parsed = int(value) if value is not None else default
        except (TypeError, ValueError):
            return int(default)
        return parsed if parsed > 0 else int(default)

    @staticmethod
    def _option_label(option_order: int) -> str:
        label = ""
        current = int(option_order)
        while current > 0:
            current, remainder = divmod(current - 1, 26)
            label = chr(65 + remainder) + label
        return label or "A"

    @staticmethod
    def _string_list(value: object) -> list[str] | None:
        if not isinstance(value, list):
            return None
        items: list[str] = []
        for item in value:
            text = str(item or "").strip()
            if text:
                items.append(text)
        return items or None

    @staticmethod
    def _safe_upload_instructions(value: object) -> str | None:
        text = str(value or "").strip()
        if not text:
            return None
        return text[:1000]

    @staticmethod
    def _expected_answer_hash(*, expected_payload: str | None, expected_payload_json: dict | None) -> str | None:
        if isinstance(expected_payload_json, dict) and expected_payload_json:
            payload_text = json.dumps(expected_payload_json, sort_keys=True, ensure_ascii=False)
            return sha256(f"json|{payload_text}".encode("utf-8")).hexdigest()
        if expected_payload:
            return sha256(f"text|{expected_payload}".encode("utf-8")).hexdigest()
        return None

    @classmethod
    def _safe_variant_parameters(cls, value: object) -> object:
        if isinstance(value, dict):
            safe: dict[str, object] = {}
            for key, item in value.items():
                key_text = str(key)
                if key_text.lower() in cls._VARIANT_PARAMETER_FORBIDDEN_KEYS:
                    continue
                safe[key_text] = cls._safe_variant_parameters(item)
            return safe
        if isinstance(value, list):
            return [cls._safe_variant_parameters(item) for item in value]
        return value

    @classmethod
    def _normalize_text_variants(cls, metadata: dict) -> list[dict]:
        raw_variants = metadata.get("text_variants")
        if not isinstance(raw_variants, list):
            raw_variants = metadata.get("variant_pool")
        if not isinstance(raw_variants, list):
            return []

        normalized: list[dict] = []
        for index, raw_variant in enumerate(raw_variants, start=1):
            if isinstance(raw_variant, str):
                text = raw_variant.strip()
                if text:
                    normalized.append(
                        {
                            "variant_code": f"V{index}",
                            "rendered_question_text": text,
                            "variant_parameters_json": {"variant_index": index},
                        }
                    )
                continue

            if not isinstance(raw_variant, dict):
                continue

            text = str(
                raw_variant.get("rendered_question_text")
                or raw_variant.get("question_text")
                or raw_variant.get("template_text")
                or ""
            ).strip()
            if not text:
                continue

            parameters = raw_variant.get("variant_parameters_json")
            if not isinstance(parameters, dict):
                parameters = raw_variant.get("parameters") if isinstance(raw_variant.get("parameters"), dict) else {}

            normalized.append(
                {
                    "variant_code": str(raw_variant.get("variant_code") or f"V{index}").strip()[:100] or f"V{index}",
                    "rendered_question_text": text,
                    "variant_parameters_json": cls._safe_variant_parameters(parameters),
                    "allowed_extensions": cls._string_list(raw_variant.get("allowed_extensions")),
                    "allowed_mime_types": cls._string_list(raw_variant.get("allowed_mime_types")),
                    "max_file_size_bytes": raw_variant.get("max_file_size_bytes"),
                    "upload_instructions": cls._safe_upload_instructions(
                        raw_variant.get("safe_upload_instructions") or raw_variant.get("upload_instructions")
                    ),
                    "expected_answer_text": (
                        str(raw_variant.get("expected_answer_text") or "").strip() or None
                    ),
                    "expected_answer_json": (
                        cls._safe_variant_parameters(raw_variant.get("expected_answer_json"))
                        if isinstance(raw_variant.get("expected_answer_json"), dict)
                        else None
                    ),
                }
            )

        return normalized

    @classmethod
    def _generated_expected_answer_snapshot(
        cls,
        *,
        runtime_question_type: str,
        metadata: dict,
        selected_variant: dict | None,
    ) -> dict | None:
        if runtime_question_type not in {"SQL_QUERY", "SQL_DDL"}:
            return None

        expected_answer_json = None
        expected_answer_text = None
        source_label = "question_metadata"
        solution_type = None

        if isinstance(selected_variant, dict):
            if isinstance(selected_variant.get("expected_answer_json"), dict) and selected_variant.get("expected_answer_json"):
                expected_answer_json = dict(selected_variant["expected_answer_json"])
                source_label = "variant_expected_answer_json"
                solution_type = "SQL_RESULT"
            elif selected_variant.get("expected_answer_text"):
                expected_answer_text = str(selected_variant["expected_answer_text"])
                source_label = "variant_expected_answer_text"
                solution_type = "SQL_TEXT"

        if expected_answer_json is None and expected_answer_text is None:
            if isinstance(metadata.get("expected_answer_json"), dict) and metadata.get("expected_answer_json"):
                expected_answer_json = dict(metadata["expected_answer_json"])
                source_label = "question_metadata_expected_answer_json"
                solution_type = "SQL_RESULT"
            elif metadata.get("expected_answer_text"):
                expected_answer_text = str(metadata.get("expected_answer_text") or "").strip() or None
                source_label = "question_metadata_expected_answer_text"
                solution_type = "SQL_TEXT"

        if expected_answer_json is None and expected_answer_text is None:
            return None

        return {
            "answer_order": 1,
            "solution_type": solution_type or "SQL_RESULT",
            "expected_payload": expected_answer_text,
            "expected_payload_json": expected_answer_json,
            "expected_hash": cls._expected_answer_hash(
                expected_payload=expected_answer_text,
                expected_payload_json=expected_answer_json,
            ),
            "metadata_json": {
                "source": "delivery_prepare_runtime_sql_expected_snapshot",
                "snapshot_source": source_label,
                "variant_code": selected_variant.get("variant_code") if isinstance(selected_variant, dict) else None,
            },
        }

    @classmethod
    def _generated_file_upload_answer_ui_snapshot(
        cls,
        *,
        metadata: dict,
        input_source: object,
        selected_variant: dict | None,
    ) -> dict:
        variant = selected_variant if isinstance(selected_variant, dict) else {}
        allowed_extensions = variant.get("allowed_extensions")
        if allowed_extensions is None:
            allowed_extensions = metadata.get("allowed_extensions")
        normalized_extensions = sorted(normalized_allowed_extensions(allowed_extensions))

        allowed_mime_types = variant.get("allowed_mime_types")
        if allowed_mime_types is None:
            allowed_mime_types = metadata.get("allowed_mime_types")
        normalized_mime_types = normalized_allowed_mimes(allowed_mime_types)
        for extension in normalized_extensions:
            normalized_mime_types.update(allowed_mimes_for_extension(extension))

        max_file_size_bytes = get_answer_file_max_bytes()
        raw_max_bytes = variant.get("max_file_size_bytes")
        if raw_max_bytes is None:
            raw_max_bytes = metadata.get("max_file_size_bytes")
        try:
            candidate = int(raw_max_bytes) if raw_max_bytes is not None else None
            if candidate is not None and candidate > 0:
                max_file_size_bytes = candidate
        except (TypeError, ValueError):
            pass

        upload_instructions = cls._safe_upload_instructions(
            variant.get("upload_instructions")
            or metadata.get("safe_upload_instructions")
            or metadata.get("upload_instructions")
        )

        answer_ui = {
            "ui_mode": str(metadata.get("ui_mode") or metadata.get("render_component") or "FILE_UPLOAD"),
            "input_source": str(input_source or "SEALED_FILE_REF"),
            "required": bool(metadata.get("required", True)),
            "allowed_extensions": normalized_extensions,
            "allowed_mime_types": sorted(normalized_mime_types),
            "max_file_size_bytes": int(max_file_size_bytes),
        }
        if upload_instructions is not None:
            answer_ui["upload_instructions"] = upload_instructions
        return answer_ui

    @classmethod
    def _normalize_multiple_choice_options(cls, metadata: dict) -> list[dict]:
        raw_options = metadata.get("mcq_options")
        if not isinstance(raw_options, list):
            return []

        normalized: list[dict] = []
        for canonical_order, raw_option in enumerate(raw_options, start=1):
            rendered_option_text = ""
            rendered_option_payload_json: dict[str, object] = {}
            if isinstance(raw_option, dict):
                rendered_option_text = str(
                    raw_option.get("rendered_option_text")
                    or raw_option.get("text")
                    or raw_option.get("label")
                    or raw_option.get("value")
                    or ""
                ).strip()
                payload_json = raw_option.get("payload_json")
                if isinstance(payload_json, dict):
                    rendered_option_payload_json = cls._safe_variant_parameters(payload_json)
            else:
                rendered_option_text = str(raw_option or "").strip()

            if not rendered_option_text:
                continue

            normalized.append(
                {
                    "original_option_id": canonical_order,
                    "canonical_option_order": canonical_order,
                    "rendered_option_text": rendered_option_text,
                    "rendered_option_payload_json": rendered_option_payload_json,
                    "metadata_json": {"canonical_option_order": canonical_order},
                }
            )

        return normalized

    @classmethod
    def _materialize_multiple_choice_options(
        cls,
        *,
        metadata: dict,
        seed_hash: str,
        question_template_id: int,
        shuffle_options: bool,
    ) -> list[dict]:
        options = list(cls._normalize_multiple_choice_options(metadata))
        if shuffle_options and len(options) > 1:
            options = sorted(
                options,
                key=lambda option: (
                    sha256(
                        (
                            f"{seed_hash}|option|{int(question_template_id)}|"
                            f"{int(option['original_option_id'])}|{option['rendered_option_text']}"
                        ).encode("utf-8")
                    ).hexdigest(),
                    int(option["canonical_option_order"]),
                ),
            )

        materialized: list[dict] = []
        for option_order, option in enumerate(options, start=1):
            materialized.append(
                {
                    **option,
                    "option_order": option_order,
                    "option_label": cls._option_label(option_order),
                }
            )
        return materialized

    @classmethod
    def _prepare_strategy_label(
        cls,
        *,
        randomization_mode: str,
        shuffle_questions: bool,
        shuffle_options: bool,
        has_multiple_choice_questions: bool,
    ) -> str:
        if has_multiple_choice_questions and (bool(shuffle_questions) or bool(shuffle_options)):
            return "MULTIPLE_CHOICE_OPTION_SESSION_SEEDED"
        if str(randomization_mode or "").strip().upper() in cls._TEXT_MANUAL_RANDOMIZATION_MODES:
            return "TEXT_MANUAL_SESSION_SEEDED"
        return "FIXED_PROFILE_ORDER"

    @classmethod
    def _materialize_runtime_questions(
        cls,
        *,
        questions: list[dict],
        exam_session_id: int,
        exam_version_id: int,
        randomization_mode: str,
        shuffle_questions: bool = False,
        shuffle_options: bool = False,
    ) -> tuple[list[dict], str, str]:
        seed_hash = cls._seed_hash(exam_session_id=int(exam_session_id), exam_version_id=int(exam_version_id))
        normalized_mode = str(randomization_mode or "FIXED").strip().upper() or "FIXED"
        text_manual_order_randomization_enabled = normalized_mode in cls._TEXT_MANUAL_RANDOMIZATION_MODES

        materialized: list[dict] = []
        for index, question in enumerate(questions, start=1):
            metadata = question.get("metadata_json") if isinstance(question.get("metadata_json"), dict) else {}
            canonical_section_order = cls._coerce_positive_int(
                metadata.get("canonical_section_order") or metadata.get("section_no"),
                default=1,
            )
            canonical_question_order = cls._coerce_positive_int(
                metadata.get("canonical_question_order") or metadata.get("question_no"),
                default=index,
            )
            runtime_question_type = cls._runtime_question_type(str(question.get("question_type") or ""), metadata)
            question_order_randomization_enabled = (
                (runtime_question_type in {"TEXT", "MANUAL"} and text_manual_order_randomization_enabled)
                or (runtime_question_type == "MULTIPLE_CHOICE" and bool(shuffle_questions))
            )
            rendered_question_text = str(question.get("template_text") or "")
            variant_code = str(metadata.get("variant_code")).strip()[:100] if metadata.get("variant_code") is not None else None
            variant_parameters_json = (
                cls._safe_variant_parameters(metadata.get("variant_parameters"))
                if isinstance(metadata.get("variant_parameters"), dict)
                else {}
            )
            generated_options = (
                cls._materialize_multiple_choice_options(
                    metadata=metadata,
                    seed_hash=seed_hash,
                    question_template_id=int(question["question_template_id"]),
                    shuffle_options=bool(shuffle_options),
                )
                if runtime_question_type == "MULTIPLE_CHOICE"
                else []
            )
            selected_variant: dict | None = None

            text_variants = cls._normalize_text_variants(metadata)
            if runtime_question_type in {"TEXT", "MANUAL", "SQL_QUERY", "SQL_DDL", "FILE_UPLOAD"} and text_variants:
                variant_index = int(
                    sha256(
                        f"{seed_hash}|variant|{int(question['question_template_id'])}|{canonical_question_order}".encode("utf-8")
                    ).hexdigest(),
                    16,
                ) % len(text_variants)
                selected_variant = text_variants[variant_index]
                variant_code = selected_variant.get("variant_code") or variant_code
                rendered_question_text = str(selected_variant.get("rendered_question_text") or rendered_question_text)
                variant_parameters_json = {
                    **variant_parameters_json,
                    **(selected_variant.get("variant_parameters_json") or {}),
                    "variant_index": int(variant_index) + 1,
                    "variant_count": len(text_variants),
                }

            generated_expected_answer_snapshot = cls._generated_expected_answer_snapshot(
                runtime_question_type=runtime_question_type,
                metadata=metadata,
                selected_variant=selected_variant,
            )

            payload_answer_ui = {
                "ui_mode": metadata.get("ui_mode") or metadata.get("render_component"),
                "input_source": question.get("input_source"),
                "required": bool(metadata.get("required", True)),
                "option_count": len(generated_options),
            }
            if runtime_question_type == "FILE_UPLOAD":
                payload_answer_ui = cls._generated_file_upload_answer_ui_snapshot(
                    metadata=metadata,
                    input_source=question.get("input_source"),
                    selected_variant=selected_variant,
                )

            materialized.append(
                {
                    "question_grading_profile_id": int(question["question_grading_profile_id"]),
                    "question_template_id": int(question["question_template_id"]),
                    "original_question_id": int(question["question_template_id"]),
                    "source_exam_question_id": None,
                    "canonical_section_order": canonical_section_order,
                    "canonical_question_order": canonical_question_order,
                    "question_code": str(question.get("template_code") or f"Q{index}")[:100],
                    "question_type": runtime_question_type,
                    "variant_code": variant_code,
                    "variant_parameters_json": variant_parameters_json,
                    "rendered_question_text": rendered_question_text,
                    "score": question.get("max_score") if question.get("max_score") is not None else question.get("default_score"),
                    "metadata_json": {
                        "source": "admin_prepare_runtime",
                        "question_no": canonical_question_order,
                        "authoring_question_type": metadata.get("authoring_question_type"),
                        "question_title": question.get("title"),
                        "variant_selection_mode": "SESSION_DETERMINISTIC" if text_variants else "FIXED",
                        "shuffle_questions": bool(runtime_question_type == "MULTIPLE_CHOICE" and shuffle_questions),
                        "shuffle_options": bool(runtime_question_type == "MULTIPLE_CHOICE" and shuffle_options),
                    },
                    "payload_data": {
                        "answer_ui": payload_answer_ui,
                    },
                    "generated_options": generated_options,
                    "generated_expected_answer_snapshot": generated_expected_answer_snapshot,
                    "display_order_sort_key": (
                        sha256(
                            f"{seed_hash}|order|{int(question['question_template_id'])}|{canonical_question_order}".encode("utf-8")
                        ).hexdigest()
                        if question_order_randomization_enabled
                        else f"canonical:{canonical_section_order:06d}:{canonical_question_order:06d}"
                    ),
                    "eligible_for_randomization": question_order_randomization_enabled,
                }
            )

        ordered = list(materialized)
        randomizable_positions = [index for index, item in enumerate(ordered) if item["eligible_for_randomization"]]
        if randomizable_positions:
            shuffled_items = sorted(
                (ordered[index] for index in randomizable_positions),
                key=lambda item: (item["display_order_sort_key"], item["canonical_section_order"], item["canonical_question_order"]),
            )
            for position, shuffled in zip(randomizable_positions, shuffled_items, strict=False):
                ordered[position] = shuffled

        for display_order, item in enumerate(ordered, start=1):
            item["question_order"] = display_order
            item["display_question_order"] = display_order

        prepare_strategy = cls._prepare_strategy_label(
            randomization_mode=normalized_mode,
            shuffle_questions=shuffle_questions,
            shuffle_options=shuffle_options,
            has_multiple_choice_questions=any(item["question_type"] == "MULTIPLE_CHOICE" for item in ordered),
        )
        return ordered, seed_hash, prepare_strategy

    _INCIDENT_SELECT_COLUMNS = """
        incident_id,
        exam_sitting_id,
        exam_sitting_room_id,
        exam_assignment_id,
        exam_session_id,
        station_id,
        device_id,
        incident_type,
        incident_status,
        reported_by,
        reported_at,
        resolved_by,
        resolved_at,
        description,
        metadata_json,
        updated_by,
        updated_at,
        resolution_note
    """

    def list_setup_sittings(self) -> list[dict]:
        query = """
        SELECT
            sit.exam_sitting_id,
            sit.exam_version_id,
            sit.sitting_code,
            sit.sitting_name,
            sit.scheduled_start_at,
            sit.scheduled_end_at,
            sit.timezone,
            sit.sitting_status,
            sit.created_by,
            sit.created_at,
            sit.updated_at,
            ev.version_no,
            ev.version_label,
            ev.status AS exam_version_status,
            exam.exam_id,
            exam.exam_code,
            exam.exam_name
        FROM delivery.exam_sitting sit
        JOIN assessment.exam_version ev
          ON ev.exam_version_id = sit.exam_version_id
        JOIN assessment.exam exam
          ON exam.exam_id = ev.exam_id
        ORDER BY sit.scheduled_start_at DESC, sit.exam_sitting_id DESC
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query)
                return cur.fetchall()

    def get_exam_version_detail(self, exam_version_id: int) -> dict | None:
        query = """
        SELECT
            ev.exam_version_id,
            ev.exam_id,
            ev.version_no,
            ev.version_label,
            ev.status AS exam_version_status,
            exam.exam_code,
            exam.exam_name
        FROM assessment.exam_version ev
        JOIN assessment.exam exam
          ON exam.exam_id = ev.exam_id
        WHERE ev.exam_version_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_version_id),))
                return cur.fetchone()

    def create_setup_sitting(
        self,
        *,
        sitting_code: str,
        sitting_name: str,
        exam_version_id: int,
        scheduled_start_at: datetime,
        scheduled_end_at: datetime,
        sitting_status: str,
        created_by: int,
    ) -> dict:
        query = """
        INSERT INTO delivery.exam_sitting (
            exam_version_id,
            sitting_code,
            sitting_name,
            scheduled_start_at,
            scheduled_end_at,
            sitting_status,
            created_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING
            exam_sitting_id,
            exam_version_id,
            sitting_code,
            sitting_name,
            scheduled_start_at,
            scheduled_end_at,
            timezone,
            sitting_status,
            created_by,
            created_at,
            updated_at
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(exam_version_id),
                        str(sitting_code).strip(),
                        str(sitting_name).strip(),
                        scheduled_start_at,
                        scheduled_end_at,
                        str(sitting_status).strip().upper(),
                        int(created_by),
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to create delivery.exam_sitting")
        return row

    def get_setup_sitting_by_id(self, exam_sitting_id: int) -> dict | None:
        query = """
        SELECT
            sit.exam_sitting_id,
            sit.exam_version_id,
            sit.sitting_code,
            sit.sitting_name,
            sit.scheduled_start_at,
            sit.scheduled_end_at,
            sit.timezone,
            sit.sitting_status,
            sit.created_by,
            sit.created_at,
            sit.updated_at,
            ev.version_no,
            ev.version_label,
            ev.status AS exam_version_status,
            exam.exam_id,
            exam.exam_code,
            exam.exam_name
        FROM delivery.exam_sitting sit
        JOIN assessment.exam_version ev
          ON ev.exam_version_id = sit.exam_version_id
        JOIN assessment.exam exam
          ON exam.exam_id = ev.exam_id
        WHERE sit.exam_sitting_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_id),))
                return cur.fetchone()

    def count_active_sessions_for_sitting(self, exam_sitting_id: int) -> int:
        query = """
        SELECT count(*) AS active_count
        FROM delivery.exam_session sess
        JOIN delivery.exam_assignment ea
          ON ea.exam_assignment_id = sess.exam_assignment_id
        WHERE ea.exam_sitting_id = %s
          AND sess.session_status IN (
              'CREATED',
              'WAITING_FOR_CHECKIN',
              'READY_TO_START',
              'IN_PROGRESS',
              'PAUSED',
              'INTERRUPTED'
          )
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_id),))
                row = cur.fetchone()
        return int(row["active_count"] if row else 0)

    def update_setup_sitting(self, *, exam_sitting_id: int, payload: dict) -> dict | None:
        allowed = {
            "exam_version_id": "exam_version_id = %s",
            "sitting_name": "sitting_name = %s",
            "scheduled_start_at": "scheduled_start_at = %s",
            "scheduled_end_at": "scheduled_end_at = %s",
            "sitting_status": "sitting_status = %s",
            "timezone": "timezone = %s",
        }
        updates: list[str] = []
        values: list[object] = []

        for key, clause in allowed.items():
            if key not in payload:
                continue
            value = payload[key]
            if key in {"sitting_name", "sitting_status"} and value is not None:
                text = str(value).strip()
                value = text.upper() if key == "sitting_status" else text
            if key == "timezone" and value is not None:
                value = str(value).strip()
            updates.append(clause)
            values.append(value)

        if not updates:
            return self.get_setup_sitting_by_id(int(exam_sitting_id))

        values.append(int(exam_sitting_id))
        query = f"""
        UPDATE delivery.exam_sitting
        SET
            {", ".join(updates)},
            updated_at = now()
        WHERE exam_sitting_id = %s
        RETURNING
            exam_sitting_id,
            exam_version_id,
            sitting_code,
            sitting_name,
            scheduled_start_at,
            scheduled_end_at,
            timezone,
            sitting_status,
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

    def list_exam_sessions_for_student(self, student_id: int) -> list[dict]:
        query = """
        SELECT
            es.exam_session_id,
            es.exam_assignment_id,
            ea.exam_sitting_id,
            ea.student_id,
            ea.assignment_status,
            es.session_code,
            es.session_no,
            es.session_status,
            es.started_at,
            es.deadline_at,
            es.ended_at,
            es.time_limit_seconds,
            es.extra_time_seconds,
            es.last_seen_at,
            es.last_activity_at,
            sit.sitting_name,
            sit.scheduled_start_at,
            sit.scheduled_end_at,
            exam.exam_code,
            exam.exam_name,
            course.course_code,
            course.course_name,
            room.room_code,
            room.room_name,
            station.station_code,
            station.seat_no,
            sub.exam_submission_id,
            sub.submission_status,
            sub.submitted_at,
            sub.sealed_at
        FROM delivery.exam_session es
        JOIN delivery.exam_assignment ea
            ON ea.exam_assignment_id = es.exam_assignment_id
        JOIN delivery.exam_sitting sit
            ON sit.exam_sitting_id = ea.exam_sitting_id
        JOIN assessment.exam_version ev
            ON ev.exam_version_id = sit.exam_version_id
        JOIN assessment.exam exam
            ON exam.exam_id = ev.exam_id
        LEFT JOIN academic.class_section section
            ON section.class_section_id = exam.class_section_id
        LEFT JOIN academic.course_offering offering
            ON offering.course_offering_id = section.course_offering_id
        LEFT JOIN academic.course course
            ON course.course_id = offering.course_id
        LEFT JOIN delivery.exam_station_assignment station_assignment
            ON station_assignment.exam_assignment_id = ea.exam_assignment_id
        LEFT JOIN delivery.exam_sitting_room sitting_room
            ON sitting_room.exam_sitting_room_id = station_assignment.exam_sitting_room_id
        LEFT JOIN facility.room room
            ON room.room_id = sitting_room.room_id
        LEFT JOIN facility.lab_station station
            ON station.station_id = station_assignment.station_id
        LEFT JOIN submission.exam_submission sub
            ON sub.exam_session_id = es.exam_session_id
        WHERE ea.student_id = %s
          AND ea.assignment_status NOT IN ('CANCELLED', 'VOIDED')
          AND es.session_status <> 'VOIDED'
          AND sit.sitting_status IN ('OPEN', 'IN_PROGRESS')
        ORDER BY sit.scheduled_start_at DESC, es.exam_session_id DESC
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (student_id,))
                return cur.fetchall()

    @staticmethod
    def _runtime_question_type(question_type: str, metadata: dict | None) -> str:
        authoring_type = str((metadata or {}).get("authoring_question_type") or question_type or "").strip().upper()
        mapping = {
            "TEXTBOX_SQL": "SQL_QUERY",
            "SQL_QUERY": "SQL_QUERY",
            "SQL_DDL": "SQL_DDL",
            "SQL_PROCEDURE": "SQL_DDL",
            "MISA_TRANSACTION": "MISA_TASK",
            "MISA_REPORT": "MISA_TASK",
            "AMIS_REPORT": "AMIS_TASK",
            "TEXTAREA": "TEXT",
            "MANUAL": "MANUAL",
            "MANUAL_TEXT": "MANUAL",
            "MCQ_SINGLE": "MULTIPLE_CHOICE",
            "FILE_UPLOAD": "FILE_UPLOAD",
        }
        return mapping.get(authoring_type, "TEXT")

    def prepare_exam_sitting_runtime(self, *, exam_sitting_id: int, actor_user_id: int | None) -> dict:
        sitting_query = """
        SELECT
            sit.exam_sitting_id,
            sit.sitting_code,
            sit.sitting_status,
            sit.exam_version_id,
            ev.duration_seconds,
            ev.randomization_mode,
            ev.shuffle_questions,
            ev.shuffle_options
        FROM delivery.exam_sitting sit
        JOIN assessment.exam_version ev
          ON ev.exam_version_id = sit.exam_version_id
        WHERE sit.exam_sitting_id = %s
        LIMIT 1
        """
        assignment_query = """
        SELECT
            ea.exam_assignment_id,
            ea.student_id
        FROM delivery.exam_assignment ea
        WHERE ea.exam_sitting_id = %s
          AND ea.assignment_status IN ('ASSIGNED', 'CHECKED_IN')
        ORDER BY ea.exam_assignment_id
        """
        question_query = """
        SELECT
            qgp.question_grading_profile_id,
            qgp.question_template_id,
            qgp.exam_version_id,
            qgp.input_source,
            qgp.max_score,
            qgp.metadata_json,
            qt.template_code,
            qt.question_type,
            qt.title,
            qt.template_text,
            qt.default_score
        FROM assessment.question_grading_profile qgp
        JOIN assessment.question_template qt
          ON qt.question_template_id = qgp.question_template_id
        WHERE qgp.exam_version_id = %s
          AND qgp.status IN ('ACTIVE', 'DRAFT')
          AND qt.status IN ('ACTIVE', 'DRAFT')
        ORDER BY
          NULLIF(qgp.metadata_json->>'question_no', '')::int NULLS LAST,
          qgp.question_template_id
        """
        insert_session_query = """
        INSERT INTO delivery.exam_session (
            exam_assignment_id,
            session_code,
            session_no,
            session_status,
            time_limit_seconds,
            created_by
        )
        VALUES (%s, %s, 1, 'READY_TO_START', %s, %s)
        ON CONFLICT (exam_assignment_id, session_no) DO UPDATE SET
            updated_at = now()
        RETURNING exam_session_id, (xmax = 0) AS inserted
        """
        create_instance_query = """
        INSERT INTO delivery.generated_exam_instance (
            exam_session_id,
            exam_version_id,
            generation_mode,
            generation_status,
            generator_name,
            generator_version,
            generation_seed_hash,
            generated_at,
            generated_by,
            metadata_json
        )
        VALUES (%s, %s, %s, 'GENERATED', 'delivery_prepare_runtime', 'mvp', %s, now(), %s, %s)
        ON CONFLICT (exam_session_id) DO UPDATE SET
            updated_at = now()
        RETURNING generated_exam_instance_id, (xmax = 0) AS inserted
        """
        count_questions_query = """
        SELECT count(*)::bigint AS total
        FROM delivery.generated_exam_question
        WHERE generated_exam_instance_id = %s
        """
        insert_question_query = """
        INSERT INTO delivery.generated_exam_question (
            generated_exam_instance_id,
            question_template_id,
            original_question_id,
            source_exam_question_id,
            blueprint_rule_id,
            question_order,
            canonical_section_order,
            canonical_question_order,
            display_question_order,
            question_code,
            question_type,
            variant_code,
            variant_parameters_json,
            rendered_question_text,
            rendered_question_payload_json,
            rendered_question_hash,
            score,
            metadata_json,
            question_grading_profile_id
        )
        VALUES (%s, %s, %s, %s, NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (generated_exam_instance_id, question_order) DO NOTHING
        RETURNING generated_exam_question_id
        """
        insert_option_query = """
        INSERT INTO delivery.generated_exam_option (
            generated_exam_question_id,
            original_option_id,
            option_order,
            option_label,
            rendered_option_text,
            rendered_option_payload_json,
            metadata_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (generated_exam_question_id, option_order) DO NOTHING
        RETURNING generated_exam_option_id
        """
        insert_expected_answer_query = """
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
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (generated_exam_question_id, answer_order) DO NOTHING
        RETURNING generated_expected_answer_id
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sitting_query, (int(exam_sitting_id),))
                sitting = cur.fetchone()
                if sitting is None:
                    return {"prepared": False, "reason": "SITTING_NOT_FOUND"}

                cur.execute(assignment_query, (int(exam_sitting_id),))
                assignments = cur.fetchall()

                cur.execute(question_query, (int(sitting["exam_version_id"]),))
                questions = cur.fetchall()

                if not assignments or not questions:
                    return {
                        "prepared": False,
                        "exam_sitting_id": int(exam_sitting_id),
                        "exam_version_id": int(sitting["exam_version_id"]),
                        "prepare_strategy": self._prepare_strategy_label(
                            randomization_mode=str(sitting.get("randomization_mode") or "FIXED"),
                            shuffle_questions=bool(sitting.get("shuffle_questions")),
                            shuffle_options=bool(sitting.get("shuffle_options")),
                            has_multiple_choice_questions=any(
                                self._runtime_question_type(
                                    str(question.get("question_type") or ""),
                                    question.get("metadata_json") if isinstance(question.get("metadata_json"), dict) else {},
                                )
                                == "MULTIPLE_CHOICE"
                                for question in questions
                            ),
                        ),
                        "assignment_count": len(assignments),
                        "question_count": len(questions),
                        "created_session_count": 0,
                        "reused_session_count": 0,
                        "created_instance_count": 0,
                        "reused_instance_count": 0,
                        "created_generated_question_count": 0,
                    }

                created_sessions = 0
                reused_sessions = 0
                created_instances = 0
                reused_instances = 0
                created_questions = 0

                for assignment in assignments:
                    session_code = f"S{int(exam_sitting_id)}-A{int(assignment['exam_assignment_id'])}-1"
                    cur.execute(
                        insert_session_query,
                        (
                            int(assignment["exam_assignment_id"]),
                            session_code,
                            int(sitting["duration_seconds"]),
                            int(actor_user_id) if actor_user_id is not None else None,
                        ),
                    )
                    session_row = cur.fetchone()
                    if session_row is None:
                        continue
                    session_id = int(session_row["exam_session_id"])
                    if bool(session_row.get("inserted")):
                        created_sessions += 1
                    else:
                        reused_sessions += 1

                    materialized_questions, seed_hash, prepare_strategy = self._materialize_runtime_questions(
                        questions=list(questions),
                        exam_session_id=session_id,
                        exam_version_id=int(sitting["exam_version_id"]),
                        randomization_mode=str(sitting.get("randomization_mode") or "FIXED"),
                        shuffle_questions=bool(sitting.get("shuffle_questions")),
                        shuffle_options=bool(sitting.get("shuffle_options")),
                    )

                    instance_metadata = Jsonb(
                        {
                            "source": "admin_prepare_runtime",
                            "exam_sitting_id": int(exam_sitting_id),
                            "exam_version_id": int(sitting["exam_version_id"]),
                            "prepare_strategy": prepare_strategy,
                        }
                    )
                    cur.execute(
                        create_instance_query,
                        (
                            session_id,
                            int(sitting["exam_version_id"]),
                            prepare_strategy,
                            seed_hash,
                            int(actor_user_id) if actor_user_id is not None else None,
                            instance_metadata,
                        ),
                    )
                    instance_row = cur.fetchone()
                    if instance_row is None:
                        continue
                    generated_exam_instance_id = int(instance_row["generated_exam_instance_id"])
                    if bool(instance_row.get("inserted")):
                        created_instances += 1
                    else:
                        reused_instances += 1

                    cur.execute(count_questions_query, (generated_exam_instance_id,))
                    count_row = cur.fetchone()
                    if int(count_row["total"] if count_row else 0) > 0:
                        continue

                    for question in materialized_questions:
                        payload_data = question["payload_data"]
                        payload_json = Jsonb(payload_data)
                        rendered_text = str(question["rendered_question_text"])
                        question_metadata = Jsonb(question["metadata_json"])
                        cur.execute(
                            insert_question_query,
                            (
                                generated_exam_instance_id,
                                int(question["question_template_id"]),
                                int(question["original_question_id"]),
                                question["source_exam_question_id"],
                                int(question["question_order"]),
                                int(question["canonical_section_order"]),
                                int(question["canonical_question_order"]),
                                int(question["display_question_order"]),
                                str(question["question_code"]),
                                str(question["question_type"]),
                                question.get("variant_code"),
                                Jsonb(question.get("variant_parameters_json") or {}),
                                rendered_text,
                                payload_json,
                                self._rendered_question_hash(
                                    rendered_question_text=rendered_text,
                                    rendered_question_payload=payload_data,
                                ),
                                question.get("score"),
                                question_metadata,
                                int(question["question_grading_profile_id"]),
                            ),
                        )
                        inserted_question_row = cur.fetchone()
                        if inserted_question_row is not None:
                            created_questions += 1
                            generated_exam_question_id = int(inserted_question_row["generated_exam_question_id"])
                            for option in question.get("generated_options") or []:
                                cur.execute(
                                    insert_option_query,
                                    (
                                        generated_exam_question_id,
                                        int(option["original_option_id"]),
                                        int(option["option_order"]),
                                        str(option["option_label"]),
                                        str(option["rendered_option_text"]),
                                        Jsonb(option.get("rendered_option_payload_json") or {}),
                                        Jsonb(option.get("metadata_json") or {}),
                                    ),
                                )
                                cur.fetchone()

                            expected_snapshot = question.get("generated_expected_answer_snapshot")
                            if isinstance(expected_snapshot, dict):
                                expected_metadata = dict(expected_snapshot.get("metadata_json") or {})
                                expected_metadata.update(
                                    {
                                        "question_template_id": int(question["question_template_id"]),
                                        "question_type": str(question["question_type"]),
                                        "variant_code": question.get("variant_code"),
                                        "variant_parameters_json": question.get("variant_parameters_json") or {},
                                    }
                                )
                                cur.execute(
                                    insert_expected_answer_query,
                                    (
                                        generated_exam_question_id,
                                        int(expected_snapshot.get("answer_order") or 1),
                                        str(expected_snapshot.get("solution_type") or "SQL_RESULT"),
                                        expected_snapshot.get("expected_payload"),
                                        Jsonb(expected_snapshot.get("expected_payload_json"))
                                        if isinstance(expected_snapshot.get("expected_payload_json"), dict)
                                        else None,
                                        expected_snapshot.get("expected_hash"),
                                        int(actor_user_id) if actor_user_id is not None else None,
                                        Jsonb(expected_metadata),
                                    ),
                                )
                                cur.fetchone()

            conn.commit()

        return {
            "prepared": bool(assignments and questions),
            "exam_sitting_id": int(exam_sitting_id),
            "exam_version_id": int(sitting["exam_version_id"]),
            "prepare_strategy": self._prepare_strategy_label(
                randomization_mode=str(sitting.get("randomization_mode") or "FIXED"),
                shuffle_questions=bool(sitting.get("shuffle_questions")),
                shuffle_options=bool(sitting.get("shuffle_options")),
                has_multiple_choice_questions=any(
                    self._runtime_question_type(
                        str(question.get("question_type") or ""),
                        question.get("metadata_json") if isinstance(question.get("metadata_json"), dict) else {},
                    )
                    == "MULTIPLE_CHOICE"
                    for question in questions
                ),
            ),
            "assignment_count": len(assignments),
            "question_count": len(questions),
            "created_session_count": created_sessions,
            "reused_session_count": reused_sessions,
            "created_instance_count": created_instances,
            "reused_instance_count": reused_instances,
            "created_generated_question_count": created_questions,
        }

    def get_session_by_id(self, session_id: int) -> dict | None:
        query = """
        SELECT
            es.exam_session_id,
            es.exam_assignment_id,
            ea.exam_sitting_id,
            ea.student_id,
            es.session_code,
            es.session_no,
            es.session_status,
            es.started_at,
            es.deadline_at,
            es.ended_at,
            es.time_limit_seconds,
            es.extra_time_seconds,
            es.last_seen_at,
            es.last_activity_at,
            station_assignment.station_assignment_id,
            station_assignment.exam_sitting_room_id,
            station_assignment.assigned_station_id,
            station_assignment.planned_device_id,
            station_assignment.station_assignment_status,
            sitting_room.room_id AS assigned_room_id,
            sitting_room.room_status,
            sitting_room.closed_at,
            sitting_room.closed_by,
            sitting_room.close_reason,
            sitting_room.close_note,
            sitting_room.close_summary_json,
            gei.generated_exam_instance_id,
            gei.generation_status
        FROM delivery.exam_session es
        JOIN delivery.exam_assignment ea
            ON ea.exam_assignment_id = es.exam_assignment_id
        LEFT JOIN LATERAL (
            SELECT
                esa.station_assignment_id,
                esa.exam_sitting_room_id,
                esa.station_id AS assigned_station_id,
                esa.planned_device_id,
                esa.status AS station_assignment_status
            FROM delivery.exam_station_assignment esa
            WHERE esa.exam_assignment_id = es.exam_assignment_id
            ORDER BY esa.station_assignment_id DESC
            LIMIT 1
        ) station_assignment ON TRUE
        LEFT JOIN delivery.exam_sitting_room sitting_room
            ON sitting_room.exam_sitting_room_id = station_assignment.exam_sitting_room_id
        LEFT JOIN delivery.generated_exam_instance gei
            ON gei.exam_session_id = es.exam_session_id
        WHERE es.exam_session_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (session_id,))
                return cur.fetchone()

    def get_session_runtime_delivery_profile_summary(self, session_id: int) -> dict | None:
        query = """
        SELECT
            sit.exam_version_id,
            profile.exam_version_delivery_profile_id,
            profile.delivery_mode,
            profile.work_mode,
            profile.primary_answer_source,
            profile.requires_capture,
            profile.capture_timing,
            profile.form_autosave_enabled,
            profile.database_work_mode,
            profile.status AS delivery_profile_status
        FROM delivery.exam_session sess
        JOIN delivery.exam_assignment ea
          ON ea.exam_assignment_id = sess.exam_assignment_id
        JOIN delivery.exam_sitting sit
          ON sit.exam_sitting_id = ea.exam_sitting_id
        LEFT JOIN assessment.exam_version_delivery_profile profile
          ON profile.exam_version_id = sit.exam_version_id
        WHERE sess.exam_session_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(session_id),))
                return cur.fetchone()

    def list_answer_state_for_submission(self, submission_id: int) -> list[dict]:
        query = """
        SELECT
            generated_exam_question_id,
            answer_type,
            answer_text,
            answer_payload_json,
            server_version,
            last_saved_at
        FROM submission.answer_state
        WHERE exam_submission_id = %s
        ORDER BY generated_exam_question_id
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(submission_id),))
                return cur.fetchall()

    def get_session_room_status(self, *, session_id: int) -> dict | None:
        row = self.get_session_by_id(int(session_id))
        if row is None:
            return None
        return {
            "exam_session_id": int(row["exam_session_id"]),
            "exam_sitting_room_id": int(row["exam_sitting_room_id"]) if row.get("exam_sitting_room_id") is not None else None,
            "session_status": row.get("session_status"),
            "room_status": row.get("room_status"),
            "closed_at": row.get("closed_at"),
            "closed_by": row.get("closed_by"),
        }

    def _get_session_room_state_with_cursor(self, *, cur, session_id: int) -> dict | None:
        query = """
        SELECT
            es.exam_session_id,
            es.exam_assignment_id,
            ea.exam_sitting_id,
            ea.student_id,
            es.session_status,
            es.started_at,
            es.deadline_at,
            es.ended_at,
            es.time_limit_seconds,
            es.extra_time_seconds,
            es.last_seen_at,
            es.last_activity_at,
            station_assignment.exam_sitting_room_id,
            sitting_room.room_status,
            sitting_room.closed_at,
            sitting_room.closed_by
        FROM delivery.exam_session es
        JOIN delivery.exam_assignment ea
            ON ea.exam_assignment_id = es.exam_assignment_id
        LEFT JOIN LATERAL (
            SELECT
                esa.exam_sitting_room_id
            FROM delivery.exam_station_assignment esa
            WHERE esa.exam_assignment_id = es.exam_assignment_id
            ORDER BY esa.station_assignment_id DESC
            LIMIT 1
        ) station_assignment ON TRUE
        LEFT JOIN delivery.exam_sitting_room sitting_room
            ON sitting_room.exam_sitting_room_id = station_assignment.exam_sitting_room_id
        WHERE es.exam_session_id = %s
        LIMIT 1
        """
        cur.execute(query, (int(session_id),))
        return cur.fetchone()

    def _lock_room_row_with_cursor(self, *, cur, exam_sitting_room_id: int, lock_clause: str = "FOR UPDATE") -> dict | None:
        normalized_lock_clause = str(lock_clause).strip().upper()
        if normalized_lock_clause not in {"FOR UPDATE", "FOR SHARE"}:
            raise ValueError("Unsupported room lock clause")
        query = f"""
        SELECT
            exam_sitting_room_id,
            room_status,
            closed_at,
            closed_by
        FROM delivery.exam_sitting_room
        WHERE exam_sitting_room_id = %s
        {normalized_lock_clause}
        """
        cur.execute(query, (int(exam_sitting_room_id),))
        return cur.fetchone()

    def _get_locked_session_room_state_with_cursor(self, *, cur, session_id: int, lock_clause: str) -> dict | None:
        row = self._get_session_room_state_with_cursor(cur=cur, session_id=int(session_id))
        if row is None:
            return None
        room_id = row.get("exam_sitting_room_id")
        if room_id is None:
            return row
        locked_room = self._lock_room_row_with_cursor(
            cur=cur,
            exam_sitting_room_id=int(room_id),
            lock_clause=lock_clause,
        )
        if locked_room is not None:
            row["room_status"] = locked_room.get("room_status")
            row["closed_at"] = locked_room.get("closed_at")
            row["closed_by"] = locked_room.get("closed_by")
        return row

    def ensure_file_upload_placeholder_question_for_session(
        self,
        *,
        session_id: int,
        actor_user_id: int | None,
    ) -> dict:
        """Ensure one generated FILE_UPLOAD question exists for placeholder-driven file-upload exams.

        This fallback is used only when:
        - exam version has an ACTIVE question_grading_profile with input_source SEALED_FILE_REF
          and metadata_json.placeholder_question=true, and
        - generated exam instance has zero generated questions.
        """

        session_query = """
        SELECT
            es.exam_session_id,
            sit.exam_version_id,
            gei.generated_exam_instance_id
        FROM delivery.exam_session es
        JOIN delivery.exam_assignment ea
          ON ea.exam_assignment_id = es.exam_assignment_id
        JOIN delivery.exam_sitting sit
          ON sit.exam_sitting_id = ea.exam_sitting_id
        LEFT JOIN delivery.generated_exam_instance gei
          ON gei.exam_session_id = es.exam_session_id
        WHERE es.exam_session_id = %s
        LIMIT 1
        """
        placeholder_query = """
        SELECT
            qgp.question_grading_profile_id,
            qgp.question_template_id,
            qgp.metadata_json,
            qgp.max_score,
            qt.template_code,
            qt.question_type,
            qt.template_text,
            qt.default_score
        FROM assessment.question_grading_profile qgp
        JOIN assessment.question_template qt
          ON qt.question_template_id = qgp.question_template_id
        WHERE qgp.exam_version_id = %s
          AND qgp.status = 'ACTIVE'
          AND upper(qgp.input_source) = 'SEALED_FILE_REF'
          AND lower(coalesce(qgp.metadata_json->>'placeholder_question', 'false')) IN ('true', '1', 'yes')
        ORDER BY qgp.question_grading_profile_id DESC
        LIMIT 1
        """
        create_instance_query = """
        INSERT INTO delivery.generated_exam_instance (
            exam_session_id,
            exam_version_id,
            generation_mode,
            generation_status,
            generator_name,
            generator_version,
            generated_at,
            generated_by,
            metadata_json
        )
        VALUES (%s, %s, 'FIXED', 'GENERATED', 'delivery_placeholder_seed', 'mvp', now(), %s, %s)
        ON CONFLICT (exam_session_id)
        DO UPDATE SET
            updated_at = now()
        RETURNING generated_exam_instance_id
        """
        count_questions_query = """
        SELECT count(*)::bigint AS total
        FROM delivery.generated_exam_question
        WHERE generated_exam_instance_id = %s
        """
        insert_question_query = """
        INSERT INTO delivery.generated_exam_question (
            generated_exam_instance_id,
            question_template_id,
            original_question_id,
            source_exam_question_id,
            blueprint_rule_id,
            question_order,
            canonical_section_order,
            canonical_question_order,
            display_question_order,
            question_code,
            question_type,
            variant_code,
            variant_parameters_json,
            rendered_question_text,
            rendered_question_payload_json,
            rendered_question_hash,
            score,
            metadata_json,
            question_grading_profile_id
        )
        VALUES (%s, %s, %s, %s, NULL, 1, 1, 1, 1, %s, 'FILE_UPLOAD', %s, %s, %s, %s, %s, %s)
        RETURNING generated_exam_question_id
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(session_query, (int(session_id),))
                session_row = cur.fetchone()
                if session_row is None:
                    return {"ensured": False, "reason": "SESSION_NOT_FOUND"}

                exam_version_id = int(session_row["exam_version_id"])
                generated_exam_instance_id = session_row.get("generated_exam_instance_id")

                cur.execute(placeholder_query, (exam_version_id,))
                placeholder = cur.fetchone()
                if placeholder is None:
                    return {"ensured": False, "reason": "NO_PLACEHOLDER_PROFILE"}

                if generated_exam_instance_id is None:
                    metadata_json = Jsonb(
                        {
                            "source": "file_upload_placeholder_fallback",
                            "exam_session_id": int(session_id),
                            "exam_version_id": int(exam_version_id),
                        }
                    )
                    cur.execute(
                        create_instance_query,
                        (
                            int(session_id),
                            int(exam_version_id),
                            int(actor_user_id) if actor_user_id is not None else None,
                            metadata_json,
                        ),
                    )
                    instance_row = cur.fetchone()
                    if instance_row is None:
                        conn.commit()
                        return {"ensured": False, "reason": "INSTANCE_CREATE_FAILED"}
                    generated_exam_instance_id = int(instance_row["generated_exam_instance_id"])
                else:
                    generated_exam_instance_id = int(generated_exam_instance_id)

                cur.execute(count_questions_query, (generated_exam_instance_id,))
                count_row = cur.fetchone()
                existing_count = int(count_row["total"]) if count_row is not None else 0
                if existing_count > 0:
                    conn.commit()
                    return {
                        "ensured": False,
                        "reason": "QUESTIONS_ALREADY_EXIST",
                        "generated_exam_instance_id": generated_exam_instance_id,
                    }

                metadata = placeholder.get("metadata_json") if isinstance(placeholder.get("metadata_json"), dict) else {}
                required = bool(metadata.get("required", True))
                allowed_extensions = metadata.get("allowed_extensions")
                if not isinstance(allowed_extensions, list):
                    allowed_extensions = [".zip", ".pdf", ".docx", ".xlsx", ".csv", ".sql", ".txt", ".json"]
                allowed_mime_types = metadata.get("allowed_mime_types")
                if not isinstance(allowed_mime_types, list):
                    allowed_mime_types = [
                        "application/zip",
                        "application/x-zip-compressed",
                        "application/pdf",
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        "text/csv",
                        "application/csv",
                        "application/sql",
                        "text/plain",
                        "application/octet-stream",
                        "application/json",
                        "text/json",
                    ]
                max_file_size_bytes = metadata.get("max_file_size_bytes")
                try:
                    max_file_size_bytes_int = int(max_file_size_bytes) if max_file_size_bytes is not None else 26214400
                except (TypeError, ValueError):
                    max_file_size_bytes_int = 26214400
                if max_file_size_bytes_int <= 0:
                    max_file_size_bytes_int = 26214400

                rendered_text = str(
                    placeholder.get("template_text") or "Đính kèm bài làm theo yêu cầu trong đề thi."
                ).strip()
                question_code = str(placeholder.get("template_code") or "FILE-UPLOAD-PLACEHOLDER").strip() or "FILE-UPLOAD-PLACEHOLDER"
                score_raw = placeholder.get("max_score")
                if score_raw is None:
                    score_raw = placeholder.get("default_score")
                score = float(score_raw) if score_raw is not None else 10.0
                if score <= 0:
                    score = 10.0

                rendered_payload_data = {
                    "answer_ui": {
                        "ui_mode": "FILE_UPLOAD",
                        "input_source": "SEALED_FILE_REF",
                        "required": required,
                        "allowed_extensions": allowed_extensions,
                        "allowed_mime_types": allowed_mime_types,
                        "max_file_size_bytes": max_file_size_bytes_int,
                    }
                }
                rendered_payload_json = Jsonb(rendered_payload_data)
                metadata_json = Jsonb(
                    {
                        "source": "file_upload_placeholder_fallback",
                        "placeholder_question": True,
                    }
                )
                variant_code = str(metadata.get("variant_code")).strip()[:100] if metadata.get("variant_code") is not None else None
                variant_parameters = metadata.get("variant_parameters") if isinstance(metadata.get("variant_parameters"), dict) else {}
                cur.execute(
                    insert_question_query,
                    (
                        generated_exam_instance_id,
                        int(placeholder["question_template_id"]),
                        int(placeholder["question_template_id"]),
                        None,
                        question_code,
                        variant_code,
                        Jsonb(variant_parameters),
                        rendered_text,
                        rendered_payload_json,
                        self._rendered_question_hash(
                            rendered_question_text=rendered_text,
                            rendered_question_payload=rendered_payload_data,
                        ),
                        score,
                        metadata_json,
                        int(placeholder["question_grading_profile_id"]),
                    ),
                )
                question_row = cur.fetchone()
            conn.commit()

        if question_row is None:
            return {"ensured": False, "reason": "QUESTION_CREATE_FAILED"}
        return {
            "ensured": True,
            "reason": "QUESTION_CREATED",
            "generated_exam_instance_id": int(generated_exam_instance_id),
            "generated_exam_question_id": int(question_row["generated_exam_question_id"]),
        }

    def get_student_id_by_user_id(self, user_id: int) -> int | None:
        query = """
        SELECT sp.student_id
        FROM identity.app_user u
        JOIN identity.student_profile sp
            ON sp.person_id = u.person_id
        WHERE u.user_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (user_id,))
                row = cur.fetchone()
        if row is None:
            return None
        return int(row["student_id"])

    def get_or_create_submission_for_session(self, *, session_id: int, actor_user_id: int | None) -> dict:
        query = """
        WITH generated AS (
            SELECT
                gei.exam_session_id,
                gei.generated_exam_instance_id
            FROM delivery.generated_exam_instance gei
            WHERE gei.exam_session_id = %s
              AND gei.generation_status = 'GENERATED'
            LIMIT 1
        ),
        inserted AS (
            INSERT INTO submission.exam_submission (
                exam_session_id,
                generated_exam_instance_id,
                submission_status,
                opened_at,
                created_by
            )
            SELECT
                generated.exam_session_id,
                generated.generated_exam_instance_id,
                'DRAFT',
                now(),
                %s
            FROM generated
            ON CONFLICT (exam_session_id) DO NOTHING
            RETURNING
                exam_submission_id,
                exam_session_id,
                generated_exam_instance_id,
                submission_status,
                opened_at,
                first_saved_at,
                last_saved_at,
                submitted_at,
                sealed_at
        )
        SELECT * FROM inserted
        UNION ALL
        SELECT
            sub.exam_submission_id,
            sub.exam_session_id,
            sub.generated_exam_instance_id,
            sub.submission_status,
            sub.opened_at,
            sub.first_saved_at,
            sub.last_saved_at,
            sub.submitted_at,
            sub.sealed_at
        FROM submission.exam_submission sub
        JOIN generated
            ON generated.exam_session_id = sub.exam_session_id
        WHERE sub.exam_session_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (session_id, actor_user_id, session_id))
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to open submission for exam session")
        return row

    def start_session(self, session_id: int) -> dict | None:
        query = """
        UPDATE delivery.exam_session
        SET
            started_at = coalesce(started_at, now()),
            deadline_at = coalesce(
                deadline_at,
                coalesce(started_at, now()) + make_interval(secs => (time_limit_seconds + extra_time_seconds))
            ),
            session_status = CASE
                WHEN session_status IN ('CREATED', 'WAITING_FOR_CHECKIN', 'READY_TO_START', 'PAUSED', 'INTERRUPTED')
                    THEN 'IN_PROGRESS'
                ELSE session_status
            END,
            last_seen_at = now(),
            last_activity_at = now(),
            updated_at = now()
        WHERE exam_session_id = %s
        RETURNING
            exam_session_id,
            exam_assignment_id,
            session_code,
            session_no,
            session_status,
            started_at,
            deadline_at,
            ended_at,
            time_limit_seconds,
            extra_time_seconds,
            last_seen_at,
            last_activity_at
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (session_id,))
                row = cur.fetchone()
            conn.commit()
        return row

    def start_session_with_room_guard(self, session_id: int) -> dict | None:
        query = """
        UPDATE delivery.exam_session
        SET
            started_at = coalesce(started_at, now()),
            deadline_at = coalesce(
                deadline_at,
                coalesce(started_at, now()) + make_interval(secs => (time_limit_seconds + extra_time_seconds))
            ),
            session_status = CASE
                WHEN session_status IN ('CREATED', 'WAITING_FOR_CHECKIN', 'READY_TO_START', 'PAUSED', 'INTERRUPTED')
                    THEN 'IN_PROGRESS'
                ELSE session_status
            END,
            last_seen_at = now(),
            last_activity_at = now(),
            updated_at = now()
        WHERE exam_session_id = %s
        RETURNING
            exam_session_id,
            exam_assignment_id,
            session_code,
            session_no,
            session_status,
            started_at,
            deadline_at,
            ended_at,
            time_limit_seconds,
            extra_time_seconds,
            last_seen_at,
            last_activity_at
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                session_state = self._get_locked_session_room_state_with_cursor(
                    cur=cur,
                    session_id=int(session_id),
                    lock_clause="FOR UPDATE",
                )
                if session_state is None:
                    conn.rollback()
                    return None
                if str(session_state.get("room_status") or "").strip().upper() == "CLOSED":
                    conn.commit()
                    return {**session_state, "__start_result": "room_closed"}
                cur.execute(query, (int(session_id),))
                row = cur.fetchone()
            conn.commit()
        if row is None:
            return None
        return {**row, "__start_result": "started"}

    def touch_heartbeat(self, session_id: int, *, last_activity_at: datetime | None) -> dict | None:
        query = """
        UPDATE delivery.exam_session
        SET
            last_seen_at = now(),
            last_activity_at = coalesce(%s, now()),
            updated_at = now()
        WHERE exam_session_id = %s
        RETURNING
            exam_session_id,
            exam_assignment_id,
            session_code,
            session_no,
            session_status,
            started_at,
            deadline_at,
            ended_at,
            time_limit_seconds,
            extra_time_seconds,
            last_seen_at,
            last_activity_at
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (last_activity_at, session_id))
                row = cur.fetchone()
            conn.commit()
        return row

    def touch_heartbeat_with_room_guard(
        self,
        session_id: int,
        *,
        last_activity_at: datetime | None,
        terminal_session_statuses: tuple[str, ...],
    ) -> dict | None:
        query = """
        UPDATE delivery.exam_session
        SET
            last_seen_at = now(),
            last_activity_at = coalesce(%s, now()),
            updated_at = now()
        WHERE exam_session_id = %s
        RETURNING
            exam_session_id,
            exam_assignment_id,
            session_code,
            session_no,
            session_status,
            started_at,
            deadline_at,
            ended_at,
            time_limit_seconds,
            extra_time_seconds,
            last_seen_at,
            last_activity_at
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                session_state = self._get_locked_session_room_state_with_cursor(
                    cur=cur,
                    session_id=int(session_id),
                    lock_clause="FOR SHARE",
                )
                if session_state is None:
                    conn.rollback()
                    return None
                if str(session_state.get("room_status") or "").strip().upper() == "CLOSED":
                    result_code = "room_closed"
                    if str(session_state.get("session_status") or "").strip().upper() in set(terminal_session_statuses):
                        result_code = "terminal_closed"
                    conn.commit()
                    return {**session_state, "__heartbeat_result": result_code}
                cur.execute(query, (last_activity_at, int(session_id)))
                row = cur.fetchone()
            conn.commit()
        if row is None:
            return None
        return {**row, "__heartbeat_result": "touched"}

    def list_generated_paper_questions(self, session_id: int) -> list[dict]:
        query = """
        SELECT
            geq.generated_exam_question_id,
                        geq.original_question_id,
                        geq.source_exam_question_id,
                        geq.canonical_section_order,
                        geq.canonical_question_order,
                        coalesce(geq.display_question_order, geq.question_order) AS display_question_order,
                        geq.question_order,
            geq.question_code,
            geq.question_type,
                        geq.variant_code,
            geq.rendered_question_text,
            geq.rendered_question_payload_json,
            geq.score,
                        coalesce(qgp_snapshot.input_source, qgp_fallback.input_source) AS grading_input_source,
                        coalesce(qgp_snapshot.answer_language, qgp_fallback.answer_language) AS grading_answer_language,
                        coalesce(qgp_snapshot_engine.engine_code, qgp_fallback.engine_code) AS grading_engine_code,
                        coalesce(qgp_snapshot.comparison_method, qgp_fallback.comparison_method) AS grading_comparison_method,
                        coalesce(qgp_snapshot.requires_capture, qgp_fallback.requires_capture) AS grading_requires_capture,
                        coalesce(qgp_snapshot.required_capture_type, qgp_fallback.required_capture_type) AS grading_required_capture_type,
                        coalesce(qgp_snapshot.metadata_json, qgp_fallback.metadata_json) AS grading_profile_metadata_json
        FROM delivery.exam_session es
        JOIN delivery.generated_exam_instance gei
          ON gei.exam_session_id = es.exam_session_id
        JOIN delivery.generated_exam_question geq
          ON geq.generated_exam_instance_id = gei.generated_exam_instance_id
                LEFT JOIN assessment.question_grading_profile qgp_snapshot
                    ON qgp_snapshot.question_grading_profile_id = geq.question_grading_profile_id
                LEFT JOIN grading.grading_engine qgp_snapshot_engine
                    ON qgp_snapshot_engine.grading_engine_id = qgp_snapshot.grading_engine_id
                LEFT JOIN LATERAL (
            SELECT
                                profile.question_grading_profile_id,
                profile.input_source,
                profile.answer_language,
                engine.engine_code,
                profile.comparison_method,
                profile.requires_capture,
                profile.required_capture_type,
                profile.metadata_json
            FROM assessment.question_grading_profile profile
            LEFT JOIN grading.grading_engine engine
              ON engine.grading_engine_id = profile.grading_engine_id
            WHERE profile.question_template_id = geq.question_template_id
              AND profile.status IN ('ACTIVE', 'DRAFT')
              AND (
                profile.exam_version_id = gei.exam_version_id
                OR profile.exam_version_id IS NULL
              )
            ORDER BY
                CASE WHEN profile.exam_version_id = gei.exam_version_id THEN 0 ELSE 1 END,
                profile.question_grading_profile_id DESC
            LIMIT 1
                ) qgp_fallback ON geq.question_grading_profile_id IS NULL
        WHERE es.exam_session_id = %s
          AND gei.generation_status IN ('GENERATED', 'VOIDED')
                ORDER BY coalesce(geq.display_question_order, geq.question_order), geq.generated_exam_question_id
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (session_id,))
                return cur.fetchall()

        def list_generated_question_options_for_session(self, session_id: int) -> list[dict]:
                query = """
                SELECT
                        geq.generated_exam_question_id,
                        geo.generated_exam_option_id,
                        geo.option_order,
                        geo.option_label,
                        geo.rendered_option_text,
                        geo.rendered_option_payload_json
                FROM delivery.exam_session es
                JOIN delivery.generated_exam_instance gei
                    ON gei.exam_session_id = es.exam_session_id
                JOIN delivery.generated_exam_question geq
                    ON geq.generated_exam_instance_id = gei.generated_exam_instance_id
                JOIN delivery.generated_exam_option geo
                    ON geo.generated_exam_question_id = geq.generated_exam_question_id
                WHERE es.exam_session_id = %s
                    AND gei.generation_status IN ('GENERATED', 'VOIDED')
                ORDER BY geq.question_order, geo.option_order, geo.generated_exam_option_id
                """
                with open_connection() as conn:
                        with conn.cursor(row_factory=dict_row) as cur:
                                cur.execute(query, (session_id,))
                                return cur.fetchall()

    def list_current_answer_file_assets_for_submission(self, submission_id: int) -> list[dict]:
        table_check_query = "SELECT to_regclass('submission.answer_file_asset') AS table_name"
        query = """
        SELECT DISTINCT ON (generated_exam_question_id)
            answer_file_asset_id,
            exam_submission_id,
            generated_exam_question_id,
            answer_state_id,
            original_filename,
            mime_type,
            file_size_bytes,
            sha256_hash,
            asset_status,
            uploaded_at
        FROM submission.answer_file_asset
        WHERE exam_submission_id = %s
          AND asset_status = 'ACTIVE'
        ORDER BY generated_exam_question_id, uploaded_at DESC, answer_file_asset_id DESC
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(table_check_query)
                table_check = cur.fetchone()
                if table_check is None or table_check.get("table_name") is None:
                    return []
                cur.execute(query, (int(submission_id),))
                return cur.fetchall()

    def list_active_paper_assets_for_session(self, session_id: int) -> list[dict]:
        table_check_query = "SELECT to_regclass('assessment.exam_version_paper_asset') AS table_name"
        query = """
        SELECT
            pa.paper_asset_id,
            pa.exam_version_id,
            pa.asset_kind,
            pa.original_filename,
            pa.stored_filename,
            pa.storage_relative_path,
            pa.mime_type,
            pa.file_size_bytes,
            pa.sha256_hash,
            pa.page_count,
            pa.render_status,
            pa.is_active,
            pa.created_at,
            pa.metadata_json
        FROM delivery.exam_session es
        JOIN delivery.exam_assignment ea
          ON ea.exam_assignment_id = es.exam_assignment_id
        JOIN delivery.exam_sitting sit
          ON sit.exam_sitting_id = ea.exam_sitting_id
        JOIN assessment.exam_version_paper_asset pa
          ON pa.exam_version_id = sit.exam_version_id
        WHERE es.exam_session_id = %s
          AND pa.is_active = true
        ORDER BY pa.created_at DESC, pa.paper_asset_id DESC
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(table_check_query)
                table_check = cur.fetchone()
                if table_check is None or table_check.get("table_name") is None:
                    return []
                cur.execute(query, (session_id,))
                return cur.fetchall()

    def get_active_paper_asset_for_session(self, *, session_id: int, paper_asset_id: int) -> dict | None:
        table_check_query = "SELECT to_regclass('assessment.exam_version_paper_asset') AS table_name"
        query = """
        SELECT
            pa.paper_asset_id,
            pa.exam_version_id,
            pa.asset_kind,
            pa.original_filename,
            pa.stored_filename,
            pa.storage_relative_path,
            pa.mime_type,
            pa.file_size_bytes,
            pa.sha256_hash,
            pa.page_count,
            pa.render_status,
            pa.is_active,
            pa.created_at,
            pa.metadata_json
        FROM delivery.exam_session es
        JOIN delivery.exam_assignment ea
          ON ea.exam_assignment_id = es.exam_assignment_id
        JOIN delivery.exam_sitting sit
          ON sit.exam_sitting_id = ea.exam_sitting_id
        JOIN assessment.exam_version_paper_asset pa
          ON pa.exam_version_id = sit.exam_version_id
        WHERE es.exam_session_id = %s
          AND pa.paper_asset_id = %s
          AND pa.is_active = true
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(table_check_query)
                table_check = cur.fetchone()
                if table_check is None or table_check.get("table_name") is None:
                    return None
                cur.execute(query, (session_id, paper_asset_id))
                return cur.fetchone()

    def get_active_device_binding(self, session_id: int) -> dict | None:
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                return self._get_active_device_binding_with_cursor(cur=cur, session_id=int(session_id))

    def _get_active_device_binding_with_cursor(self, *, cur, session_id: int) -> dict | None:
        query = """
        SELECT
            session_device_binding_id,
            exam_session_id,
            exam_sitting_id,
            station_id,
            device_id,
            binding_status,
            bound_at,
            unbound_at,
            bind_reason
        FROM delivery.exam_session_device_binding
        WHERE exam_session_id = %s
          AND binding_status = 'ACTIVE'
        ORDER BY bound_at DESC, session_device_binding_id DESC
        LIMIT 1
        """
        cur.execute(query, (int(session_id),))
        return cur.fetchone()

    def close_active_binding(self, session_device_binding_id: int) -> None:
        with open_connection() as conn:
            with conn.cursor() as cur:
                self._close_active_binding_with_cursor(cur=cur, session_device_binding_id=int(session_device_binding_id))
            conn.commit()

    def _close_active_binding_with_cursor(self, *, cur, session_device_binding_id: int) -> None:
        query = """
        UPDATE delivery.exam_session_device_binding
        SET
            binding_status = 'TRANSFERRED',
            unbound_at = now()
        WHERE session_device_binding_id = %s
          AND binding_status = 'ACTIVE'
        """
        cur.execute(query, (int(session_device_binding_id),))

    def create_device_binding(
        self,
        *,
        exam_session_id: int,
        exam_sitting_id: int,
        station_id: int,
        device_id: int | None,
        bind_reason: str,
        ip_address: str | None,
        hostname: str | None,
        client_fingerprint: str | None,
        metadata_json: dict | None,
    ) -> dict:
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                row = self._create_device_binding_with_cursor(
                    cur=cur,
                    exam_session_id=int(exam_session_id),
                    exam_sitting_id=int(exam_sitting_id),
                    station_id=int(station_id),
                    device_id=int(device_id) if device_id is not None else None,
                    bind_reason=str(bind_reason),
                    ip_address=ip_address,
                    hostname=hostname,
                    client_fingerprint=client_fingerprint,
                    metadata_json=metadata_json,
                )
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to create delivery.exam_session_device_binding")
        return row

    def _create_device_binding_with_cursor(
        self,
        *,
        cur,
        exam_session_id: int,
        exam_sitting_id: int,
        station_id: int,
        device_id: int | None,
        bind_reason: str,
        ip_address: str | None,
        hostname: str | None,
        client_fingerprint: str | None,
        metadata_json: dict | None,
    ) -> dict | None:
        query = """
        INSERT INTO delivery.exam_session_device_binding (
            exam_session_id,
            exam_sitting_id,
            station_id,
            device_id,
            binding_status,
            bound_at,
            ip_address,
            hostname,
            client_fingerprint,
            bind_reason,
            metadata_json
        )
        VALUES (%s, %s, %s, %s, 'ACTIVE', now(), %s, %s, %s, %s, %s)
        RETURNING
            session_device_binding_id,
            exam_session_id,
            exam_sitting_id,
            station_id,
            device_id,
            binding_status,
            bound_at,
            unbound_at,
            bind_reason
        """
        payload = Jsonb(metadata_json) if metadata_json is not None else None
        cur.execute(
            query,
            (
                int(exam_session_id),
                int(exam_sitting_id),
                int(station_id),
                int(device_id) if device_id is not None else None,
                ip_address,
                hostname,
                client_fingerprint,
                bind_reason,
                payload,
            ),
        )
        return cur.fetchone()

    def replace_device_binding_with_room_guard(
        self,
        *,
        exam_session_id: int,
        exam_sitting_id: int,
        station_id: int,
        device_id: int | None,
        bind_reason: str,
        ip_address: str | None,
        hostname: str | None,
        client_fingerprint: str | None,
        metadata_json: dict | None,
    ) -> dict | None:
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                session_state = self._get_locked_session_room_state_with_cursor(
                    cur=cur,
                    session_id=int(exam_session_id),
                    lock_clause="FOR UPDATE",
                )
                if session_state is None:
                    conn.rollback()
                    return None
                if str(session_state.get("room_status") or "").strip().upper() == "CLOSED":
                    conn.commit()
                    return {**session_state, "__bind_result": "room_closed"}

                active = self._get_active_device_binding_with_cursor(cur=cur, session_id=int(exam_session_id))
                if active is not None:
                    same_station = int(active["station_id"]) == int(station_id)
                    same_device = (active.get("device_id") is None and device_id is None) or (
                        active.get("device_id") is not None and int(active["device_id"]) == int(device_id)
                    )
                    if same_station and same_device:
                        conn.commit()
                        return {"__bind_result": "idempotent", "binding": active}
                    self._close_active_binding_with_cursor(
                        cur=cur,
                        session_device_binding_id=int(active["session_device_binding_id"]),
                    )

                binding = self._create_device_binding_with_cursor(
                    cur=cur,
                    exam_session_id=int(exam_session_id),
                    exam_sitting_id=int(exam_sitting_id),
                    station_id=int(station_id),
                    device_id=int(device_id) if device_id is not None else None,
                    bind_reason=str(bind_reason),
                    ip_address=ip_address,
                    hostname=hostname,
                    client_fingerprint=client_fingerprint,
                    metadata_json=metadata_json,
                )
            conn.commit()
        if binding is None:
            return None
        return {"__bind_result": "created", "binding": binding}

    def create_session_event(
        self,
        *,
        exam_session_id: int,
        event_type: str,
        actor_user_id: int | None,
        station_id: int | None = None,
        device_id: int | None = None,
        event_payload_json: dict | None = None,
    ) -> None:
        query = """
        INSERT INTO delivery.exam_session_event (
            exam_session_id,
            event_type,
            event_at,
            actor_user_id,
            station_id,
            device_id,
            event_payload_json
        )
        VALUES (%s, %s, now(), %s, %s, %s, %s)
        """
        payload = Jsonb(event_payload_json) if event_payload_json is not None else None
        with open_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        exam_session_id,
                        event_type,
                        actor_user_id,
                        station_id,
                        device_id,
                        payload,
                    ),
                )
            conn.commit()

    def _insert_room_history_row(self, *, cur, payload: dict) -> dict | None:
        query = """
        INSERT INTO delivery.exam_sitting_room_history (
            exam_sitting_room_id,
            actor_user_id,
            actor_role,
            action_type,
            from_room_status,
            to_room_status,
            close_reason,
            close_note,
            close_summary_json,
            blocker_summary_json,
            context_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING
            room_history_id,
            exam_sitting_room_id,
            actor_user_id,
            actor_role,
            action_type,
            from_room_status,
            to_room_status,
            close_reason,
            close_note,
            close_summary_json,
            blocker_summary_json,
            context_json,
            changed_at
        """
        cur.execute(
            query,
            (
                int(payload["exam_sitting_room_id"]),
                int(payload["actor_user_id"]) if payload.get("actor_user_id") is not None else None,
                str(payload.get("actor_role") or "UNKNOWN"),
                str(payload.get("action_type") or "ROOM_UPDATED"),
                str(payload["from_room_status"]).strip().upper() if payload.get("from_room_status") is not None else None,
                str(payload.get("to_room_status") or "CLOSED").strip().upper(),
                payload.get("close_reason"),
                payload.get("close_note"),
                Jsonb(payload.get("close_summary_json")) if payload.get("close_summary_json") is not None else None,
                Jsonb(payload.get("blocker_summary_json")) if payload.get("blocker_summary_json") is not None else None,
                Jsonb(payload.get("context_json")) if payload.get("context_json") is not None else None,
            ),
        )
        return cur.fetchone()

    def insert_room_history(self, *, payload: dict) -> dict:
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                row = self._insert_room_history_row(cur=cur, payload=payload)
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to insert delivery.exam_sitting_room_history")
        return row

    def close_room_with_history(
        self,
        *,
        exam_sitting_room_id: int,
        actor_user_id: int | None,
        actor_role: str,
        close_reason: str,
        close_note: str | None,
        close_summary_json: dict,
        blocker_summary_json: dict | None,
        context_json: dict | None,
        heartbeat_seconds: int,
    ) -> dict | None:
        select_query = """
        SELECT
            exam_sitting_room_id,
            exam_sitting_id,
            room_id,
            room_status,
            capacity_allocated,
            closed_at,
            closed_by,
            close_reason,
            close_note,
            close_summary_json,
            updated_at,
            updated_by
        FROM delivery.exam_sitting_room
        WHERE exam_sitting_room_id = %s
        FOR UPDATE
        """
        update_query = """
        UPDATE delivery.exam_sitting_room
        SET
            room_status = 'CLOSED',
            closed_at = now(),
            closed_by = %s,
            close_reason = %s,
            close_note = %s,
            close_summary_json = %s,
            updated_at = now(),
            updated_by = %s
        WHERE exam_sitting_room_id = %s
        RETURNING
            exam_sitting_room_id,
            exam_sitting_id,
            room_id,
            room_status,
            capacity_allocated,
            closed_at,
            closed_by,
            close_reason,
            close_note,
            close_summary_json,
            updated_at,
            updated_by
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(select_query, (int(exam_sitting_room_id),))
                existing = cur.fetchone()
                if existing is None:
                    conn.rollback()
                    return None
                existing_room_status = str(existing.get("room_status") or "").strip().upper()
                if existing_room_status == "CLOSED":
                    conn.commit()
                    return {**existing, "__close_result": "already_closed"}
                if existing_room_status not in self._ROOM_CLOSEABLE_ROOM_STATUSES:
                    conn.rollback()
                    return {**existing, "__close_result": "invalid_status"}

                counts = self._get_room_close_counts_with_cursor(
                    cur=cur,
                    exam_sitting_room_id=int(exam_sitting_room_id),
                    heartbeat_seconds=int(heartbeat_seconds),
                )
                if any(
                    counts[key] > 0
                    for key in (
                        "pending_attendance_count",
                        "open_incident_count",
                        "in_progress_incident_count",
                        "active_session_count",
                        "interrupted_session_count",
                        "pending_submission_count",
                        "stale_heartbeat_count",
                    )
                ):
                    conn.rollback()
                    return {**existing, "__close_result": "blocked", "blocker_counts": counts}

                cur.execute(
                    update_query,
                    (
                        int(actor_user_id) if actor_user_id is not None else None,
                        close_reason,
                        close_note,
                        Jsonb(close_summary_json),
                        int(actor_user_id) if actor_user_id is not None else None,
                        int(exam_sitting_room_id),
                    ),
                )
                row = cur.fetchone()
                if row is None:
                    conn.rollback()
                    return None

                self._insert_room_history_row(
                    cur=cur,
                    payload={
                        "exam_sitting_room_id": int(exam_sitting_room_id),
                        "actor_user_id": int(actor_user_id) if actor_user_id is not None else None,
                        "actor_role": actor_role,
                        "action_type": "ROOM_CLOSED",
                        "from_room_status": existing.get("room_status"),
                        "to_room_status": "CLOSED",
                        "close_reason": close_reason,
                        "close_note": close_note,
                        "close_summary_json": close_summary_json,
                        "blocker_summary_json": blocker_summary_json,
                        "context_json": context_json,
                    },
                )
            conn.commit()
        return {**row, "__close_result": "closed"}

    def get_active_session_by_exam_assignment(self, exam_assignment_id: int) -> dict | None:
        query = """
        SELECT
            es.exam_session_id,
            es.exam_assignment_id,
            es.session_status,
            es.session_no,
            gei.generated_exam_instance_id,
            gei.generation_status
        FROM delivery.exam_session es
        LEFT JOIN delivery.generated_exam_instance gei
            ON gei.exam_session_id = es.exam_session_id
        WHERE es.exam_assignment_id = %s
            AND es.session_status IN ('CREATED', 'WAITING_FOR_CHECKIN', 'READY_TO_START', 'IN_PROGRESS', 'PAUSED', 'INTERRUPTED')
        ORDER BY es.session_no DESC, es.exam_session_id DESC
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_assignment_id),))
                return cur.fetchone()

    # Phase 3.0 setup APIs
    def list_exam_sittings(self) -> list[dict]:
        return self.list_setup_sittings()

    def get_exam_sitting_by_id(self, exam_sitting_id: int) -> dict | None:
        return self.get_setup_sitting_by_id(int(exam_sitting_id))

    def get_exam_sitting_readiness_context(self, exam_sitting_id: int) -> dict | None:
        query = """
        SELECT
            sit.exam_sitting_id,
            sit.exam_version_id,
            sit.sitting_code,
            sit.sitting_name,
            sit.sitting_status,
            ev.status AS exam_version_status,
            ev.shuffle_questions,
            ev.shuffle_options,
            ev.randomization_mode,
            evdp.exam_version_delivery_profile_id,
            evdp.delivery_mode,
            evdp.primary_answer_source,
            evdp.requires_capture,
            evdp.database_work_mode,
            evdp.status AS delivery_profile_status,
            evdp.metadata_json AS delivery_profile_metadata_json
        FROM delivery.exam_sitting sit
        LEFT JOIN assessment.exam_version ev
          ON ev.exam_version_id = sit.exam_version_id
        LEFT JOIN assessment.exam_version_delivery_profile evdp
          ON evdp.exam_version_id = sit.exam_version_id
        WHERE sit.exam_sitting_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_id),))
                return cur.fetchone()

    def list_exam_sitting_readiness_assignments(self, exam_sitting_id: int) -> list[dict]:
        query = """
        SELECT
            exam_assignment_id,
            exam_sitting_id,
            student_id,
            assignment_status
        FROM delivery.exam_assignment
        WHERE exam_sitting_id = %s
          AND assignment_status IN ('ASSIGNED', 'CHECKED_IN')
        ORDER BY exam_assignment_id
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_id),))
                return cur.fetchall()

    def list_exam_sitting_readiness_station_assignments(self, exam_sitting_id: int) -> list[dict]:
        query = """
        SELECT
            esa.station_assignment_id,
            esa.exam_assignment_id,
            esa.exam_sitting_room_id,
            esa.station_id,
            esa.status,
            esr.room_id AS sitting_room_room_id,
            station.room_id AS station_room_id
        FROM delivery.exam_station_assignment esa
        JOIN delivery.exam_assignment ea
          ON ea.exam_assignment_id = esa.exam_assignment_id
        JOIN delivery.exam_sitting_room esr
          ON esr.exam_sitting_room_id = esa.exam_sitting_room_id
        JOIN facility.lab_station station
          ON station.station_id = esa.station_id
        WHERE ea.exam_sitting_id = %s
          AND ea.assignment_status IN ('ASSIGNED', 'CHECKED_IN')
          AND esa.status IN ('ASSIGNED', 'CHECKED_IN', 'TRANSFERRED')
        ORDER BY esa.station_assignment_id
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_id),))
                return cur.fetchall()

    def list_exam_sitting_readiness_proctors(self, exam_sitting_id: int) -> list[dict]:
        query = """
        SELECT
            pa.proctor_assignment_id,
            pa.exam_sitting_room_id,
            pa.proctor_user_id,
            pa.proctor_role,
            pa.status
        FROM delivery.proctor_assignment pa
        JOIN delivery.exam_sitting_room esr
          ON esr.exam_sitting_room_id = pa.exam_sitting_room_id
        WHERE esr.exam_sitting_id = %s
          AND pa.status IN ('ASSIGNED', 'CONFIRMED')
        ORDER BY pa.proctor_assignment_id
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_id),))
                return cur.fetchall()

    def list_exam_version_readiness_question_profiles(self, exam_version_id: int) -> list[dict]:
        query = """
        SELECT
            qgp.question_grading_profile_id,
            qgp.question_template_id,
            qgp.input_source,
            qgp.requires_capture,
            qgp.required_capture_type,
            qgp.capture_profile_id,
            qgp.grading_engine_id,
            qgp.comparison_method,
            qgp.status,
            qgp.metadata_json,
            qt.status AS question_template_status,
            cp.status AS capture_profile_status,
            CASE WHEN ge.is_active THEN 'ACTIVE' ELSE 'INACTIVE' END AS grading_engine_status,
            ge.engine_code AS grading_engine_code
        FROM assessment.question_grading_profile qgp
        JOIN assessment.question_template qt
          ON qt.question_template_id = qgp.question_template_id
        LEFT JOIN capture.capture_profile cp
          ON cp.capture_profile_id = qgp.capture_profile_id
        LEFT JOIN grading.grading_engine ge
          ON ge.grading_engine_id = qgp.grading_engine_id
        WHERE qgp.exam_version_id = %s
          AND qgp.status = 'ACTIVE'
          AND qt.status = 'ACTIVE'
        ORDER BY qgp.question_grading_profile_id
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_version_id),))
                return cur.fetchall()

    def list_exam_version_active_paper_assets(self, exam_version_id: int) -> list[dict]:
        table_check_query = "SELECT to_regclass('assessment.exam_version_paper_asset') AS table_name"
        query = """
        SELECT
            paper_asset_id,
            exam_version_id,
            asset_kind,
            render_status,
            is_active
        FROM assessment.exam_version_paper_asset
        WHERE exam_version_id = %s
          AND is_active = true
        ORDER BY paper_asset_id
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(table_check_query)
                table_check = cur.fetchone()
                if table_check is None or table_check.get("table_name") is None:
                    return []
                cur.execute(query, (int(exam_version_id),))
                return cur.fetchall()

    def update_exam_sitting(self, *, exam_sitting_id: int, payload: dict) -> dict | None:
        return self.update_setup_sitting(exam_sitting_id=int(exam_sitting_id), payload=payload)

    def room_detail(self, room_id: int) -> dict | None:
        query = """
        SELECT room_id, room_code, room_name, capacity, status
        FROM facility.room
        WHERE room_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(room_id),))
                return cur.fetchone()

    def list_sitting_rooms(self, exam_sitting_id: int) -> list[dict]:
        query = """
        SELECT
            esr.exam_sitting_room_id,
            esr.exam_sitting_id,
            esr.room_id,
            esr.capacity_allocated,
            esr.room_status,
            esr.created_at,
            r.room_code,
            r.room_name,
            r.capacity AS room_capacity,
            r.status AS room_master_status
        FROM delivery.exam_sitting_room esr
        JOIN facility.room r ON r.room_id = esr.room_id
        WHERE esr.exam_sitting_id = %s
        ORDER BY esr.exam_sitting_room_id DESC
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_id),))
                return cur.fetchall()

    def create_sitting_room(self, *, exam_sitting_id: int, room_id: int, capacity_allocated: int | None, room_status: str) -> dict:
        query = """
        INSERT INTO delivery.exam_sitting_room (
            exam_sitting_id,
            room_id,
            capacity_allocated,
            room_status
        )
        VALUES (%s, %s, %s, %s)
        RETURNING exam_sitting_room_id, exam_sitting_id, room_id, capacity_allocated, room_status, created_at
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_id), int(room_id), capacity_allocated, str(room_status).strip().upper()))
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to create delivery.exam_sitting_room")
        return row

    def count_sessions_or_submissions_for_sitting(self, exam_sitting_id: int) -> dict:
        query = """
        SELECT
            count(DISTINCT sess.exam_session_id)::bigint AS session_count,
            count(DISTINCT sub.exam_submission_id)::bigint AS submission_count
        FROM delivery.exam_assignment ea
        LEFT JOIN delivery.exam_session sess
          ON sess.exam_assignment_id = ea.exam_assignment_id
        LEFT JOIN submission.exam_submission sub
          ON sub.exam_session_id = sess.exam_session_id
        WHERE ea.exam_sitting_id = %s
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_id),))
                row = cur.fetchone()
        return {
            "session_count": int(row["session_count"] if row else 0),
            "submission_count": int(row["submission_count"] if row else 0),
        }

    def get_sitting_room_by_id(self, exam_sitting_room_id: int) -> dict | None:
        query = """
        SELECT exam_sitting_room_id, exam_sitting_id, room_id, capacity_allocated, room_status, created_at
        FROM delivery.exam_sitting_room
        WHERE exam_sitting_room_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_room_id),))
                return cur.fetchone()

    def update_sitting_room(self, *, exam_sitting_room_id: int, payload: dict) -> dict | None:
        allowed = {
            "capacity_allocated": "capacity_allocated = %s",
            "room_status": "room_status = %s",
        }
        updates: list[str] = []
        values: list[object] = []
        for key, clause in allowed.items():
            if key not in payload:
                continue
            value = payload[key]
            if key == "room_status" and value is not None:
                value = str(value).strip().upper()
            updates.append(clause)
            values.append(value)
        if not updates:
            return self.get_sitting_room_by_id(int(exam_sitting_room_id))
        values.append(int(exam_sitting_room_id))
        query = f"""
        UPDATE delivery.exam_sitting_room
        SET {", ".join(updates)}
        WHERE exam_sitting_room_id = %s
        RETURNING exam_sitting_room_id, exam_sitting_id, room_id, capacity_allocated, room_status, created_at
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, tuple(values))
                row = cur.fetchone()
            conn.commit()
        return row

    def cancel_sitting_room(self, exam_sitting_room_id: int) -> dict | None:
        return self.update_sitting_room(exam_sitting_room_id=int(exam_sitting_room_id), payload={"room_status": "CANCELLED"})

    def user_exists(self, user_id: int) -> bool:
        query = "SELECT 1 FROM identity.app_user WHERE user_id = %s LIMIT 1"
        with open_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (int(user_id),))
                return cur.fetchone() is not None

    def list_proctors(self, exam_sitting_room_id: int) -> list[dict]:
        query = """
        SELECT
            pa.proctor_assignment_id,
            pa.exam_sitting_room_id,
            pa.proctor_user_id,
            pa.proctor_role,
            pa.assigned_at,
            pa.assigned_by,
            pa.status,
            u.username,
            p.full_name AS display_name,
            COALESCE(p.full_name, u.username, pa.proctor_user_id::text) AS proctor_display_name
        FROM delivery.proctor_assignment pa
        LEFT JOIN identity.app_user u ON u.user_id = pa.proctor_user_id
        LEFT JOIN identity.person p ON p.person_id = u.person_id
        WHERE pa.exam_sitting_room_id = %s
        ORDER BY pa.proctor_assignment_id DESC
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_room_id),))
                return cur.fetchall()

    def create_proctor_assignment(
        self,
        *,
        exam_sitting_room_id: int,
        proctor_user_id: int,
        proctor_role: str,
        assigned_by: int | None,
        status: str,
    ) -> dict:
        query = """
        INSERT INTO delivery.proctor_assignment (
            exam_sitting_room_id,
            proctor_user_id,
            proctor_role,
            assigned_by,
            status
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING proctor_assignment_id, exam_sitting_room_id, proctor_user_id, proctor_role, assigned_at, assigned_by, status
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (int(exam_sitting_room_id), int(proctor_user_id), str(proctor_role).strip().upper(), assigned_by, str(status).strip().upper()),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to create delivery.proctor_assignment")
        return row

    def get_proctor_assignment_by_id(self, proctor_assignment_id: int) -> dict | None:
        query = """
        SELECT proctor_assignment_id, exam_sitting_room_id, proctor_user_id, proctor_role, assigned_at, assigned_by, status
        FROM delivery.proctor_assignment
        WHERE proctor_assignment_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(proctor_assignment_id),))
                return cur.fetchone()

    def update_proctor_assignment(self, *, proctor_assignment_id: int, payload: dict) -> dict | None:
        allowed = {"proctor_role": "proctor_role = %s", "status": "status = %s"}
        updates: list[str] = []
        values: list[object] = []
        for key, clause in allowed.items():
            if key in payload:
                value = payload[key]
                if value is not None:
                    value = str(value).strip().upper()
                updates.append(clause)
                values.append(value)
        if not updates:
            return self.get_proctor_assignment_by_id(int(proctor_assignment_id))
        values.append(int(proctor_assignment_id))
        query = f"""
        UPDATE delivery.proctor_assignment
        SET {", ".join(updates)}
        WHERE proctor_assignment_id = %s
        RETURNING proctor_assignment_id, exam_sitting_room_id, proctor_user_id, proctor_role, assigned_at, assigned_by, status
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, tuple(values))
                row = cur.fetchone()
            conn.commit()
        return row

    def cancel_proctor_assignment(self, proctor_assignment_id: int) -> dict | None:
        return self.update_proctor_assignment(proctor_assignment_id=int(proctor_assignment_id), payload={"status": "CANCELLED"})

    def student_exists(self, student_id: int) -> bool:
        query = "SELECT 1 FROM identity.student_profile WHERE student_id = %s LIMIT 1"
        with open_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (int(student_id),))
                return cur.fetchone() is not None

    def get_student_by_code(self, student_code: str) -> dict | None:
        query = """
        SELECT student_id, student_code
        FROM identity.student_profile
        WHERE lower(student_code) = lower(%s)
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (str(student_code).strip(),))
                return cur.fetchone()

    def get_exam_sitting_by_code(self, sitting_code: str) -> dict | None:
        query = """
        SELECT
            sit.exam_sitting_id,
            sit.exam_version_id,
            sit.sitting_code,
            sit.sitting_name,
            sit.scheduled_start_at,
            sit.scheduled_end_at,
            sit.timezone,
            sit.sitting_status,
            sit.created_by,
            sit.created_at,
            sit.updated_at
        FROM delivery.exam_sitting sit
        WHERE lower(sit.sitting_code) = lower(%s)
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (str(sitting_code).strip(),))
                return cur.fetchone()

    def list_exam_assignments(self, exam_sitting_id: int) -> list[dict]:
        query = """
        SELECT
            ea.exam_assignment_id,
            ea.exam_sitting_id,
            ea.student_id,
            ea.assignment_status,
            ea.assigned_at,
            ea.assigned_by,
            ea.note,
            sp.student_code,
            p.full_name
        FROM delivery.exam_assignment ea
        LEFT JOIN identity.student_profile sp ON sp.student_id = ea.student_id
        LEFT JOIN identity.person p ON p.person_id = sp.person_id
        WHERE ea.exam_sitting_id = %s
        ORDER BY ea.exam_assignment_id DESC
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_id),))
                return cur.fetchall()

    def create_exam_assignment(
        self,
        *,
        exam_sitting_id: int,
        student_id: int,
        assignment_status: str,
        assigned_by: int | None,
        note: str | None,
    ) -> dict:
        query = """
        INSERT INTO delivery.exam_assignment (
            exam_sitting_id, student_id, assignment_status, assigned_by, note
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING exam_assignment_id, exam_sitting_id, student_id, assignment_status, assigned_at, assigned_by, note
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (int(exam_sitting_id), int(student_id), str(assignment_status).strip().upper(), assigned_by, note),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to create delivery.exam_assignment")
        return row

    def get_exam_assignment_by_id(self, exam_assignment_id: int) -> dict | None:
        query = """
        SELECT exam_assignment_id, exam_sitting_id, student_id, assignment_status, assigned_at, assigned_by, note
        FROM delivery.exam_assignment
        WHERE exam_assignment_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_assignment_id),))
                return cur.fetchone()

    def get_exam_assignment_by_sitting_student(self, *, exam_sitting_id: int, student_id: int) -> dict | None:
        query = """
        SELECT exam_assignment_id, exam_sitting_id, student_id, assignment_status, assigned_at, assigned_by, note
        FROM delivery.exam_assignment
        WHERE exam_sitting_id = %s
          AND student_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_id), int(student_id)))
                return cur.fetchone()

    def get_room_student_session_target(self, *, exam_sitting_room_id: int, student_id: int) -> dict | None:
        query = """
        SELECT
            ea.exam_assignment_id,
            ea.exam_sitting_id,
            esa.exam_sitting_room_id,
            ea.student_id,
            u.user_id
        FROM delivery.exam_assignment ea
        JOIN delivery.exam_station_assignment esa
          ON esa.exam_assignment_id = ea.exam_assignment_id
        JOIN identity.student_profile sp
          ON sp.student_id = ea.student_id
        LEFT JOIN identity.app_user u
          ON u.person_id = sp.person_id
        WHERE esa.exam_sitting_room_id = %s
          AND ea.student_id = %s
          AND ea.assignment_status NOT IN ('CANCELLED', 'VOIDED')
        ORDER BY esa.station_assignment_id DESC, ea.exam_assignment_id DESC
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_room_id), int(student_id)))
                return cur.fetchone()

    def get_room_assignment_target(self, *, exam_sitting_room_id: int, exam_assignment_id: int) -> dict | None:
        query = """
        SELECT
            ea.exam_assignment_id,
            ea.exam_sitting_id,
            ea.student_id,
            ea.assignment_status,
            esa.station_assignment_id,
            esa.exam_sitting_room_id,
            esa.station_id,
            esa.status AS station_assignment_status,
            sess.exam_session_id,
            sess.session_status
        FROM delivery.exam_assignment ea
        JOIN delivery.exam_station_assignment esa
          ON esa.exam_assignment_id = ea.exam_assignment_id
        LEFT JOIN LATERAL (
            SELECT exam_session_id, session_status
            FROM delivery.exam_session
            WHERE exam_assignment_id = ea.exam_assignment_id
              AND session_status <> 'VOIDED'
            ORDER BY session_no DESC, exam_session_id DESC
            LIMIT 1
        ) sess ON TRUE
        WHERE esa.exam_sitting_room_id = %s
          AND ea.exam_assignment_id = %s
          AND ea.assignment_status NOT IN ('CANCELLED', 'VOIDED')
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_room_id), int(exam_assignment_id)))
                return cur.fetchone()

    def get_room_assignment_target_by_student_code(self, *, exam_sitting_room_id: int, student_code: str) -> dict | None:
        query = """
        SELECT
            ea.exam_assignment_id,
            ea.exam_sitting_id,
            ea.student_id,
            ea.assignment_status,
            esa.station_assignment_id,
            esa.exam_sitting_room_id,
            esa.station_id,
            esa.status AS station_assignment_status,
            sp.student_code,
            sess.exam_session_id,
            sess.session_status
        FROM delivery.exam_assignment ea
        JOIN delivery.exam_station_assignment esa
          ON esa.exam_assignment_id = ea.exam_assignment_id
        JOIN identity.student_profile sp
          ON sp.student_id = ea.student_id
        LEFT JOIN LATERAL (
            SELECT exam_session_id, session_status
            FROM delivery.exam_session
            WHERE exam_assignment_id = ea.exam_assignment_id
              AND session_status <> 'VOIDED'
            ORDER BY session_no DESC, exam_session_id DESC
            LIMIT 1
        ) sess ON TRUE
        WHERE esa.exam_sitting_room_id = %s
          AND lower(sp.student_code) = lower(%s)
          AND ea.assignment_status NOT IN ('CANCELLED', 'VOIDED')
        ORDER BY esa.station_assignment_id DESC, ea.exam_assignment_id DESC
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_room_id), str(student_code).strip()))
                return cur.fetchone()

    def update_exam_assignment(self, *, exam_assignment_id: int, payload: dict) -> dict | None:
        allowed = {"assignment_status": "assignment_status = %s", "note": "note = %s"}
        updates: list[str] = []
        values: list[object] = []
        for key, clause in allowed.items():
            if key in payload:
                value = payload[key]
                if key == "assignment_status" and value is not None:
                    value = str(value).strip().upper()
                updates.append(clause)
                values.append(value)
        if not updates:
            return self.get_exam_assignment_by_id(int(exam_assignment_id))
        values.append(int(exam_assignment_id))
        query = f"""
        UPDATE delivery.exam_assignment
        SET {", ".join(updates)}
        WHERE exam_assignment_id = %s
        RETURNING exam_assignment_id, exam_sitting_id, student_id, assignment_status, assigned_at, assigned_by, note
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, tuple(values))
                row = cur.fetchone()
            conn.commit()
        return row

    def station_detail(self, station_id: int) -> dict | None:
        query = """
        SELECT station_id, room_id, station_code, status
        FROM facility.lab_station
        WHERE station_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(station_id),))
                return cur.fetchone()

    def device_detail(self, device_id: int) -> dict | None:
        query = """
        SELECT device_id, current_station_id, status
        FROM facility.device
        WHERE device_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(device_id),))
                return cur.fetchone()

    def list_seating_plan(self, exam_sitting_id: int) -> list[dict]:
        query = """
        SELECT
            esa.station_assignment_id,
            esa.exam_assignment_id,
            esa.exam_sitting_room_id,
            esa.station_id,
            esa.planned_device_id,
            esa.status,
            ea.exam_sitting_id,
            ea.student_id,
            sp.student_code,
            p.full_name,
            room.room_code,
            station.station_code,
            device.asset_tag AS planned_device_asset_tag
        FROM delivery.exam_station_assignment esa
        JOIN delivery.exam_assignment ea ON ea.exam_assignment_id = esa.exam_assignment_id
        JOIN delivery.exam_sitting_room esr ON esr.exam_sitting_room_id = esa.exam_sitting_room_id
        JOIN facility.room room ON room.room_id = esr.room_id
        JOIN facility.lab_station station ON station.station_id = esa.station_id
        LEFT JOIN facility.device device ON device.device_id = esa.planned_device_id
        LEFT JOIN identity.student_profile sp ON sp.student_id = ea.student_id
        LEFT JOIN identity.person p ON p.person_id = sp.person_id
        WHERE ea.exam_sitting_id = %s
        ORDER BY room.room_code, station.station_code, esa.station_assignment_id
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_id),))
                return cur.fetchall()

    def create_station_assignment(
        self,
        *,
        exam_assignment_id: int,
        exam_sitting_room_id: int,
        station_id: int,
        planned_device_id: int | None,
        assigned_by: int | None,
        status: str,
    ) -> dict:
        query = """
        INSERT INTO delivery.exam_station_assignment (
            exam_assignment_id, exam_sitting_room_id, station_id, planned_device_id, assigned_by, status
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING station_assignment_id, exam_assignment_id, exam_sitting_room_id, station_id, planned_device_id, assigned_at, assigned_by, status
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(exam_assignment_id),
                        int(exam_sitting_room_id),
                        int(station_id),
                        int(planned_device_id) if planned_device_id is not None else None,
                        assigned_by,
                        str(status).strip().upper(),
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to create delivery.exam_station_assignment")
        return row

    def get_station_assignment_by_id(self, station_assignment_id: int) -> dict | None:
        query = """
        SELECT station_assignment_id, exam_assignment_id, exam_sitting_room_id, station_id, planned_device_id, assigned_at, assigned_by, status
        FROM delivery.exam_station_assignment
        WHERE station_assignment_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(station_assignment_id),))
                return cur.fetchone()

    def update_station_assignment(self, *, station_assignment_id: int, payload: dict) -> dict | None:
        allowed = {
            "exam_sitting_room_id": "exam_sitting_room_id = %s",
            "station_id": "station_id = %s",
            "planned_device_id": "planned_device_id = %s",
            "status": "status = %s",
        }
        updates: list[str] = []
        values: list[object] = []
        for key, clause in allowed.items():
            if key in payload:
                value = payload[key]
                if key == "status" and value is not None:
                    value = str(value).strip().upper()
                updates.append(clause)
                values.append(value)
        if not updates:
            return self.get_station_assignment_by_id(int(station_assignment_id))
        values.append(int(station_assignment_id))
        query = f"""
        UPDATE delivery.exam_station_assignment
        SET {", ".join(updates)}
        WHERE station_assignment_id = %s
        RETURNING station_assignment_id, exam_assignment_id, exam_sitting_room_id, station_id, planned_device_id, assigned_at, assigned_by, status
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, tuple(values))
                row = cur.fetchone()
            conn.commit()
        return row

    def get_sitting_room_for_proctor(self, *, exam_sitting_id: int, proctor_user_id: int) -> list[int]:
        query = """
        SELECT esr.exam_sitting_room_id
        FROM delivery.exam_sitting_room esr
        JOIN delivery.proctor_assignment pa
          ON pa.exam_sitting_room_id = esr.exam_sitting_room_id
        WHERE esr.exam_sitting_id = %s
          AND pa.proctor_user_id = %s
          AND pa.status IN ('ASSIGNED', 'CONFIRMED')
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_id), int(proctor_user_id)))
                rows = cur.fetchall()
        return [int(row["exam_sitting_room_id"]) for row in rows]

    def list_sitting_rooms_for_proctor(self, *, proctor_user_id: int) -> list[dict]:
        query = """
        SELECT DISTINCT
            s.exam_sitting_id,
            s.exam_sitting_room_id,
            s.room_id,
            s.room_code,
            s.room_name,
            s.sitting_code,
            s.sitting_name,
            s.sitting_status,
            s.scheduled_start_at,
            s.scheduled_end_at,
            s.room_status,
            s.capacity_allocated,
            s.assigned_student_count,
            s.assigned_station_count
        FROM delivery.v_exam_sitting_room_summary s
        JOIN delivery.proctor_assignment pa
          ON pa.exam_sitting_room_id = s.exam_sitting_room_id
        WHERE pa.proctor_user_id = %s
          AND pa.status IN ('ASSIGNED', 'CONFIRMED')
        ORDER BY s.scheduled_start_at DESC, s.exam_sitting_room_id DESC
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(proctor_user_id),))
                return cur.fetchall()

    def list_all_sitting_rooms_summary(self) -> list[dict]:
        query = """
        SELECT
            exam_sitting_id,
            exam_sitting_room_id,
            room_id,
            room_code,
            room_name,
            sitting_code,
            sitting_name,
            sitting_status,
            scheduled_start_at,
            scheduled_end_at,
            room_status,
            capacity_allocated,
            assigned_student_count,
            assigned_station_count
        FROM delivery.v_exam_sitting_room_summary
        ORDER BY scheduled_start_at DESC, exam_sitting_room_id DESC
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query)
                return cur.fetchall()

    def get_exam_sitting_room_summary_by_id(self, *, exam_sitting_room_id: int) -> dict | None:
        query = """
        SELECT
            exam_sitting_id,
            exam_sitting_room_id,
            room_id,
            room_code,
            room_name,
            sitting_code,
            sitting_name,
            sitting_status,
            scheduled_start_at,
            scheduled_end_at,
            room_status,
            capacity_allocated,
            assigned_student_count,
            assigned_station_count
        FROM delivery.v_exam_sitting_room_summary
        WHERE exam_sitting_room_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_room_id),))
                return cur.fetchone()

    def get_room_lifecycle_state(self, *, exam_sitting_room_id: int) -> dict | None:
        query = """
        SELECT
            esr.exam_sitting_room_id,
            esr.exam_sitting_id,
            esr.room_id,
            room.room_code,
            esr.room_status,
            esr.capacity_allocated,
            esr.closed_at,
            esr.closed_by,
            esr.close_reason,
            esr.close_note,
            esr.close_summary_json,
            esr.updated_at,
            esr.updated_by
        FROM delivery.exam_sitting_room esr
        LEFT JOIN facility.room room
          ON room.room_id = esr.room_id
        WHERE esr.exam_sitting_room_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_room_id),))
                return cur.fetchone()

    def get_session_heartbeat_seconds(self) -> int:
        query = "SELECT session_heartbeat_seconds FROM ops.system_settings LIMIT 1"
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query)
                row = cur.fetchone()
        if row is None or row.get("session_heartbeat_seconds") is None:
            return 30
        return max(1, int(row["session_heartbeat_seconds"]))

    def list_proctor_room_roster(self, *, exam_sitting_room_id: int, include_photo: bool) -> list[dict]:
        photo_select = "r.photo_ref" if include_photo else "NULL::text AS photo_ref"
        query = f"""
        SELECT
            r.exam_sitting_id,
            r.exam_sitting_room_id,
            r.room_code,
            r.exam_assignment_id,
            r.station_id,
            r.station_code,
            r.student_id,
            r.student_code,
            r.full_name,
            {photo_select},
            r.assignment_status,
            r.station_assignment_status,
            esa.planned_device_id,
            d.asset_tag AS planned_device_asset_tag,
            rsr.last_checkin_at,
            rsr.last_health_status AS latest_health_status,
            sess.exam_session_id,
            sess.session_code,
            sess.session_status,
            sess.started_at,
            sess.ended_at,
            sess.last_seen_at,
            sub.exam_submission_id,
            sub.submission_status,
            sub.submitted_at,
            sub.sealed_at
        FROM delivery.v_proctor_room_roster r
        JOIN delivery.exam_station_assignment esa
          ON esa.exam_assignment_id = r.exam_assignment_id
         AND esa.exam_sitting_room_id = r.exam_sitting_room_id
         AND esa.station_id = r.station_id
        LEFT JOIN facility.device d
          ON d.device_id = esa.planned_device_id
        LEFT JOIN delivery.v_room_station_readiness rsr
          ON rsr.station_id = r.station_id
        LEFT JOIN LATERAL (
            SELECT
                exam_session_id,
                session_code,
                session_status,
                started_at,
                ended_at,
                last_seen_at
            FROM delivery.exam_session
            WHERE exam_assignment_id = r.exam_assignment_id
              AND session_status <> 'VOIDED'
            ORDER BY session_no DESC, exam_session_id DESC
            LIMIT 1
        ) sess ON TRUE
        LEFT JOIN LATERAL (
            SELECT
                exam_submission_id,
                submission_status,
                submitted_at,
                sealed_at
            FROM submission.exam_submission
            WHERE exam_session_id = sess.exam_session_id
            ORDER BY exam_submission_id DESC
            LIMIT 1
        ) sub ON TRUE
        WHERE r.exam_sitting_room_id = %s
        ORDER BY r.station_code ASC, r.student_code ASC
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_room_id),))
                return cur.fetchall()

    def _fetch_proctor_room_attendance(
        self,
        *,
        exam_sitting_room_id: int,
        exam_assignment_id: int | None = None,
    ) -> list[dict]:
        query = """
        SELECT
            esr.exam_sitting_id,
            esr.exam_sitting_room_id,
            room.room_code,
            ea.exam_assignment_id,
            esa.station_assignment_id,
            esa.station_id,
            station.station_code,
            ea.student_id,
            sp.student_code,
            p.full_name,
            cp.photo_ref,
            ea.assignment_status,
            esa.status AS station_assignment_status,
            latest_ver.verification_status AS latest_verification_status,
            latest_ver.verification_method AS latest_verification_method,
            latest_ver.verified_at AS latest_verified_at,
            latest_ver.verified_by AS latest_verified_by,
            checked_in.changed_at AS checked_in_at,
            checked_in.actor_user_id AS checked_in_by,
            latest_hist.note AS latest_attendance_note,
            sess.exam_session_id,
            sess.session_status,
            sub.submission_status,
            sess.last_seen_at
        FROM delivery.exam_station_assignment esa
        JOIN delivery.exam_assignment ea
          ON ea.exam_assignment_id = esa.exam_assignment_id
        JOIN delivery.exam_sitting_room esr
          ON esr.exam_sitting_room_id = esa.exam_sitting_room_id
        JOIN facility.room room
          ON room.room_id = esr.room_id
        LEFT JOIN facility.lab_station station
          ON station.station_id = esa.station_id
        LEFT JOIN identity.student_profile sp
          ON sp.student_id = ea.student_id
        LEFT JOIN identity.person p
          ON p.person_id = sp.person_id
        LEFT JOIN LATERAL (
            SELECT pp.photo_ref
            FROM identity.person_photo pp
            WHERE pp.person_id = p.person_id
              AND pp.is_current = true
              AND pp.valid_to IS NULL
            ORDER BY pp.valid_from DESC, pp.person_photo_id DESC
            LIMIT 1
        ) cp ON TRUE
        LEFT JOIN LATERAL (
            SELECT
                cv.verification_status,
                cv.verification_method,
                cv.verified_at,
                cv.verified_by
            FROM delivery.exam_checkin_verification cv
            WHERE cv.exam_assignment_id = ea.exam_assignment_id
            ORDER BY cv.verified_at DESC, cv.checkin_verification_id DESC
            LIMIT 1
        ) latest_ver ON TRUE
        LEFT JOIN LATERAL (
            SELECT
                ah.changed_at,
                ah.actor_user_id
            FROM delivery.exam_assignment_attendance_history ah
            WHERE ah.exam_assignment_id = ea.exam_assignment_id
              AND ah.new_assignment_status = 'CHECKED_IN'
            ORDER BY ah.changed_at DESC, ah.attendance_history_id DESC
            LIMIT 1
        ) checked_in ON TRUE
        LEFT JOIN LATERAL (
            SELECT ah.note
            FROM delivery.exam_assignment_attendance_history ah
            WHERE ah.exam_assignment_id = ea.exam_assignment_id
            ORDER BY ah.changed_at DESC, ah.attendance_history_id DESC
            LIMIT 1
        ) latest_hist ON TRUE
        LEFT JOIN LATERAL (
            SELECT exam_session_id, session_status, last_seen_at
            FROM delivery.exam_session
            WHERE exam_assignment_id = ea.exam_assignment_id
              AND session_status <> 'VOIDED'
            ORDER BY session_no DESC, exam_session_id DESC
            LIMIT 1
        ) sess ON TRUE
        LEFT JOIN LATERAL (
            SELECT submission_status
                 , exam_submission_id
            FROM submission.exam_submission
            WHERE exam_session_id = sess.exam_session_id
            ORDER BY exam_submission_id DESC
            LIMIT 1
        ) sub ON TRUE
        WHERE esa.exam_sitting_room_id = %s
          AND ea.assignment_status NOT IN ('CANCELLED', 'VOIDED')
          AND (%s::bigint IS NULL OR ea.exam_assignment_id = %s)
        ORDER BY station.station_code ASC NULLS LAST, sp.student_code ASC NULLS LAST, ea.exam_assignment_id ASC
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(exam_sitting_room_id),
                        int(exam_assignment_id) if exam_assignment_id is not None else None,
                        int(exam_assignment_id) if exam_assignment_id is not None else None,
                    ),
                )
                return cur.fetchall()

    def list_proctor_room_attendance(self, *, exam_sitting_room_id: int) -> list[dict]:
        return self._fetch_proctor_room_attendance(exam_sitting_room_id=int(exam_sitting_room_id))

    def list_proctor_room_submission_monitor(self, *, exam_sitting_room_id: int) -> list[dict]:
        return self._fetch_proctor_room_attendance(exam_sitting_room_id=int(exam_sitting_room_id))

    def get_room_close_preflight_snapshot(self, *, exam_sitting_room_id: int) -> list[dict]:
        return self._fetch_proctor_room_attendance(exam_sitting_room_id=int(exam_sitting_room_id))

    def get_room_submission_preflight_snapshot(self, *, exam_sitting_room_id: int) -> list[dict]:
        return self._fetch_proctor_room_attendance(exam_sitting_room_id=int(exam_sitting_room_id))

    def _get_room_close_counts_with_cursor(self, *, cur, exam_sitting_room_id: int, heartbeat_seconds: int) -> dict:
        stale_cutoff = datetime.now(timezone.utc) - timedelta(seconds=max(1, int(heartbeat_seconds)) * 3)
        query = """
        WITH room_snapshot AS (
            SELECT
                ea.exam_assignment_id,
                ea.assignment_status,
                sess.exam_session_id,
                sess.session_status,
                sess.last_seen_at,
                sub.submission_status
            FROM delivery.exam_station_assignment esa
            JOIN delivery.exam_assignment ea
              ON ea.exam_assignment_id = esa.exam_assignment_id
            LEFT JOIN LATERAL (
                SELECT
                    es.exam_session_id,
                    es.session_status,
                    es.last_seen_at
                FROM delivery.exam_session es
                WHERE es.exam_assignment_id = ea.exam_assignment_id
                  AND es.session_status <> 'VOIDED'
                ORDER BY es.session_no DESC, es.exam_session_id DESC
                LIMIT 1
            ) sess ON TRUE
            LEFT JOIN LATERAL (
                SELECT sub.submission_status
                FROM submission.exam_submission sub
                WHERE sub.exam_session_id = sess.exam_session_id
                ORDER BY sub.exam_submission_id DESC
                LIMIT 1
            ) sub ON TRUE
            WHERE esa.exam_sitting_room_id = %s
              AND ea.assignment_status NOT IN ('CANCELLED', 'VOIDED')
        ),
        incident_snapshot AS (
            SELECT incident_status
            FROM delivery.exam_session_incident
            WHERE exam_sitting_room_id = %s
        )
        SELECT
            COALESCE((SELECT count(*)::bigint FROM room_snapshot), 0) AS total_assignments,
            COALESCE((SELECT count(*)::bigint FROM room_snapshot WHERE assignment_status = 'CHECKED_IN'), 0) AS checked_in_count,
            COALESCE((SELECT count(*)::bigint FROM room_snapshot WHERE assignment_status = 'ABSENT'), 0) AS absent_count,
            COALESCE((SELECT count(*)::bigint FROM room_snapshot WHERE assignment_status NOT IN ('CHECKED_IN', 'ABSENT', 'COMPLETED', 'RESCHEDULED', 'CANCELLED', 'VOIDED')), 0) AS pending_attendance_count,
            COALESCE((SELECT count(*)::bigint FROM incident_snapshot WHERE incident_status = 'OPEN'), 0) AS open_incident_count,
            COALESCE((SELECT count(*)::bigint FROM incident_snapshot WHERE incident_status = 'IN_PROGRESS'), 0) AS in_progress_incident_count,
            COALESCE((SELECT count(*)::bigint FROM room_snapshot WHERE session_status IN ('READY_TO_START', 'IN_PROGRESS', 'PAUSED')), 0) AS active_session_count,
            COALESCE((SELECT count(*)::bigint FROM room_snapshot WHERE session_status = 'INTERRUPTED'), 0) AS interrupted_session_count,
            COALESCE((
                SELECT count(*)::bigint
                FROM room_snapshot
                WHERE assignment_status <> 'ABSENT'
                  AND session_status IN ('IN_PROGRESS', 'PAUSED', 'INTERRUPTED', 'ENDED', 'EXPIRED', 'SUBMITTED', 'FORCE_CLOSED')
                  AND COALESCE(submission_status, '') NOT IN ('SUBMITTED', 'AUTO_SUBMITTED', 'FORCE_SEALED', 'EXPIRED_SEALED', 'VOIDED')
            ), 0) AS pending_submission_count,
            COALESCE((
                SELECT count(*)::bigint
                FROM room_snapshot
                WHERE session_status IN ('READY_TO_START', 'IN_PROGRESS', 'PAUSED')
                  AND last_seen_at IS NOT NULL
                  AND last_seen_at < %s
            ), 0) AS stale_heartbeat_count
        """
        cur.execute(query, (int(exam_sitting_room_id), int(exam_sitting_room_id), stale_cutoff))
        row = cur.fetchone()
        if row is None:
            return {
                "total_assignments": 0,
                "checked_in_count": 0,
                "absent_count": 0,
                "pending_attendance_count": 0,
                "open_incident_count": 0,
                "in_progress_incident_count": 0,
                "active_session_count": 0,
                "interrupted_session_count": 0,
                "pending_submission_count": 0,
                "stale_heartbeat_count": 0,
            }
        return {key: int(row.get(key) or 0) for key in row.keys()}

    def get_room_close_counts(self, *, exam_sitting_room_id: int, heartbeat_seconds: int) -> dict:
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                return self._get_room_close_counts_with_cursor(
                    cur=cur,
                    exam_sitting_room_id=int(exam_sitting_room_id),
                    heartbeat_seconds=int(heartbeat_seconds),
                )

    def get_room_assignment_attendance_item(self, *, exam_sitting_room_id: int, exam_assignment_id: int) -> dict | None:
        rows = self._fetch_proctor_room_attendance(
            exam_sitting_room_id=int(exam_sitting_room_id),
            exam_assignment_id=int(exam_assignment_id),
        )
        return rows[0] if rows else None

    def _insert_assignment_attendance_history_row(self, *, cur, payload: dict) -> dict | None:
        query = """
        INSERT INTO delivery.exam_assignment_attendance_history (
            exam_assignment_id,
            exam_sitting_room_id,
            station_assignment_id,
            previous_assignment_status,
            new_assignment_status,
            previous_station_status,
            new_station_status,
            actor_user_id,
            actor_role,
            action_type,
            note,
            context_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING
            attendance_history_id,
            exam_assignment_id,
            exam_sitting_room_id,
            station_assignment_id,
            previous_assignment_status,
            new_assignment_status,
            previous_station_status,
            new_station_status,
            actor_user_id,
            actor_role,
            action_type,
            note,
            changed_at,
            context_json
        """
        cur.execute(
            query,
            (
                int(payload["exam_assignment_id"]),
                int(payload["exam_sitting_room_id"]),
                int(payload["station_assignment_id"]) if payload.get("station_assignment_id") is not None else None,
                str(payload["previous_assignment_status"]).strip().upper() if payload.get("previous_assignment_status") is not None else None,
                str(payload["new_assignment_status"]).strip().upper(),
                str(payload["previous_station_status"]).strip().upper() if payload.get("previous_station_status") is not None else None,
                str(payload["new_station_status"]).strip().upper() if payload.get("new_station_status") is not None else None,
                int(payload["actor_user_id"]) if payload.get("actor_user_id") is not None else None,
                str(payload.get("actor_role") or "UNKNOWN"),
                str(payload.get("action_type") or "ATTENDANCE_UPDATED"),
                payload.get("note"),
                Jsonb(payload.get("context_json")) if payload.get("context_json") is not None else None,
            ),
        )
        return cur.fetchone()

    def update_assignment_attendance_with_history(
        self,
        *,
        exam_assignment_id: int,
        exam_sitting_room_id: int,
        station_assignment_id: int | None,
        previous_assignment_status: str | None,
        new_assignment_status: str,
        previous_station_status: str | None,
        new_station_status: str | None,
        actor_user_id: int | None,
        actor_role: str,
        action_type: str,
        note: str | None,
        context_json: dict | None,
    ) -> dict | None:
        assignment_query = """
        UPDATE delivery.exam_assignment
        SET assignment_status = %s
        WHERE exam_assignment_id = %s
        RETURNING exam_assignment_id
        """
        station_query = """
        UPDATE delivery.exam_station_assignment
        SET status = %s
        WHERE station_assignment_id = %s
        RETURNING station_assignment_id
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    assignment_query,
                    (
                        str(new_assignment_status).strip().upper(),
                        int(exam_assignment_id),
                    ),
                )
                assignment_row = cur.fetchone()
                if assignment_row is None:
                    conn.rollback()
                    return None
                if station_assignment_id is not None and new_station_status is not None:
                    cur.execute(
                        station_query,
                        (
                            str(new_station_status).strip().upper(),
                            int(station_assignment_id),
                        ),
                    )
                    station_row = cur.fetchone()
                    if station_row is None:
                        conn.rollback()
                        return None
                self._insert_assignment_attendance_history_row(
                    cur=cur,
                    payload={
                        "exam_assignment_id": int(exam_assignment_id),
                        "exam_sitting_room_id": int(exam_sitting_room_id),
                        "station_assignment_id": int(station_assignment_id) if station_assignment_id is not None else None,
                        "previous_assignment_status": previous_assignment_status,
                        "new_assignment_status": new_assignment_status,
                        "previous_station_status": previous_station_status,
                        "new_station_status": new_station_status,
                        "actor_user_id": int(actor_user_id) if actor_user_id is not None else None,
                        "actor_role": actor_role,
                        "action_type": action_type,
                        "note": note,
                        "context_json": context_json,
                    },
                )
            conn.commit()
        return self.get_room_assignment_attendance_item(
            exam_sitting_room_id=int(exam_sitting_room_id),
            exam_assignment_id=int(exam_assignment_id),
        )

    def insert_checkin_verification(
        self,
        *,
        exam_assignment_id: int,
        exam_session_id: int | None,
        station_assignment_id: int | None,
        verified_by: int,
        verification_status: str,
        verification_method: str,
        note: str | None,
        metadata_json: dict | None,
    ) -> dict:
        query = """
        INSERT INTO delivery.exam_checkin_verification (
            exam_assignment_id,
            exam_session_id,
            station_assignment_id,
            verified_by,
            verification_status,
            verification_method,
            note,
            metadata_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING
            checkin_verification_id,
            exam_assignment_id,
            exam_session_id,
            station_assignment_id,
            verified_by,
            verified_at,
            verification_status,
            verification_method,
            note,
            metadata_json
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(exam_assignment_id),
                        int(exam_session_id) if exam_session_id is not None else None,
                        int(station_assignment_id) if station_assignment_id is not None else None,
                        int(verified_by),
                        str(verification_status).strip().upper(),
                        str(verification_method).strip().upper(),
                        note,
                        Jsonb(metadata_json) if metadata_json is not None else None,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to insert delivery.exam_checkin_verification")
        return row

    def get_latest_assignment_verification_summary(self, *, exam_assignment_id: int) -> dict | None:
        query = """
        SELECT
            verification_status AS latest_verification_status,
            verification_method AS latest_verification_method,
            verified_at AS latest_verified_at,
            verified_by AS latest_verified_by
        FROM delivery.exam_checkin_verification
        WHERE exam_assignment_id = %s
        ORDER BY verified_at DESC, checkin_verification_id DESC
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_assignment_id),))
                return cur.fetchone()

    def list_room_readiness(self, *, room_id: int) -> list[dict]:
        query = """
        SELECT
            rsr.room_id,
            rsr.room_code,
            rsr.station_id,
            rsr.station_code,
            rsr.device_id,
            rsr.asset_tag,
            rsr.last_checkin_at,
            rsr.last_health_status,
            d.current_station_id
        FROM delivery.v_room_station_readiness rsr
        LEFT JOIN facility.device d ON d.device_id = rsr.device_id
        WHERE rsr.room_id = %s
        ORDER BY rsr.station_code ASC
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(room_id),))
                return cur.fetchall()

    def create_exam_session_incident(
        self,
        *,
        exam_sitting_id: int,
        exam_sitting_room_id: int | None,
        exam_assignment_id: int | None,
        station_id: int | None,
        device_id: int | None,
        incident_type: str,
        incident_status: str,
        description: str | None,
        metadata_json: dict | None,
        reported_by: int | None,
    ) -> dict:
        query = """
        INSERT INTO delivery.exam_session_incident (
            exam_sitting_id,
            exam_sitting_room_id,
            exam_assignment_id,
            station_id,
            device_id,
            incident_type,
            incident_status,
            reported_by,
            description,
            metadata_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING
            incident_id,
            exam_sitting_id,
            exam_sitting_room_id,
            exam_assignment_id,
            exam_session_id,
            station_id,
            device_id,
            incident_type,
            incident_status,
            reported_by,
            reported_at,
            resolved_by,
            resolved_at,
            description,
            metadata_json,
            updated_by,
            updated_at,
            resolution_note
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(exam_sitting_id),
                        int(exam_sitting_room_id) if exam_sitting_room_id is not None else None,
                        int(exam_assignment_id) if exam_assignment_id is not None else None,
                        int(station_id) if station_id is not None else None,
                        int(device_id) if device_id is not None else None,
                        str(incident_type).strip().upper(),
                        str(incident_status).strip().upper(),
                        int(reported_by) if reported_by is not None else None,
                        description,
                        Jsonb(metadata_json or {}),
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to create delivery.exam_session_incident")
        return row

    def get_incident_by_id(self, *, incident_id: int) -> dict | None:
        query = """
         SELECT
             incident_id, exam_sitting_id, exam_sitting_room_id, exam_assignment_id, exam_session_id, station_id, device_id,
             incident_type, incident_status, reported_by, reported_at, resolved_by, resolved_at, description, metadata_json,
             updated_by, updated_at, resolution_note
        FROM delivery.exam_session_incident
        WHERE incident_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(incident_id),))
                return cur.fetchone()

    def update_incident(
        self,
        *,
        incident_id: int,
        payload: dict,
    ) -> dict | None:
        allowed = {
            "incident_status": "incident_status = %s",
            "description": "description = %s",
            "metadata_json": "metadata_json = %s",
            "resolved_by": "resolved_by = %s",
            "resolved_at": "resolved_at = %s",
            "updated_by": "updated_by = %s",
            "updated_at": "updated_at = %s",
            "resolution_note": "resolution_note = %s",
        }
        updates: list[str] = []
        values: list[object] = []
        for key, clause in allowed.items():
            if key in payload:
                updates.append(clause)
                value = payload[key]
                if key == "incident_status" and value is not None:
                    value = str(value).strip().upper()
                if key == "metadata_json":
                    value = Jsonb(value or {})
                values.append(value)
        if not updates:
            return self.get_incident_by_id(incident_id=incident_id)
        values.append(int(incident_id))
        query = f"""
        UPDATE delivery.exam_session_incident
        SET {", ".join(updates)}
        WHERE incident_id = %s
        RETURNING
            incident_id,
            exam_sitting_id,
            exam_sitting_room_id,
            exam_assignment_id,
            exam_session_id,
            station_id,
            device_id,
            incident_type,
            incident_status,
            reported_by,
            reported_at,
            resolved_by,
            resolved_at,
            description,
            metadata_json,
            updated_by,
            updated_at,
            resolution_note
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, tuple(values))
                row = cur.fetchone()
            conn.commit()
        return row

    def insert_incident_history(self, *, payload: dict) -> dict:
        query = """
        INSERT INTO delivery.exam_session_incident_history (
            incident_id,
            actor_user_id,
            actor_role,
            action_type,
            from_status,
            to_status,
            description_before,
            description_after,
            resolution_note,
            metadata_before,
            metadata_after,
            context_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING
            incident_history_id,
            incident_id,
            actor_user_id,
            actor_role,
            action_type,
            from_status,
            to_status,
            description_before,
            description_after,
            resolution_note,
            metadata_before,
            metadata_after,
            changed_at,
            context_json
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                row = self._insert_incident_history_row(cur=cur, payload=payload)
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to insert delivery.exam_session_incident_history")
        return row

    def _insert_incident_history_row(self, *, cur, payload: dict) -> dict | None:
        query = """
        INSERT INTO delivery.exam_session_incident_history (
            incident_id,
            actor_user_id,
            actor_role,
            action_type,
            from_status,
            to_status,
            description_before,
            description_after,
            resolution_note,
            metadata_before,
            metadata_after,
            context_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING
            incident_history_id,
            incident_id,
            actor_user_id,
            actor_role,
            action_type,
            from_status,
            to_status,
            description_before,
            description_after,
            resolution_note,
            metadata_before,
            metadata_after,
            changed_at,
            context_json
        """
        cur.execute(
            query,
            (
                int(payload["incident_id"]),
                int(payload["actor_user_id"]) if payload.get("actor_user_id") is not None else None,
                str(payload.get("actor_role") or "UNKNOWN"),
                str(payload.get("action_type") or "INCIDENT_UPDATED"),
                str(payload["from_status"]).strip().upper() if payload.get("from_status") is not None else None,
                str(payload["to_status"]).strip().upper() if payload.get("to_status") is not None else None,
                payload.get("description_before"),
                payload.get("description_after"),
                payload.get("resolution_note"),
                Jsonb(payload.get("metadata_before")) if payload.get("metadata_before") is not None else None,
                Jsonb(payload.get("metadata_after")) if payload.get("metadata_after") is not None else None,
                Jsonb(payload.get("context_json")) if payload.get("context_json") is not None else None,
            ),
        )
        return cur.fetchone()

    def update_incident_with_history(self, *, incident_id: int, payload: dict, history_payload: dict) -> dict | None:
        allowed = {
            "incident_status": "incident_status = %s",
            "description": "description = %s",
            "metadata_json": "metadata_json = %s",
            "resolved_by": "resolved_by = %s",
            "resolved_at": "resolved_at = %s",
            "updated_by": "updated_by = %s",
            "updated_at": "updated_at = %s",
            "resolution_note": "resolution_note = %s",
        }
        updates: list[str] = []
        values: list[object] = []
        for key, clause in allowed.items():
            if key in payload:
                updates.append(clause)
                value = payload[key]
                if key == "incident_status" and value is not None:
                    value = str(value).strip().upper()
                if key == "metadata_json":
                    value = Jsonb(value)
                values.append(value)
        if not updates:
            return self.get_incident_by_id(incident_id=incident_id)

        values.append(int(incident_id))
        query = f"""
        UPDATE delivery.exam_session_incident
        SET {", ".join(updates)}
        WHERE incident_id = %s
        RETURNING
            incident_id,
            exam_sitting_id,
            exam_sitting_room_id,
            exam_assignment_id,
            exam_session_id,
            station_id,
            device_id,
            incident_type,
            incident_status,
            reported_by,
            reported_at,
            resolved_by,
            resolved_at,
            description,
            metadata_json,
            updated_by,
            updated_at,
            resolution_note
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, tuple(values))
                row = cur.fetchone()
                if row is None:
                    conn.rollback()
                    return None
                self._insert_incident_history_row(
                    cur=cur,
                    payload={
                        **history_payload,
                        "incident_id": int(incident_id),
                    },
                )
            conn.commit()
        return row

    def list_incident_history(self, *, incident_id: int) -> list[dict]:
        query = """
        SELECT
            incident_history_id,
            incident_id,
            actor_user_id,
            actor_role,
            action_type,
            from_status,
            to_status,
            description_before,
            description_after,
            resolution_note,
            metadata_before,
            metadata_after,
            changed_at,
            context_json
        FROM delivery.exam_session_incident_history
        WHERE incident_id = %s
        ORDER BY changed_at DESC, incident_history_id DESC
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(incident_id),))
                return cur.fetchall()

    def list_incidents_by_sitting(self, *, exam_sitting_id: int) -> list[dict]:
        query = """
         SELECT incident_id, exam_sitting_id, exam_sitting_room_id, exam_assignment_id, exam_session_id, station_id, device_id,
             incident_type, incident_status, reported_by, reported_at, resolved_by, resolved_at, description, metadata_json,
             updated_by, updated_at, resolution_note
        FROM delivery.exam_session_incident
        WHERE exam_sitting_id = %s
        ORDER BY reported_at DESC, incident_id DESC
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_id),))
                return cur.fetchall()

    def list_incidents_for_sitting_room(
        self,
        *,
        exam_sitting_room_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        query = """
         SELECT incident_id, exam_sitting_id, exam_sitting_room_id, exam_assignment_id, exam_session_id, station_id, device_id,
             incident_type, incident_status, reported_by, reported_at, resolved_by, resolved_at, description, metadata_json,
             updated_by, updated_at, resolution_note
        FROM delivery.exam_session_incident
        WHERE exam_sitting_room_id = %s
        ORDER BY reported_at DESC, incident_id DESC
        LIMIT %s OFFSET %s
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_room_id), int(limit), int(offset)))
                return cur.fetchall()

    def get_station_assignment_by_exam_assignment(self, *, exam_assignment_id: int) -> dict | None:
        query = """
        SELECT station_assignment_id, exam_assignment_id, exam_sitting_room_id, station_id, planned_device_id, assigned_at, assigned_by, status
        FROM delivery.exam_station_assignment
        WHERE exam_assignment_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_assignment_id),))
                return cur.fetchone()

    def get_sitting_room_by_sitting_and_room(self, *, exam_sitting_id: int, room_id: int) -> dict | None:
        query = """
        SELECT
            exam_sitting_room_id,
            exam_sitting_id,
            room_id,
            capacity_allocated,
            room_status,
            closed_at,
            closed_by,
            close_reason,
            close_note,
            close_summary_json,
            updated_at,
            updated_by,
            created_at
        FROM delivery.exam_sitting_room
        WHERE exam_sitting_id = %s AND room_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_id), int(room_id)))
                return cur.fetchone()

    def is_station_occupied_in_sitting_room(
        self,
        *,
        exam_sitting_room_id: int,
        station_id: int,
        exclude_exam_assignment_id: int | None = None,
    ) -> bool:
        query = """
        SELECT 1
        FROM delivery.exam_station_assignment
        WHERE exam_sitting_room_id = %s
          AND station_id = %s
          AND status IN ('ASSIGNED', 'CHECKED_IN')
          AND (%s::bigint IS NULL OR exam_assignment_id <> %s)
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(exam_sitting_room_id),
                        int(station_id),
                        int(exclude_exam_assignment_id) if exclude_exam_assignment_id is not None else None,
                        int(exclude_exam_assignment_id) if exclude_exam_assignment_id is not None else None,
                    ),
                )
                row = cur.fetchone()
        return row is not None

    def create_station_transfer(
        self,
        *,
        exam_sitting_id: int,
        exam_assignment_id: int,
        exam_session_id: int | None,
        from_station_id: int,
        to_station_id: int,
        from_device_id: int | None,
        to_device_id: int | None,
        reason_code: str,
        approved_by: int,
        time_adjustment_seconds: int,
        note: str | None,
    ) -> dict:
        query = """
        INSERT INTO delivery.exam_session_transfer (
            exam_sitting_id,
            exam_assignment_id,
            exam_session_id,
            from_station_id,
            to_station_id,
            from_device_id,
            to_device_id,
            reason_code,
            approved_by,
            time_adjustment_seconds,
            note
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING session_transfer_id, exam_sitting_id, exam_assignment_id, exam_session_id,
                  from_station_id, to_station_id, from_device_id, to_device_id, reason_code, approved_by,
                  approved_at, time_adjustment_seconds, note
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(exam_sitting_id),
                        int(exam_assignment_id),
                        int(exam_session_id) if exam_session_id is not None else None,
                        int(from_station_id),
                        int(to_station_id),
                        int(from_device_id) if from_device_id is not None else None,
                        int(to_device_id) if to_device_id is not None else None,
                        str(reason_code).strip().upper(),
                        int(approved_by),
                        int(time_adjustment_seconds),
                        note,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to create delivery.exam_session_transfer")
        return row

    def create_reschedule(
        self,
        *,
        original_exam_assignment_id: int,
        new_exam_assignment_id: int | None,
        reason_code: str,
        approved_by: int,
        policy_code: str | None,
        note: str | None,
        status: str,
    ) -> dict:
        query = """
        INSERT INTO delivery.exam_reschedule (
            original_exam_assignment_id,
            new_exam_assignment_id,
            reason_code,
            approved_by,
            policy_code,
            note,
            status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING reschedule_id, original_exam_assignment_id, new_exam_assignment_id, original_exam_session_id,
                  reason_code, approved_by, approved_at, policy_code, note, status
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(original_exam_assignment_id),
                        int(new_exam_assignment_id) if new_exam_assignment_id is not None else None,
                        str(reason_code).strip().upper(),
                        int(approved_by),
                        str(policy_code).strip().upper() if policy_code is not None else None,
                        note,
                        str(status).strip().upper(),
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to create delivery.exam_reschedule")
        return row

    def get_reschedule_by_id(self, *, reschedule_id: int) -> dict | None:
        query = """
        SELECT reschedule_id, original_exam_assignment_id, new_exam_assignment_id, original_exam_session_id,
               reason_code, approved_by, approved_at, policy_code, note, status
        FROM delivery.exam_reschedule
        WHERE reschedule_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(reschedule_id),))
                return cur.fetchone()

    def update_reschedule(self, *, reschedule_id: int, payload: dict) -> dict | None:
        allowed = {
            "new_exam_assignment_id": "new_exam_assignment_id = %s",
            "policy_code": "policy_code = %s",
            "note": "note = %s",
            "status": "status = %s",
            "approved_by": "approved_by = %s",
            "approved_at": "approved_at = %s",
        }
        updates: list[str] = []
        values: list[object] = []
        for key, clause in allowed.items():
            if key not in payload:
                continue
            value = payload[key]
            if key in {"policy_code", "status"} and value is not None:
                value = str(value).strip().upper()
            updates.append(clause)
            values.append(value)
        if not updates:
            return self.get_reschedule_by_id(reschedule_id=reschedule_id)
        values.append(int(reschedule_id))
        query = f"""
        UPDATE delivery.exam_reschedule
        SET {", ".join(updates)}
        WHERE reschedule_id = %s
        RETURNING reschedule_id, original_exam_assignment_id, new_exam_assignment_id, original_exam_session_id,
                  reason_code, approved_by, approved_at, policy_code, note, status
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, tuple(values))
                row = cur.fetchone()
            conn.commit()
        return row

    def has_proctor_assignment_access(
        self,
        *,
        exam_sitting_id: int,
        exam_assignment_id: int,
        proctor_user_id: int,
    ) -> bool:
        query = """
        SELECT 1
        FROM delivery.exam_assignment ea
        JOIN delivery.exam_station_assignment esa
          ON esa.exam_assignment_id = ea.exam_assignment_id
        JOIN delivery.proctor_assignment pa
          ON pa.exam_sitting_room_id = esa.exam_sitting_room_id
        WHERE ea.exam_sitting_id = %s
          AND ea.exam_assignment_id = %s
          AND pa.proctor_user_id = %s
          AND pa.status IN ('ASSIGNED', 'CONFIRMED')
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (int(exam_sitting_id), int(exam_assignment_id), int(proctor_user_id)),
                )
                row = cur.fetchone()
        return row is not None

    def get_student_candidate_profile(self, student_id: int) -> dict | None:
        query = """
        SELECT
            sp.student_id,
            sp.student_code,
            p.full_name,
            cp.photo_ref
        FROM identity.student_profile sp
        JOIN identity.person p
            ON p.person_id = sp.person_id
        LEFT JOIN LATERAL (
            SELECT pp.photo_ref
            FROM identity.person_photo pp
            WHERE pp.person_id = p.person_id
              AND pp.is_current = true
              AND pp.valid_to IS NULL
            ORDER BY pp.valid_from DESC, pp.person_photo_id DESC
            LIMIT 1
        ) cp
            ON true
        WHERE sp.student_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(student_id),))
                return cur.fetchone()

    def list_class_sections_for_sitting(self, exam_sitting_id: int, conn: Connection | object | None = None) -> list[dict]:
        query = """
        SELECT
            esc.exam_sitting_class_section_id,
            esc.exam_sitting_id,
            esc.class_section_id,
            esc.status,
            esc.created_by,
            esc.created_at,
            esc.updated_at,
            cs.class_code,
            cs.class_name
        FROM delivery.exam_sitting_class_section esc
        JOIN academic.class_section cs
          ON cs.class_section_id = esc.class_section_id
        WHERE esc.exam_sitting_id = %s
          AND esc.status = 'ACTIVE'
        ORDER BY cs.class_code ASC
        """
        if conn is not None:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_id),))
                return cur.fetchall()
        with open_connection() as conn_new:
            with conn_new.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_id),))
                return cur.fetchall()

    def class_section_exists(self, class_section_id: int, conn: Connection | object | None = None) -> bool:
        query = """
        SELECT 1
        FROM academic.class_section
        WHERE class_section_id = %s
        LIMIT 1
        """
        if conn is not None:
            with conn.cursor() as cur:
                cur.execute(query, (int(class_section_id),))
                return cur.fetchone() is not None
        with open_connection() as conn_new:
            with conn_new.cursor() as cur:
                cur.execute(query, (int(class_section_id),))
                return cur.fetchone() is not None

    def add_class_sections_to_sitting(
        self,
        *,
        exam_sitting_id: int,
        class_section_ids: list[int],
        created_by: int,
        conn: Connection | object | None = None,
    ) -> None:
        query = """
        INSERT INTO delivery.exam_sitting_class_section (
            exam_sitting_id,
            class_section_id,
            status,
            created_by,
            created_at
        )
        VALUES (%s, %s, 'ACTIVE', %s, now())
        ON CONFLICT (exam_sitting_id, class_section_id)
        DO UPDATE SET status = 'ACTIVE', updated_at = now()
        """
        if conn is not None:
            with conn.cursor() as cur:
                for cs_id in class_section_ids:
                    cur.execute(query, (int(exam_sitting_id), int(cs_id), int(created_by)))
            return

        with open_connection() as conn_new:
            with conn_new.cursor() as cur:
                for cs_id in class_section_ids:
                    cur.execute(query, (int(exam_sitting_id), int(cs_id), int(created_by)))
            conn_new.commit()

    def remove_class_sections_from_sitting(
        self,
        *,
        exam_sitting_id: int,
        class_section_ids: list[int],
        conn: Connection | object | None = None,
    ) -> None:
        query = """
        UPDATE delivery.exam_sitting_class_section
        SET status = 'INACTIVE', updated_at = now()
        WHERE exam_sitting_id = %s
          AND class_section_id = ANY(%s)
        """
        param_ids = list(class_section_ids)
        if conn is not None:
            with conn.cursor() as cur:
                cur.execute(query, (int(exam_sitting_id), param_ids))
            return

        with open_connection() as conn_new:
            with conn_new.cursor() as cur:
                cur.execute(query, (int(exam_sitting_id), param_ids))
            conn_new.commit()

    def replace_class_sections_for_sitting(
        self,
        *,
        exam_sitting_id: int,
        to_activate: list[int],
        to_deactivate: list[int],
        created_by: int,
        conn: Connection | object | None = None,
    ) -> None:
        """Atomically deactivate removed sections and (re)activate kept/added ones."""

        def _apply(active_conn: Connection | object) -> None:
            if to_deactivate:
                self.remove_class_sections_from_sitting(
                    exam_sitting_id=int(exam_sitting_id),
                    class_section_ids=to_deactivate,
                    conn=active_conn,
                )
            if to_activate:
                self.add_class_sections_to_sitting(
                    exam_sitting_id=int(exam_sitting_id),
                    class_section_ids=to_activate,
                    created_by=int(created_by),
                    conn=active_conn,
                )

        if conn is not None:
            _apply(conn)
            return

        with open_connection() as conn_new:
            _apply(conn_new)
            conn_new.commit()

    def get_enrolled_student_ids_for_class_sections(
        self,
        class_section_ids: list[int],
        conn: Connection | object | None = None,
    ) -> list[int]:
        if not class_section_ids:
            return []
        query = """
        SELECT DISTINCT student_id
        FROM academic.class_enrollment
        WHERE class_section_id = ANY(%s)
          AND enrollment_status = 'ENROLLED'
        """
        param_ids = [int(x) for x in class_section_ids]
        if conn is not None:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (param_ids,))
                rows = cur.fetchall()
            return [int(r["student_id"]) for r in rows]

        with open_connection() as conn_new:
            with conn_new.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (param_ids,))
                rows = cur.fetchall()
            return [int(r["student_id"]) for r in rows]

    def get_assigned_student_ids_for_sitting(
        self,
        exam_sitting_id: int,
        conn: Connection | object | None = None,
    ) -> list[int]:
        query = """
        SELECT student_id
        FROM delivery.exam_assignment
        WHERE exam_sitting_id = %s
        """
        if conn is not None:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_id),))
                rows = cur.fetchall()
            return [int(r["student_id"]) for r in rows]

        with open_connection() as conn_new:
            with conn_new.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_sitting_id),))
                rows = cur.fetchall()
            return [int(r["student_id"]) for r in rows]
