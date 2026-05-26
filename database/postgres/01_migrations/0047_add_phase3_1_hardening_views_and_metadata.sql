-- Phase 3.1.4 source: docs/phase_3_0_facility_proctoring_foundation.md
-- Hardening, safe views, FK lookup index completion, and Phase 3.1 metadata backfill.

-- Ensure FK lookup indexes for Phase 3.1 runtime tables (idempotent, non-duplicative).
CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_exam_assignment_id
    ON delivery.exam_session (exam_assignment_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_created_by
    ON delivery.exam_session (created_by);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_checkin_verification_exam_assignment_id
    ON delivery.exam_checkin_verification (exam_assignment_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_checkin_verification_exam_session_id
    ON delivery.exam_checkin_verification (exam_session_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_checkin_verification_station_assignment_id
    ON delivery.exam_checkin_verification (station_assignment_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_checkin_verification_verified_by
    ON delivery.exam_checkin_verification (verified_by);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_device_binding_exam_session_id
    ON delivery.exam_session_device_binding (exam_session_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_device_binding_exam_sitting_id
    ON delivery.exam_session_device_binding (exam_sitting_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_device_binding_station_id
    ON delivery.exam_session_device_binding (station_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_device_binding_device_id
    ON delivery.exam_session_device_binding (device_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_time_adjustment_exam_session_id
    ON delivery.exam_session_time_adjustment (exam_session_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_time_adjustment_approved_by
    ON delivery.exam_session_time_adjustment (approved_by);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_event_exam_session_id
    ON delivery.exam_session_event (exam_session_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_event_actor_user_id
    ON delivery.exam_session_event (actor_user_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_event_station_id
    ON delivery.exam_session_event (station_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_event_device_id
    ON delivery.exam_session_event (device_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_incident_exam_session_id
    ON delivery.exam_session_incident (exam_session_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_transfer_exam_session_id
    ON delivery.exam_session_transfer (exam_session_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_reschedule_original_exam_session_id
    ON delivery.exam_reschedule (original_exam_session_id);

-- Ensure sensitive direct table access is explicitly restricted for readonly role.
REVOKE SELECT ON TABLE delivery.exam_checkin_verification FROM exam_sys_readonly;
REVOKE SELECT ON TABLE delivery.exam_session_device_binding FROM exam_sys_readonly;
REVOKE SELECT ON TABLE delivery.exam_session_time_adjustment FROM exam_sys_readonly;
REVOKE SELECT ON TABLE delivery.exam_session_event FROM exam_sys_readonly;

CREATE OR REPLACE VIEW delivery.v_student_exam_launch_state AS
SELECT
    es.exam_session_id,
    ea.exam_assignment_id,
    ea.exam_sitting_id,
    ea.student_id,
    es.session_code,
    es.session_status,
    es.started_at,
    es.deadline_at,
    es.ended_at,
    es.time_limit_seconds,
    es.extra_time_seconds,
    ab.station_id,
    ls.station_code,
    r.room_id,
    r.room_code,
    ab.device_id,
    d.asset_tag,
    ab.binding_status
FROM delivery.exam_session es
JOIN delivery.exam_assignment ea
    ON ea.exam_assignment_id = es.exam_assignment_id
LEFT JOIN LATERAL (
    SELECT
        b.station_id,
        b.device_id,
        b.binding_status
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
    ON d.device_id = ab.device_id;

COMMENT ON VIEW delivery.v_student_exam_launch_state IS
    'Safe launch-state view for student exam startup. Excludes device fingerprint, metadata payloads, incident notes, and answer-bearing content.';

CREATE OR REPLACE VIEW delivery.v_proctor_active_session_monitor AS
SELECT
    ea.exam_sitting_id,
    esa.exam_sitting_room_id,
    r.room_id,
    r.room_code,
    COALESCE(ab.station_id, esa.station_id) AS station_id,
    ls.station_code,
    ea.exam_assignment_id,
    ea.student_id,
    sp.student_code,
    p.full_name,
    cp.photo_ref,
    es.exam_session_id,
    es.session_status,
    es.started_at,
    es.deadline_at,
    es.ended_at,
    es.last_seen_at,
    es.last_activity_at,
    ab.device_id,
    d.asset_tag,
    ab.binding_status
FROM delivery.exam_session es
JOIN delivery.exam_assignment ea
    ON ea.exam_assignment_id = es.exam_assignment_id
LEFT JOIN delivery.exam_station_assignment esa
    ON esa.exam_assignment_id = ea.exam_assignment_id
LEFT JOIN delivery.exam_sitting_room esr
    ON esr.exam_sitting_room_id = esa.exam_sitting_room_id
LEFT JOIN facility.room r
    ON r.room_id = esr.room_id
LEFT JOIN LATERAL (
    SELECT
        b.station_id,
        b.device_id,
        b.binding_status
    FROM delivery.exam_session_device_binding b
    WHERE b.exam_session_id = es.exam_session_id
      AND b.binding_status = 'ACTIVE'
    ORDER BY b.bound_at DESC, b.session_device_binding_id DESC
    LIMIT 1
) ab
    ON true
LEFT JOIN facility.lab_station ls
    ON ls.station_id = COALESCE(ab.station_id, esa.station_id)
LEFT JOIN facility.device d
    ON d.device_id = ab.device_id
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
) cp
    ON true
WHERE es.session_status IN (
    'CREATED',
    'WAITING_FOR_CHECKIN',
    'READY_TO_START',
    'IN_PROGRESS',
    'PAUSED',
    'INTERRUPTED'
);

COMMENT ON VIEW delivery.v_proctor_active_session_monitor IS
    'Operational proctor active-session monitor with identifiable student/person/photo data. If no proctor-specific role exists, service layer must enforce room-level authorization.';

CREATE OR REPLACE VIEW delivery.v_exam_session_timeline AS
SELECT
    ese.exam_session_id,
    ese.event_type,
    ese.event_at,
    ese.actor_user_id,
    ese.station_id,
    ese.device_id
FROM delivery.exam_session_event ese;

COMMENT ON VIEW delivery.v_exam_session_timeline IS
    'Safe exam-session timeline view without raw event_payload_json.';

GRANT SELECT ON TABLE delivery.v_student_exam_launch_state TO exam_sys_app;
GRANT SELECT ON TABLE delivery.v_proctor_active_session_monitor TO exam_sys_app;
GRANT SELECT ON TABLE delivery.v_exam_session_timeline TO exam_sys_app;

GRANT SELECT ON TABLE delivery.v_exam_session_timeline TO exam_sys_readonly;

-- Restrict identifiable launch/proctor views from broad readonly.
REVOKE SELECT ON TABLE delivery.v_student_exam_launch_state FROM exam_sys_readonly;
REVOKE SELECT ON TABLE delivery.v_proctor_active_session_monitor FROM exam_sys_readonly;

-- Ensure migration metadata includes all Phase 3.1 migrations.
INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0040_create_exam_session_core_tables.sql', 'Create delivery exam_session and exam_checkin_verification runtime core tables with constraints and indexes', NULL, current_user),
    ('0041_record_phase3_1_1_versions.sql', 'Record Phase 3.1.1 migration versions', NULL, current_user),
    ('0042_create_exam_session_device_binding.sql', 'Create delivery exam_session_device_binding with binding constraints, indexes, and hardened access', NULL, current_user),
    ('0043_attach_exam_session_foreign_keys.sql', 'Attach/ensure exam_session foreign keys and indexes for phase 3.0 operational tables', NULL, current_user),
    ('0044_record_phase3_1_2_versions.sql', 'Record Phase 3.1.2 migration versions', NULL, current_user),
    ('0045_create_exam_session_time_adjustment_and_event_tables.sql', 'Create exam_session_time_adjustment and exam_session_event with constraints, indexes, and hardened access', NULL, current_user),
    ('0046_record_phase3_1_3_versions.sql', 'Record Phase 3.1.3 migration versions', NULL, current_user),
    ('0047_add_phase3_1_hardening_views_and_metadata.sql', 'Add Phase 3.1 hardening, safe views, FK lookup index completion, and metadata backfill', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
