-- Phase 3.3.1 source: docs/phase_3_0_facility_proctoring_foundation.md
-- Final runtime hardening and integrity summary views for Phase 3 readiness.

-- Ensure sensitive direct table access is restricted for readonly role.
REVOKE SELECT ON TABLE identity.person_photo FROM exam_sys_readonly;
REVOKE SELECT ON TABLE facility.device_registration FROM exam_sys_readonly;
REVOKE SELECT ON TABLE delivery.exam_station_assignment FROM exam_sys_readonly;
REVOKE SELECT ON TABLE delivery.exam_session FROM exam_sys_readonly;
REVOKE SELECT ON TABLE delivery.exam_checkin_verification FROM exam_sys_readonly;
REVOKE SELECT ON TABLE delivery.exam_session_device_binding FROM exam_sys_readonly;
REVOKE SELECT ON TABLE delivery.exam_session_event FROM exam_sys_readonly;
REVOKE SELECT ON TABLE delivery.exam_session_time_adjustment FROM exam_sys_readonly;
REVOKE SELECT ON TABLE delivery.generated_question_parameter FROM exam_sys_readonly;
REVOKE SELECT ON TABLE delivery.generated_expected_answer FROM exam_sys_readonly;

-- Runtime/audit-sensitive tables must not be physically deletable by app role.
REVOKE DELETE ON TABLE delivery.exam_session FROM exam_sys_app;
REVOKE DELETE ON TABLE delivery.exam_checkin_verification FROM exam_sys_app;
REVOKE DELETE ON TABLE delivery.exam_session_device_binding FROM exam_sys_app;
REVOKE DELETE ON TABLE delivery.exam_session_time_adjustment FROM exam_sys_app;
REVOKE DELETE ON TABLE delivery.exam_session_event FROM exam_sys_app;
REVOKE DELETE ON TABLE delivery.exam_session_incident FROM exam_sys_app;
REVOKE DELETE ON TABLE delivery.exam_session_transfer FROM exam_sys_app;
REVOKE DELETE ON TABLE delivery.exam_reschedule FROM exam_sys_app;
REVOKE DELETE ON TABLE delivery.generated_exam_instance FROM exam_sys_app;
REVOKE DELETE ON TABLE delivery.generated_exam_question FROM exam_sys_app;
REVOKE DELETE ON TABLE delivery.generated_question_parameter FROM exam_sys_app;
REVOKE DELETE ON TABLE delivery.generated_expected_answer FROM exam_sys_app;

CREATE OR REPLACE VIEW delivery.v_phase3_session_delivery_state AS
SELECT
    ea.exam_sitting_id,
    ea.exam_assignment_id,
    es.exam_session_id,
    ea.student_id,
    es.session_status,
    es.started_at,
    es.deadline_at,
    es.ended_at,
    ab.station_id,
    ls.station_code,
    r.room_id,
    r.room_code,
    ab.device_id,
    d.asset_tag,
    gei.generated_exam_instance_id,
    gei.generation_status,
    COALESCE(gq.generated_question_count, 0) AS generated_question_count,
    COALESCE(gq.generated_total_score, 0::numeric) AS generated_total_score
FROM delivery.exam_session es
JOIN delivery.exam_assignment ea
    ON ea.exam_assignment_id = es.exam_assignment_id
LEFT JOIN LATERAL (
    SELECT
        b.station_id,
        b.device_id
    FROM delivery.exam_session_device_binding b
    WHERE b.exam_session_id = es.exam_session_id
      AND b.binding_status = 'ACTIVE'
    ORDER BY b.bound_at DESC, b.session_device_binding_id DESC
    LIMIT 1
) ab
    ON true
LEFT JOIN facility.lab_station ls
    ON ls.station_id = ab.station_id
LEFT JOIN facility.room r
    ON r.room_id = ls.room_id
LEFT JOIN facility.device d
    ON d.device_id = ab.device_id
LEFT JOIN delivery.generated_exam_instance gei
    ON gei.exam_session_id = es.exam_session_id
LEFT JOIN (
    SELECT
        generated_exam_instance_id,
        COUNT(*) AS generated_question_count,
        SUM(score) AS generated_total_score
    FROM delivery.generated_exam_question
    GROUP BY generated_exam_instance_id
) gq
    ON gq.generated_exam_instance_id = gei.generated_exam_instance_id;

COMMENT ON VIEW delivery.v_phase3_session_delivery_state IS
    'Safe phase-3 delivery runtime state view without expected answers, parameter values, fingerprints, event payloads, or incident notes.';

