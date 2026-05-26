"""Database-backed read model for the admin dashboard."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from psycopg.rows import dict_row

from app.core.security import get_security_settings
from app.infrastructure.database.connection import open_connection


_ACTIVE_ASSIGNMENT_STATUSES = ("ASSIGNED", "CHECKED_IN")
_PROCTOR_ASSIGNMENT_STATUSES = ("ASSIGNED", "CONFIRMED")
_OPENABLE_ROOM_STATUSES = ("OPEN", "READY")
_TERMINAL_SUBMISSION_STATUSES = ("SUBMITTED", "AUTO_SUBMITTED", "FORCE_SEALED", "EXPIRED_SEALED", "VOIDED")
_FAILED_GRADING_STATUSES = ("FAILED", "PARTIALLY_FAILED", "CANCELLED")
_PENDING_GRADING_STATUSES = ("QUEUED", "WAITING_CAPTURE")
_RUNNING_GRADING_STATUSES = ("CLAIMED", "RUNNING", "RETRYING")
_NON_STARTED_SESSION_STATUSES = ("CREATED", "WAITING_FOR_CHECKIN", "READY_TO_START")
_STARTED_SESSION_STATUSES = ("IN_PROGRESS", "PAUSED", "INTERRUPTED", "ENDED", "SUBMITTED", "FORCE_CLOSED", "EXPIRED")
_ATTENDANCE_PENDING_STATUSES = ("ASSIGNED",)
_ACTIVE_SESSION_STATUSES = ("READY_TO_START", "IN_PROGRESS", "PAUSED")
_EXPECTED_SUBMISSION_SESSION_STATUSES = ("IN_PROGRESS", "PAUSED", "INTERRUPTED", "ENDED", "EXPIRED", "SUBMITTED", "FORCE_CLOSED")


class DashboardRepository:
    """Aggregated operational queries for dashboard contracts."""

    def get_summary_snapshot(self, *, now: datetime) -> dict:
        settings = self._load_settings()

        summary = self._load_sitting_and_setup_counts(now=now, settings=settings)
        summary.update(self._load_live_counts())
        summary.update(self._load_incident_counts(now=now))
        summary.update(self._load_close_room_counts(settings=settings))
        summary.update(self._load_grading_counts())
        summary.update(self._load_system_counts(now=now))
        return summary

    def list_alert_rows(self, *, now: datetime) -> list[dict]:
        settings = self._load_settings()
        rows: list[dict] = []
        rows.extend(self._list_incident_alert_rows())
        rows.extend(self._list_close_room_alert_rows(settings=settings))
        rows.extend(self._list_setup_alert_rows())
        rows.extend(self._list_stale_session_alert_rows(settings=settings, now=now))
        rows.sort(key=lambda row: (row["created_at"], row["alert_id"]), reverse=True)
        return rows

    @staticmethod
    def _row_int(row: dict | None, key: str) -> int:
        if row is None:
            return 0
        return int(row.get(key) or 0)

    def _load_settings(self) -> dict:
        query = """
        SELECT
            COALESCE(min_proctors_per_room, 1) AS min_proctors_per_room,
            COALESCE(session_heartbeat_seconds, 30) AS session_heartbeat_seconds
        FROM ops.system_settings
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query)
                row = cur.fetchone()
        if row is None:
            return {"min_proctors_per_room": 1, "session_heartbeat_seconds": 30}
        return {
            "min_proctors_per_room": max(1, int(row.get("min_proctors_per_room") or 1)),
            "session_heartbeat_seconds": max(1, int(row.get("session_heartbeat_seconds") or 30)),
        }

    def _load_sitting_and_setup_counts(self, *, now: datetime, settings: dict) -> dict:
        query = """
        WITH sitting_flags AS (
            SELECT
                sit.exam_sitting_id,
                sit.scheduled_start_at,
                upper(coalesce(sit.sitting_status, '')) AS sitting_status,
                sit.exam_version_id,
                EXISTS (
                    SELECT 1
                    FROM delivery.exam_assignment ea
                    WHERE ea.exam_sitting_id = sit.exam_sitting_id
                      AND ea.assignment_status = ANY(%s)
                ) AS has_runtime_assignments,
                EXISTS (
                    SELECT 1
                    FROM delivery.generated_exam_question geq
                    JOIN delivery.generated_exam_instance gei
                      ON gei.generated_exam_instance_id = geq.generated_exam_instance_id
                    JOIN delivery.exam_session sess
                      ON sess.exam_session_id = gei.exam_session_id
                    JOIN delivery.exam_assignment ea
                      ON ea.exam_assignment_id = sess.exam_assignment_id
                    WHERE ea.exam_sitting_id = sit.exam_sitting_id
                ) AS has_generated_questions
            FROM delivery.exam_sitting sit
        ),
        room_flags AS (
            SELECT
                room.exam_sitting_room_id,
                room.exam_sitting_id,
                COALESCE((
                    SELECT count(*)::bigint
                    FROM delivery.proctor_assignment pa
                    WHERE pa.exam_sitting_room_id = room.exam_sitting_room_id
                                            AND upper(coalesce(pa.status, '')) = ANY(%s)
                ), 0) AS proctor_count,
                EXISTS (
                    SELECT 1
                    FROM delivery.v_room_station_readiness rsr
                    WHERE rsr.room_id = room.room_id
                      AND upper(coalesce(rsr.last_health_status, 'UNKNOWN')) = 'READY'
                ) AS has_ready_station
            FROM delivery.exam_sitting_room room
        ),
        unassigned_assignments AS (
            SELECT DISTINCT ea.exam_sitting_id, ea.exam_assignment_id
            FROM delivery.exam_assignment ea
            LEFT JOIN delivery.exam_station_assignment esa
              ON esa.exam_assignment_id = ea.exam_assignment_id
            WHERE ea.assignment_status NOT IN ('CANCELLED', 'VOIDED')
              AND esa.exam_assignment_id IS NULL
        ),
        not_ready_sittings AS (
            SELECT exam_sitting_id
            FROM sitting_flags
            WHERE exam_version_id IS NULL
               OR NOT (has_runtime_assignments AND has_generated_questions)
            UNION
            SELECT exam_sitting_id
            FROM room_flags
            WHERE proctor_count < %s OR NOT has_ready_station
            UNION
            SELECT exam_sitting_id
            FROM unassigned_assignments
        ),
        import_failures AS (
            SELECT count(*)::bigint AS failed_import_jobs
            FROM importing.import_job job
            WHERE upper(coalesce(job.job_status, '')) = 'FAILED'
               OR upper(coalesce(job.validation_status, '')) = 'FAILED'
               OR upper(coalesce(job.commit_status, '')) = 'FAILED'
        )
        SELECT
            COALESCE((
                SELECT count(*)::bigint
                FROM sitting_flags
                WHERE scheduled_start_at >= date_trunc('day', %s)
                  AND scheduled_start_at < date_trunc('day', %s) + interval '1 day'
            ), 0) AS sittings_today,
            COALESCE((
                SELECT count(*)::bigint
                FROM sitting_flags
                WHERE sitting_status = 'OPEN'
            ), 0) AS open_sittings,
            COALESCE((
                SELECT count(*)::bigint
                FROM sitting_flags
                WHERE scheduled_start_at >= %s
                  AND scheduled_start_at < %s + interval '24 hour'
            ), 0) AS upcoming_24h_sittings,
            COALESCE((SELECT count(*)::bigint FROM not_ready_sittings), 0) AS not_ready_sittings,
            COALESCE((
                SELECT count(*)::bigint
                FROM sitting_flags
                WHERE exam_version_id IS NULL
            ), 0) AS sittings_without_published_exam,
            COALESCE((
                SELECT count(*)::bigint
                FROM sitting_flags
                WHERE exam_version_id IS NULL
                   OR NOT (has_runtime_assignments AND has_generated_questions)
            ), 0) AS sittings_not_prepared,
            COALESCE((
                SELECT count(*)::bigint
                FROM room_flags
                WHERE proctor_count < %s
            ), 0) AS rooms_missing_proctors,
            COALESCE((
                SELECT count(*)::bigint
                FROM room_flags
                WHERE NOT has_ready_station
            ), 0) AS rooms_missing_ready_stations,
            COALESCE((
                SELECT count(*)::bigint
                FROM unassigned_assignments
            ), 0) AS students_unassigned,
            COALESCE((SELECT failed_import_jobs FROM import_failures), 0) AS failed_import_jobs
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        list(_ACTIVE_ASSIGNMENT_STATUSES),
                        list(_PROCTOR_ASSIGNMENT_STATUSES),
                        int(settings["min_proctors_per_room"]),
                        now,
                        now,
                        now,
                        now,
                        int(settings["min_proctors_per_room"]),
                    ),
                )
                row = cur.fetchone()
        row = row or {}
        return {
            "sittings_today": self._row_int(row, "sittings_today"),
            "open_sittings": self._row_int(row, "open_sittings"),
            "upcoming_24h_sittings": self._row_int(row, "upcoming_24h_sittings"),
            "not_ready_sittings": self._row_int(row, "not_ready_sittings"),
            "sittings_without_published_exam": self._row_int(row, "sittings_without_published_exam"),
            "sittings_not_prepared": self._row_int(row, "sittings_not_prepared"),
            "rooms_missing_proctors": self._row_int(row, "rooms_missing_proctors"),
            "rooms_missing_ready_stations": self._row_int(row, "rooms_missing_ready_stations"),
            "students_unassigned": self._row_int(row, "students_unassigned"),
            "failed_import_jobs": self._row_int(row, "failed_import_jobs"),
        }

    def _load_live_counts(self) -> dict:
        query = """
        WITH live_assignments AS (
            SELECT
                ea.exam_assignment_id,
                ea.exam_sitting_id,
                upper(coalesce(ea.assignment_status, '')) AS assignment_status,
                upper(coalesce(sit.sitting_status, '')) AS sitting_status,
                room.exam_sitting_room_id,
                upper(coalesce(room.room_status, '')) AS room_status,
                sess.exam_session_id,
                upper(coalesce(sess.session_status, '')) AS session_status,
                sess.started_at,
                sub.submission_status
            FROM delivery.exam_assignment ea
            JOIN delivery.exam_sitting sit
              ON sit.exam_sitting_id = ea.exam_sitting_id
            LEFT JOIN delivery.exam_station_assignment esa
              ON esa.exam_assignment_id = ea.exam_assignment_id
            LEFT JOIN delivery.exam_sitting_room room
              ON room.exam_sitting_room_id = esa.exam_sitting_room_id
            LEFT JOIN LATERAL (
                SELECT
                    es.exam_session_id,
                    es.session_status,
                    es.started_at
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
            WHERE ea.assignment_status NOT IN ('CANCELLED', 'VOIDED')
        )
        SELECT
            count(DISTINCT exam_sitting_room_id) FILTER (WHERE room_status = 'OPEN')::bigint AS open_rooms,
            count(*) FILTER (WHERE sitting_status = 'OPEN' AND assignment_status = 'CHECKED_IN')::bigint AS checked_in,
            count(*) FILTER (WHERE sitting_status = 'OPEN' AND assignment_status = ANY(%s))::bigint AS not_checked_in,
            count(*) FILTER (
                WHERE started_at IS NOT NULL
                   OR session_status = ANY(%s)
            )::bigint AS started,
            count(*) FILTER (
                WHERE assignment_status = 'CHECKED_IN'
                  AND (exam_session_id IS NULL OR session_status = ANY(%s))
            )::bigint AS checked_in_not_started,
            count(*) FILTER (
                WHERE sitting_status = 'OPEN'
                  AND assignment_status NOT IN ('ABSENT', 'COMPLETED', 'RESCHEDULED', 'CANCELLED', 'VOIDED')
                  AND (exam_session_id IS NULL OR session_status = ANY(%s))
            )::bigint AS not_started_in_open_sittings,
            count(*) FILTER (WHERE session_status = 'INTERRUPTED')::bigint AS interrupted,
            count(*) FILTER (
                WHERE upper(coalesce(submission_status, '')) = ANY(%s)
            )::bigint AS sealed
        FROM live_assignments
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        list(_ATTENDANCE_PENDING_STATUSES),
                        list(_STARTED_SESSION_STATUSES),
                        list(_NON_STARTED_SESSION_STATUSES),
                        list(_NON_STARTED_SESSION_STATUSES),
                        list(_TERMINAL_SUBMISSION_STATUSES),
                    ),
                )
                row = cur.fetchone()
        row = row or {}
        return {
            "open_rooms": self._row_int(row, "open_rooms"),
            "checked_in": self._row_int(row, "checked_in"),
            "not_checked_in": self._row_int(row, "not_checked_in"),
            "started": self._row_int(row, "started"),
            "checked_in_not_started": self._row_int(row, "checked_in_not_started"),
            "not_started_in_open_sittings": self._row_int(row, "not_started_in_open_sittings"),
            "interrupted": self._row_int(row, "interrupted"),
            "sealed": self._row_int(row, "sealed"),
        }

    def _load_incident_counts(self, *, now: datetime) -> dict:
        query = """
        SELECT
            count(*) FILTER (WHERE upper(coalesce(incident_status, '')) = 'OPEN')::bigint AS open_incidents,
            count(*) FILTER (WHERE upper(coalesce(incident_status, '')) = 'IN_PROGRESS')::bigint AS in_progress_incidents,
            count(*) FILTER (
                WHERE upper(coalesce(incident_status, '')) = 'RESOLVED'
                  AND resolved_at >= date_trunc('day', %s)
                  AND resolved_at < date_trunc('day', %s) + interval '1 day'
            )::bigint AS resolved_today_incidents
        FROM delivery.exam_session_incident
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (now, now))
                row = cur.fetchone()
        row = row or {}
        return {
            "open_incidents": self._row_int(row, "open_incidents"),
            "in_progress_incidents": self._row_int(row, "in_progress_incidents"),
            "resolved_today_incidents": self._row_int(row, "resolved_today_incidents"),
        }

    def _load_close_room_counts(self, *, settings: dict) -> dict:
        stale_cutoff = datetime.now(timezone.utc) - timedelta(seconds=int(settings["session_heartbeat_seconds"]) * 3)
        query = """
        WITH per_room_snapshot AS (
            SELECT
                room.exam_sitting_room_id,
                upper(coalesce(room.room_status, '')) AS room_status,
                count(*) FILTER (
                    WHERE ea.assignment_status NOT IN ('CHECKED_IN', 'ABSENT', 'COMPLETED', 'RESCHEDULED', 'CANCELLED', 'VOIDED')
                )::bigint AS pending_attendance_count,
                count(*) FILTER (
                    WHERE upper(coalesce(inc.incident_status, '')) = 'OPEN'
                )::bigint AS open_incident_count,
                count(*) FILTER (
                    WHERE upper(coalesce(inc.incident_status, '')) = 'IN_PROGRESS'
                )::bigint AS in_progress_incident_count,
                count(*) FILTER (
                    WHERE upper(coalesce(sess.session_status, '')) = ANY(%s)
                )::bigint AS active_session_count,
                count(*) FILTER (
                    WHERE upper(coalesce(sess.session_status, '')) = 'INTERRUPTED'
                )::bigint AS interrupted_session_count,
                count(*) FILTER (
                    WHERE ea.assignment_status <> 'ABSENT'
                      AND upper(coalesce(sess.session_status, '')) = ANY(%s)
                      AND upper(coalesce(sub.submission_status, '')) <> ALL(%s)
                )::bigint AS pending_submission_count,
                count(*) FILTER (
                    WHERE upper(coalesce(sess.session_status, '')) = ANY(%s)
                      AND sess.last_seen_at IS NOT NULL
                      AND sess.last_seen_at < %s
                )::bigint AS stale_heartbeat_count
            FROM delivery.exam_sitting_room room
            LEFT JOIN delivery.exam_station_assignment esa
              ON esa.exam_sitting_room_id = room.exam_sitting_room_id
            LEFT JOIN delivery.exam_assignment ea
              ON ea.exam_assignment_id = esa.exam_assignment_id
            LEFT JOIN LATERAL (
                SELECT es.exam_session_id, es.session_status, es.last_seen_at
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
            LEFT JOIN delivery.exam_session_incident inc
              ON inc.exam_sitting_room_id = room.exam_sitting_room_id
            GROUP BY room.exam_sitting_room_id, room.room_status
        )
        SELECT
            count(*) FILTER (
                WHERE room_status = ANY(%s)
                  AND (
                    pending_attendance_count > 0
                    OR open_incident_count > 0
                    OR in_progress_incident_count > 0
                    OR active_session_count > 0
                    OR interrupted_session_count > 0
                    OR pending_submission_count > 0
                    OR stale_heartbeat_count > 0
                  )
            )::bigint AS blocked_rooms,
            count(*) FILTER (WHERE room_status = 'CLOSED')::bigint AS closed_rooms
        FROM per_room_snapshot
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        list(_ACTIVE_SESSION_STATUSES),
                        list(_EXPECTED_SUBMISSION_SESSION_STATUSES),
                        list(_TERMINAL_SUBMISSION_STATUSES),
                        list(_ACTIVE_SESSION_STATUSES),
                        stale_cutoff,
                        list(_OPENABLE_ROOM_STATUSES),
                    ),
                )
                row = cur.fetchone()
        row = row or {}
        return {
            "blocked_rooms": self._row_int(row, "blocked_rooms"),
            "closed_rooms": self._row_int(row, "closed_rooms"),
        }

    def _load_grading_counts(self) -> dict:
        query = """
        WITH job_counts AS (
            SELECT
                count(*) FILTER (WHERE upper(coalesce(grading_status, '')) = ANY(%s))::bigint AS pending_grading_jobs,
                count(*) FILTER (WHERE upper(coalesce(grading_status, '')) = ANY(%s))::bigint AS running_grading_jobs,
                count(*) FILTER (WHERE upper(coalesce(grading_status, '')) = ANY(%s))::bigint AS failed_grading_jobs
            FROM grading.grading_job
        ),
        score_counts AS (
            SELECT count(*)::bigint AS computed_scores
            FROM grading.v_submission_score_summary
            WHERE is_current = true
              AND upper(coalesce(score_status, '')) <> 'VOIDED'
        ),
        review_counts AS (
            SELECT count(*)::bigint AS needs_review_count
            FROM grading.v_manual_review_queue
            WHERE upper(coalesce(review_status, 'OPEN')) NOT IN ('RESOLVED', 'VOIDED')
        )
        SELECT
            COALESCE((SELECT pending_grading_jobs FROM job_counts), 0) AS pending_grading_jobs,
            COALESCE((SELECT running_grading_jobs FROM job_counts), 0) AS running_grading_jobs,
            COALESCE((SELECT computed_scores FROM score_counts), 0) AS computed_scores,
            COALESCE((SELECT needs_review_count FROM review_counts), 0) AS needs_review_count,
            COALESCE((SELECT failed_grading_jobs FROM job_counts), 0) AS failed_grading_jobs
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        list(_PENDING_GRADING_STATUSES),
                        list(_RUNNING_GRADING_STATUSES),
                        list(_FAILED_GRADING_STATUSES),
                    ),
                )
                row = cur.fetchone()
        row = row or {}
        return {
            "pending_grading_jobs": self._row_int(row, "pending_grading_jobs"),
            "running_grading_jobs": self._row_int(row, "running_grading_jobs"),
            "computed_scores": self._row_int(row, "computed_scores"),
            "needs_review_count": self._row_int(row, "needs_review_count"),
            "failed_grading_jobs": self._row_int(row, "failed_grading_jobs"),
        }

    def _load_system_counts(self, *, now: datetime) -> dict:
        security = get_security_settings()
        window_start = now - timedelta(seconds=max(1, int(security.auth_lockout_window_seconds)))
        query = """
        WITH active_sessions AS (
            SELECT count(*)::bigint AS active_user_sessions
            FROM identity.user_session
            WHERE revoked_at IS NULL
              AND expires_at > %s
        ),
        locked_identifier AS (
            SELECT
                lower(username_or_email) AS identifier,
                count(*) FILTER (WHERE success = FALSE AND attempted_at >= %s)::bigint AS failure_count,
                max(attempted_at) FILTER (WHERE success = FALSE AND attempted_at >= %s) AS latest_failure_at
            FROM identity.login_attempt
            GROUP BY lower(username_or_email)
        ),
        lockouts AS (
            SELECT count(*)::bigint AS locked_accounts
            FROM locked_identifier
            WHERE failure_count >= %s
              AND latest_failure_at IS NOT NULL
              AND latest_failure_at + (%s * interval '1 second') > %s
        )
        SELECT
            COALESCE((SELECT active_user_sessions FROM active_sessions), 0) AS active_user_sessions,
            COALESCE((SELECT locked_accounts FROM lockouts), 0) AS locked_accounts
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        now,
                        window_start,
                        window_start,
                        int(security.auth_max_failed_attempts),
                        int(security.auth_lockout_duration_seconds),
                        now,
                    ),
                )
                row = cur.fetchone()
        row = row or {}
        return {
            "active_user_sessions": self._row_int(row, "active_user_sessions"),
            "locked_accounts": self._row_int(row, "locked_accounts"),
            "workers_unhealthy": 0,
        }

    def _list_incident_alert_rows(self) -> list[dict]:
        query = """
        SELECT
            concat('incident:', inc.incident_id) AS alert_id,
            'INCIDENT' AS type,
            CASE
                WHEN upper(coalesce(inc.incident_status, '')) = 'OPEN' THEN 'critical'
                WHEN upper(coalesce(inc.incident_status, '')) = 'IN_PROGRESS' THEN 'warning'
                ELSE 'info'
            END AS severity,
            concat('Incident ', coalesce(inc.incident_type, 'OPEN')) AS title,
            left(coalesce(nullif(trim(inc.description), ''), 'Exam session incident requires attention'), 2000) AS description,
            'incident' AS entity_type,
            inc.incident_id::text AS entity_id,
            room.exam_sitting_id,
            inc.exam_sitting_room_id,
            CASE
                WHEN inc.exam_sitting_room_id IS NOT NULL THEN concat('/proctor/sitting-rooms/', inc.exam_sitting_room_id::text, '/incidents')
                ELSE '/delivery/incidents'
            END AS action_route,
            coalesce(inc.reported_at, now()) AS created_at,
            'open' AS status
        FROM delivery.exam_session_incident inc
        LEFT JOIN delivery.exam_sitting_room room
          ON room.exam_sitting_room_id = inc.exam_sitting_room_id
        WHERE upper(coalesce(inc.incident_status, '')) IN ('OPEN', 'IN_PROGRESS')
        ORDER BY coalesce(inc.reported_at, now()) DESC, inc.incident_id DESC
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query)
                return cur.fetchall()

    def _list_close_room_alert_rows(self, *, settings: dict) -> list[dict]:
        stale_cutoff = datetime.now(timezone.utc) - timedelta(seconds=int(settings["session_heartbeat_seconds"]) * 3)
        query = """
        WITH per_room AS (
            SELECT
                room.exam_sitting_room_id,
                room.exam_sitting_id,
                fr.room_code,
                upper(coalesce(room.room_status, '')) AS room_status,
                count(*) FILTER (
                    WHERE ea.assignment_status NOT IN ('CHECKED_IN', 'ABSENT', 'COMPLETED', 'RESCHEDULED', 'CANCELLED', 'VOIDED')
                )::bigint AS pending_attendance_count,
                count(*) FILTER (WHERE upper(coalesce(inc.incident_status, '')) = 'OPEN')::bigint AS open_incident_count,
                count(*) FILTER (WHERE upper(coalesce(inc.incident_status, '')) = 'IN_PROGRESS')::bigint AS in_progress_incident_count,
                count(*) FILTER (WHERE upper(coalesce(sess.session_status, '')) = ANY(%s))::bigint AS active_session_count,
                count(*) FILTER (WHERE upper(coalesce(sess.session_status, '')) = 'INTERRUPTED')::bigint AS interrupted_session_count,
                count(*) FILTER (
                    WHERE ea.assignment_status <> 'ABSENT'
                      AND upper(coalesce(sess.session_status, '')) = ANY(%s)
                      AND upper(coalesce(sub.submission_status, '')) <> ALL(%s)
                )::bigint AS pending_submission_count,
                count(*) FILTER (
                    WHERE upper(coalesce(sess.session_status, '')) = ANY(%s)
                      AND sess.last_seen_at IS NOT NULL
                      AND sess.last_seen_at < %s
                )::bigint AS stale_heartbeat_count,
                max(coalesce(sess.last_seen_at, room.updated_at, room.created_at, now())) AS created_at
            FROM delivery.exam_sitting_room room
                        LEFT JOIN facility.room fr
                            ON fr.room_id = room.room_id
            LEFT JOIN delivery.exam_station_assignment esa
              ON esa.exam_sitting_room_id = room.exam_sitting_room_id
            LEFT JOIN delivery.exam_assignment ea
              ON ea.exam_assignment_id = esa.exam_assignment_id
            LEFT JOIN LATERAL (
                SELECT exam_session_id, session_status, last_seen_at
                FROM delivery.exam_session es
                WHERE es.exam_assignment_id = ea.exam_assignment_id
                  AND es.session_status <> 'VOIDED'
                ORDER BY es.session_no DESC, es.exam_session_id DESC
                LIMIT 1
            ) sess ON TRUE
            LEFT JOIN LATERAL (
                SELECT submission_status
                FROM submission.exam_submission sub
                WHERE sub.exam_session_id = sess.exam_session_id
                ORDER BY sub.exam_submission_id DESC
                LIMIT 1
            ) sub ON TRUE
            LEFT JOIN delivery.exam_session_incident inc
              ON inc.exam_sitting_room_id = room.exam_sitting_room_id
                        GROUP BY room.exam_sitting_room_id, room.exam_sitting_id, fr.room_code, room.room_status
        )
        SELECT
            concat('close-room:', exam_sitting_room_id) AS alert_id,
            'CLOSE_ROOM_BLOCKED' AS type,
            'critical' AS severity,
            concat('Close room blocked for ', coalesce(room_code, concat('room ', exam_sitting_room_id::text))) AS title,
            left(concat(
                'Close room remains blocked. pending_attendance=', pending_attendance_count,
                ', open_incidents=', open_incident_count,
                ', in_progress_incidents=', in_progress_incident_count,
                ', active_sessions=', active_session_count,
                ', interrupted_sessions=', interrupted_session_count,
                ', pending_submissions=', pending_submission_count,
                ', stale_heartbeats=', stale_heartbeat_count
            ), 2000) AS description,
            'exam_sitting_room' AS entity_type,
            exam_sitting_room_id::text AS entity_id,
            exam_sitting_id,
            exam_sitting_room_id,
            concat('/proctor/sitting-rooms/', exam_sitting_room_id::text, '/close-preflight') AS action_route,
            created_at,
            'open' AS status
        FROM per_room
        WHERE room_status = ANY(%s)
          AND (
            pending_attendance_count > 0
            OR open_incident_count > 0
            OR in_progress_incident_count > 0
            OR active_session_count > 0
            OR interrupted_session_count > 0
            OR pending_submission_count > 0
            OR stale_heartbeat_count > 0
          )
        ORDER BY created_at DESC, exam_sitting_room_id DESC
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        list(_ACTIVE_SESSION_STATUSES),
                        list(_EXPECTED_SUBMISSION_SESSION_STATUSES),
                        list(_TERMINAL_SUBMISSION_STATUSES),
                        list(_ACTIVE_SESSION_STATUSES),
                        stale_cutoff,
                        list(_OPENABLE_ROOM_STATUSES),
                    ),
                )
                return cur.fetchall()

    def _list_setup_alert_rows(self) -> list[dict]:
        query = """
        WITH sitting_flags AS (
            SELECT
                sit.exam_sitting_id,
                sit.sitting_code,
                sit.sitting_name,
                sit.exam_version_id,
                sit.scheduled_start_at,
                EXISTS (
                    SELECT 1
                    FROM delivery.exam_assignment ea
                    WHERE ea.exam_sitting_id = sit.exam_sitting_id
                      AND ea.assignment_status = ANY(%s)
                ) AS has_runtime_assignments,
                EXISTS (
                    SELECT 1
                    FROM delivery.generated_exam_question geq
                    JOIN delivery.generated_exam_instance gei
                      ON gei.generated_exam_instance_id = geq.generated_exam_instance_id
                    JOIN delivery.exam_session sess
                      ON sess.exam_session_id = gei.exam_session_id
                    JOIN delivery.exam_assignment ea
                      ON ea.exam_assignment_id = sess.exam_assignment_id
                    WHERE ea.exam_sitting_id = sit.exam_sitting_id
                ) AS has_generated_questions
            FROM delivery.exam_sitting sit
        ),
        issue_rows AS (
            SELECT
                exam_sitting_id,
                scheduled_start_at AS created_at,
                CASE
                    WHEN exam_version_id IS NULL THEN 'SETUP_BLOCKER_NO_PUBLISHED_EXAM'
                    ELSE 'SETUP_BLOCKER_NOT_PREPARED'
                END AS type,
                CASE
                    WHEN exam_version_id IS NULL THEN 'critical'
                    ELSE 'warning'
                END AS severity,
                CASE
                    WHEN exam_version_id IS NULL THEN 'Sitting missing published exam version'
                    ELSE 'Sitting runtime is not prepared'
                END AS title,
                CASE
                    WHEN exam_version_id IS NULL THEN 'Exam sitting cannot proceed because no published exam version is linked.'
                    ELSE 'Exam sitting has not been prepared with runtime assignments and generated questions.'
                END AS description
            FROM sitting_flags
            WHERE exam_version_id IS NULL
               OR NOT (has_runtime_assignments AND has_generated_questions)
        )
        SELECT
            concat('setup:', type, ':', exam_sitting_id) AS alert_id,
            type,
            severity,
            title,
            left(description, 2000) AS description,
            'exam_sitting' AS entity_type,
            exam_sitting_id::text AS entity_id,
            exam_sitting_id,
            NULL::bigint AS exam_sitting_room_id,
            concat('/delivery/exam-sittings/', exam_sitting_id::text) AS action_route,
            created_at,
            'open' AS status
        FROM issue_rows
        ORDER BY created_at DESC, exam_sitting_id DESC
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (list(_ACTIVE_ASSIGNMENT_STATUSES),))
                return cur.fetchall()

    def _list_stale_session_alert_rows(self, *, settings: dict, now: datetime) -> list[dict]:
        stale_cutoff = now - timedelta(seconds=int(settings["session_heartbeat_seconds"]) * 3)
        query = """
        WITH stale_sessions AS (
            SELECT
                sess.exam_session_id,
                ea.exam_sitting_id,
                room.exam_sitting_room_id,
                sess.last_seen_at,
                upper(coalesce(sess.session_status, '')) AS session_status
            FROM delivery.exam_session sess
            JOIN delivery.exam_assignment ea
              ON ea.exam_assignment_id = sess.exam_assignment_id
            LEFT JOIN delivery.exam_station_assignment esa
              ON esa.exam_assignment_id = ea.exam_assignment_id
            LEFT JOIN delivery.exam_sitting_room room
              ON room.exam_sitting_room_id = esa.exam_sitting_room_id
            WHERE upper(coalesce(sess.session_status, '')) IN ('READY_TO_START', 'IN_PROGRESS', 'PAUSED', 'INTERRUPTED')
              AND sess.last_seen_at IS NOT NULL
              AND sess.last_seen_at < %s
        )
        SELECT
            concat('session:', exam_session_id) AS alert_id,
            CASE WHEN session_status = 'INTERRUPTED' THEN 'SESSION_INTERRUPTED' ELSE 'SESSION_STALE' END AS type,
            CASE WHEN session_status = 'INTERRUPTED' THEN 'critical' ELSE 'warning' END AS severity,
            CASE WHEN session_status = 'INTERRUPTED' THEN 'Interrupted candidate session' ELSE 'Candidate session heartbeat is stale' END AS title,
            left(
                CASE
                    WHEN session_status = 'INTERRUPTED' THEN 'Candidate session is interrupted and requires operational follow-up.'
                    ELSE 'Candidate session has not reported heartbeat within the configured safety window.'
                END,
                2000
            ) AS description,
            'exam_session' AS entity_type,
            exam_session_id::text AS entity_id,
            exam_sitting_id,
            exam_sitting_room_id,
            CASE
                WHEN exam_sitting_room_id IS NOT NULL THEN concat('/proctor/sitting-rooms/', exam_sitting_room_id::text, '/submission-monitor')
                ELSE concat('/delivery/exam-sessions/', exam_session_id::text)
            END AS action_route,
            last_seen_at AS created_at,
            'open' AS status
        FROM stale_sessions
        ORDER BY last_seen_at DESC, exam_session_id DESC
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (stale_cutoff,))
                return cur.fetchall()
