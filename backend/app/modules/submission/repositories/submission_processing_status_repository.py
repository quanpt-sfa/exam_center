"""Read-only S2W-6 projection queries for submission processing status."""

from __future__ import annotations

from datetime import datetime

from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class SubmissionProcessingStatusRepository:
    """Build a consolidated read model snapshot for one submission."""

    def get_submission_snapshot(self, exam_submission_id: int) -> dict | None:
        submission_id = int(exam_submission_id)
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                submission_row = self._fetch_submission_row(cur, submission_id)
                if submission_row is None:
                    return None

                capture_row = self._fetch_latest_capture_row(cur, submission_id)
                capture_event_row = None
                if capture_row is not None:
                    capture_event_row = self._fetch_latest_capture_event_row(cur, int(capture_row["capture_job_id"]))

                grading_row = self._fetch_latest_grading_row(cur, submission_id)
                grading_run_row = None
                grading_event_row = None
                task_summary = self._empty_task_summary()
                result_summary = self._empty_result_summary()

                if grading_row is not None:
                    grading_job_id = int(grading_row["grading_job_id"])
                    grading_run_row = self._fetch_latest_grading_run_row(cur, grading_job_id)
                    grading_event_row = self._fetch_latest_grading_event_row(cur, grading_job_id)
                    task_summary = self._fetch_task_summary(cur, grading_job_id)
                    result_summary = self._fetch_result_summary(cur, grading_job_id)

                score_row = self._fetch_current_submission_score(cur, submission_id)

                return {
                    "submission": dict(submission_row),
                    "capture": {
                        "job": dict(capture_row) if capture_row else None,
                        "latest_event": dict(capture_event_row) if capture_event_row else None,
                    },
                    "grading": {
                        "job": dict(grading_row) if grading_row else None,
                        "run": dict(grading_run_row) if grading_run_row else None,
                        "latest_event": dict(grading_event_row) if grading_event_row else None,
                    },
                    "tasks": task_summary,
                    "results": result_summary,
                    "score": dict(score_row) if score_row else None,
                }

    @staticmethod
    def _fetch_submission_row(cur, exam_submission_id: int) -> dict | None:
        query = """
        SELECT
            es.exam_submission_id,
            es.submission_status,
            es.sealed_at AS submission_sealed_at,
            es.created_at,
            es.updated_at,
            ss.submission_seal_id,
            ss.seal_status,
            ss.sealed_at AS seal_row_sealed_at,
            coalesce(sa.sealed_answer_count, 0)::bigint AS sealed_answer_count,
            gei.exam_version_id,
            evdp.default_capture_profile_id,
            EXISTS (
                SELECT 1
                FROM assessment.v_question_grading_profile_summary qgps
                WHERE qgps.exam_version_id = gei.exam_version_id
                  AND qgps.status IN ('ACTIVE', 'DRAFT')
                  AND qgps.requires_capture = true
                LIMIT 1
            ) AS profile_capture_required
        FROM submission.exam_submission es
        LEFT JOIN submission.submission_seal ss
            ON ss.exam_submission_id = es.exam_submission_id
        LEFT JOIN delivery.generated_exam_instance gei
            ON gei.generated_exam_instance_id = es.generated_exam_instance_id
        LEFT JOIN assessment.exam_version_delivery_profile evdp
            ON evdp.exam_version_id = gei.exam_version_id
           AND evdp.status = 'ACTIVE'
        LEFT JOIN (
            SELECT
                exam_submission_id,
                count(*) AS sealed_answer_count
            FROM submission.sealed_answer
            GROUP BY exam_submission_id
        ) sa
            ON sa.exam_submission_id = es.exam_submission_id
        WHERE es.exam_submission_id = %s
        LIMIT 1
        """
        cur.execute(query, (int(exam_submission_id),))
        return cur.fetchone()

    @staticmethod
    def _fetch_latest_capture_row(cur, exam_submission_id: int) -> dict | None:
        query = """
        SELECT
            cj.capture_job_id,
            cj.capture_type,
            cj.capture_status,
            cj.requested_at,
            cj.started_at,
            cj.finished_at,
            cj.worker_id,
            cj.error_code,
            cj.error_message,
            coalesce(vs.artifact_count, 0)::bigint AS artifact_count,
            coalesce(vs.dataset_count, 0)::bigint AS dataset_count
        FROM capture.capture_job cj
        LEFT JOIN capture.v_capture_job_status vs
            ON vs.capture_job_id = cj.capture_job_id
        WHERE cj.exam_submission_id = %s
        ORDER BY cj.requested_at DESC, cj.capture_job_id DESC
        LIMIT 1
        """
        cur.execute(query, (int(exam_submission_id),))
        return cur.fetchone()

    @staticmethod
    def _fetch_latest_capture_event_row(cur, capture_job_id: int) -> dict | None:
        query = """
        SELECT
            event_type,
            event_at
        FROM capture.capture_job_event
        WHERE capture_job_id = %s
        ORDER BY event_at DESC, capture_job_event_id DESC
        LIMIT 1
        """
        cur.execute(query, (int(capture_job_id),))
        return cur.fetchone()

    @staticmethod
    def _fetch_latest_grading_row(cur, exam_submission_id: int) -> dict | None:
        query = """
        SELECT
            grading_job_id,
            grading_status,
            requested_at,
            started_at,
            finished_at,
            error_code,
            total_tasks,
            completed_tasks,
            failed_tasks,
            needs_review_tasks
        FROM grading.v_grading_job_status
        WHERE exam_submission_id = %s
        ORDER BY requested_at DESC, grading_job_id DESC
        LIMIT 1
        """
        cur.execute(query, (int(exam_submission_id),))
        return cur.fetchone()

    @staticmethod
    def _fetch_latest_grading_run_row(cur, grading_job_id: int) -> dict | None:
        query = """
        SELECT
            grading_run_id,
            run_status,
            started_at,
            finished_at,
            worker_id
        FROM grading.grading_run
        WHERE grading_job_id = %s
        ORDER BY run_no DESC, grading_run_id DESC
        LIMIT 1
        """
        cur.execute(query, (int(grading_job_id),))
        return cur.fetchone()

    @staticmethod
    def _fetch_latest_grading_event_row(cur, grading_job_id: int) -> dict | None:
        query = """
        SELECT
            event_type,
            event_at
        FROM grading.grading_event
        WHERE grading_job_id = %s
        ORDER BY event_at DESC, grading_event_id DESC
        LIMIT 1
        """
        cur.execute(query, (int(grading_job_id),))
        return cur.fetchone()

    @classmethod
    def _fetch_task_summary(cls, cur, grading_job_id: int) -> dict:
        counters_query = """
        SELECT
            count(*)::bigint AS total,
            count(*) FILTER (WHERE task_status = 'QUEUED')::bigint AS queued,
            count(*) FILTER (WHERE task_status = 'RUNNING')::bigint AS running,
            count(*) FILTER (WHERE task_status = 'WAITING_CAPTURE')::bigint AS waiting_capture,
            count(*) FILTER (WHERE task_status = 'COMPLETED')::bigint AS completed,
            count(*) FILTER (WHERE task_status = 'FAILED')::bigint AS failed,
            count(*) FILTER (WHERE task_status = 'NEEDS_REVIEW')::bigint AS needs_review
        FROM grading.question_grading_task
        WHERE grading_job_id = %s
        """
        cur.execute(counters_query, (int(grading_job_id),))
        counters = cur.fetchone() or cls._empty_task_summary()

        by_input_source_query = """
        SELECT input_source, count(*)::bigint AS total
        FROM grading.question_grading_task
        WHERE grading_job_id = %s
        GROUP BY input_source
        ORDER BY input_source ASC
        """
        cur.execute(by_input_source_query, (int(grading_job_id),))
        by_input_rows = cur.fetchall()

        by_language_query = """
        SELECT answer_language, count(*)::bigint AS total
        FROM grading.question_grading_task
        WHERE grading_job_id = %s
        GROUP BY answer_language
        ORDER BY answer_language ASC
        """
        cur.execute(by_language_query, (int(grading_job_id),))
        by_language_rows = cur.fetchall()

        summary = {
            "total": int(counters.get("total") or 0),
            "queued": int(counters.get("queued") or 0),
            "running": int(counters.get("running") or 0),
            "waiting_capture": int(counters.get("waiting_capture") or 0),
            "completed": int(counters.get("completed") or 0),
            "failed": int(counters.get("failed") or 0),
            "needs_review": int(counters.get("needs_review") or 0),
            "by_input_source": {
                str(row["input_source"]): int(row["total"])
                for row in by_input_rows
                if row.get("input_source") is not None
            },
            "by_answer_language": {
                str(row["answer_language"]): int(row["total"])
                for row in by_language_rows
                if row.get("answer_language") is not None
            },
        }
        if summary["total"] == 0:
            planned = cls._fetch_planned_task_summary(cur, grading_job_id)
            if planned["total"] > 0:
                return planned
        return summary

    @staticmethod
    def _fetch_planned_task_summary(cur, grading_job_id: int) -> dict:
        query = """
        SELECT
            count(sa.sealed_answer_id)::bigint AS total
        FROM grading.grading_job gj
        JOIN submission.sealed_answer sa
          ON sa.exam_submission_id = gj.exam_submission_id
         AND sa.submission_seal_id = gj.submission_seal_id
        WHERE gj.grading_job_id = %s
        """
        cur.execute(query, (int(grading_job_id),))
        row = cur.fetchone()
        total = int(row.get("total") or 0) if row else 0
        return {
            "total": total,
            "queued": total,
            "running": 0,
            "waiting_capture": 0,
            "completed": 0,
            "failed": 0,
            "needs_review": 0,
            "by_input_source": {},
            "by_answer_language": {},
        }

    @staticmethod
    def _fetch_result_summary(cur, grading_job_id: int) -> dict:
        query = """
        SELECT
            (
                SELECT count(*)
                FROM grading.actual_result ar
                JOIN grading.question_grading_task qgt
                    ON qgt.question_grading_task_id = ar.question_grading_task_id
                WHERE qgt.grading_job_id = %s
            )::bigint AS actual_result_count,
            (
                SELECT count(*)
                FROM grading.expected_actual_comparison eac
                JOIN grading.question_grading_task qgt
                    ON qgt.question_grading_task_id = eac.question_grading_task_id
                WHERE qgt.grading_job_id = %s
            )::bigint AS comparison_count,
            (
                SELECT count(*)
                FROM grading.question_score qs
                JOIN grading.question_grading_task qgt
                    ON qgt.question_grading_task_id = qs.question_grading_task_id
                WHERE qgt.grading_job_id = %s
            )::bigint AS question_score_count
        """
        cur.execute(query, (int(grading_job_id), int(grading_job_id), int(grading_job_id)))
        row = cur.fetchone()
        if row is None:
            return SubmissionProcessingStatusRepository._empty_result_summary()
        return {
            "actual_result_count": int(row.get("actual_result_count") or 0),
            "comparison_count": int(row.get("comparison_count") or 0),
            "question_score_count": int(row.get("question_score_count") or 0),
        }

    @staticmethod
    def _fetch_current_submission_score(cur, exam_submission_id: int) -> dict | None:
        query = """
        SELECT
            submission_score_id,
            final_score,
            total_max_score,
            score_status,
            finalized_at,
            scored_at
        FROM grading.v_submission_score_summary
        WHERE exam_submission_id = %s
          AND is_current = true
          AND score_status <> 'VOIDED'
        ORDER BY score_version_no DESC
        LIMIT 1
        """
        cur.execute(query, (int(exam_submission_id),))
        return cur.fetchone()

    @staticmethod
    def _empty_task_summary() -> dict:
        return {
            "total": 0,
            "queued": 0,
            "running": 0,
            "waiting_capture": 0,
            "completed": 0,
            "failed": 0,
            "needs_review": 0,
            "by_input_source": {},
            "by_answer_language": {},
        }

    @staticmethod
    def _empty_result_summary() -> dict:
        return {
            "actual_result_count": 0,
            "comparison_count": 0,
            "question_score_count": 0,
        }


def latest_non_null_datetime(values: list[datetime | None]) -> datetime | None:
    filtered = [value for value in values if value is not None]
    if not filtered:
        return None
    return max(filtered)