CREATE OR REPLACE VIEW delivery.v_phase3_integrity_summary AS
SELECT
    es.exam_sitting_id,
    COALESCE(a.assigned_students, 0) AS assigned_students,
    COALESCE(sa.station_assignments, 0) AS station_assignments,
    COALESCE(ss.sessions_created, 0) AS sessions_created,
    COALESCE(ss.active_sessions, 0) AS active_sessions,
    COALESCE(gi.generated_instances, 0) AS generated_instances,
    COALESCE(gq.generated_questions, 0) AS generated_questions,
    COALESCE(i.incidents, 0) AS incidents,
    COALESCE(t.transfers, 0) AS transfers,
    COALESCE(r.reschedules, 0) AS reschedules
FROM delivery.exam_sitting es
LEFT JOIN (
    SELECT exam_sitting_id, COUNT(*) AS assigned_students
    FROM delivery.exam_assignment
    GROUP BY exam_sitting_id
) a
    ON a.exam_sitting_id = es.exam_sitting_id
LEFT JOIN (
    SELECT ea.exam_sitting_id, COUNT(*) AS station_assignments
    FROM delivery.exam_station_assignment esa
    JOIN delivery.exam_assignment ea
        ON ea.exam_assignment_id = esa.exam_assignment_id
    GROUP BY ea.exam_sitting_id
) sa
    ON sa.exam_sitting_id = es.exam_sitting_id
LEFT JOIN (
    SELECT
        ea.exam_sitting_id,
        COUNT(*) AS sessions_created,
        COUNT(*) FILTER (
            WHERE sess.session_status IN ('CREATED', 'WAITING_FOR_CHECKIN', 'READY_TO_START', 'IN_PROGRESS', 'PAUSED', 'INTERRUPTED')
        ) AS active_sessions
    FROM delivery.exam_session sess
    JOIN delivery.exam_assignment ea
        ON ea.exam_assignment_id = sess.exam_assignment_id
    GROUP BY ea.exam_sitting_id
) ss
    ON ss.exam_sitting_id = es.exam_sitting_id
LEFT JOIN (
    SELECT ea.exam_sitting_id, COUNT(*) AS generated_instances
    FROM delivery.generated_exam_instance gei
    JOIN delivery.exam_session sess
        ON sess.exam_session_id = gei.exam_session_id
    JOIN delivery.exam_assignment ea
        ON ea.exam_assignment_id = sess.exam_assignment_id
    GROUP BY ea.exam_sitting_id
) gi
    ON gi.exam_sitting_id = es.exam_sitting_id
LEFT JOIN (
    SELECT ea.exam_sitting_id, COUNT(*) AS generated_questions
    FROM delivery.generated_exam_question geq
    JOIN delivery.generated_exam_instance gei
        ON gei.generated_exam_instance_id = geq.generated_exam_instance_id
    JOIN delivery.exam_session sess
        ON sess.exam_session_id = gei.exam_session_id
    JOIN delivery.exam_assignment ea
        ON ea.exam_assignment_id = sess.exam_assignment_id
    GROUP BY ea.exam_sitting_id
) gq
    ON gq.exam_sitting_id = es.exam_sitting_id
LEFT JOIN (
    SELECT exam_sitting_id, COUNT(*) AS incidents
    FROM delivery.exam_session_incident
    GROUP BY exam_sitting_id
) i
    ON i.exam_sitting_id = es.exam_sitting_id
LEFT JOIN (
    SELECT exam_sitting_id, COUNT(*) AS transfers
    FROM delivery.exam_session_transfer
    GROUP BY exam_sitting_id
) t
    ON t.exam_sitting_id = es.exam_sitting_id
LEFT JOIN (
    SELECT ea.exam_sitting_id, COUNT(*) AS reschedules
    FROM delivery.exam_reschedule er
    JOIN delivery.exam_assignment ea
        ON ea.exam_assignment_id = er.original_exam_assignment_id
    GROUP BY ea.exam_sitting_id
) r
    ON r.exam_sitting_id = es.exam_sitting_id;

COMMENT ON VIEW delivery.v_phase3_integrity_summary IS
    'Phase 3 operational integrity counts by exam_sitting for transition-readiness monitoring.';

GRANT SELECT ON TABLE delivery.v_phase3_session_delivery_state TO exam_sys_app;
GRANT SELECT ON TABLE delivery.v_phase3_integrity_summary TO exam_sys_app;

GRANT SELECT ON TABLE delivery.v_phase3_session_delivery_state TO exam_sys_readonly;
GRANT SELECT ON TABLE delivery.v_phase3_integrity_summary TO exam_sys_readonly;
