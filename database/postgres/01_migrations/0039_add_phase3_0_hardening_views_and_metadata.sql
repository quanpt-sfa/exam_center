-- Phase 3.0.5 source: docs/phase_3_0_facility_proctoring_foundation.md
-- Hardening, safe views, FK lookup index completion, and Phase 3.0 metadata backfill.

-- Add missing FK lookup indexes for Phase 3.0 tables (non-duplicative).
CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_transfer_from_device_id
    ON delivery.exam_session_transfer (from_device_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_transfer_to_device_id
    ON delivery.exam_session_transfer (to_device_id);

-- Ensure sensitive direct table access is explicitly restricted for readonly role.
REVOKE SELECT ON TABLE identity.person_photo FROM exam_sys_readonly;
REVOKE SELECT ON TABLE facility.device_registration FROM exam_sys_readonly;
REVOKE SELECT ON TABLE delivery.exam_session_incident FROM exam_sys_readonly;
REVOKE SELECT ON TABLE delivery.exam_session_transfer FROM exam_sys_readonly;
REVOKE SELECT ON TABLE delivery.exam_reschedule FROM exam_sys_readonly;

CREATE OR REPLACE VIEW delivery.v_exam_sitting_room_summary AS
SELECT
    es.exam_sitting_id,
    es.sitting_code,
    es.sitting_name,
    es.sitting_status,
    es.scheduled_start_at,
    es.scheduled_end_at,
    esr.exam_sitting_room_id,
    r.room_id,
    r.room_code,
    r.room_name,
    esr.room_status,
    esr.capacity_allocated,
    COALESCE(a.assigned_student_count, 0) AS assigned_student_count,
    COALESCE(a.assigned_station_count, 0) AS assigned_station_count
FROM delivery.exam_sitting es
JOIN delivery.exam_sitting_room esr
    ON esr.exam_sitting_id = es.exam_sitting_id
JOIN facility.room r
    ON r.room_id = esr.room_id
LEFT JOIN (
    SELECT
        esa.exam_sitting_room_id,
        COUNT(DISTINCT esa.exam_assignment_id) AS assigned_student_count,
        COUNT(DISTINCT esa.station_id) AS assigned_station_count
    FROM delivery.exam_station_assignment esa
    GROUP BY esa.exam_sitting_room_id
) a
    ON a.exam_sitting_room_id = esr.exam_sitting_room_id;

COMMENT ON VIEW delivery.v_exam_sitting_room_summary IS
    'Safe delivery room summary view for sitting/room capacity and assignment counts.';

CREATE OR REPLACE VIEW delivery.v_room_station_readiness AS
SELECT
    r.room_id,
    r.room_code,
    ls.station_id,
    ls.station_code,
    ls.status AS station_status,
    d.device_id,
    d.asset_tag,
    d.status AS device_status,
    lc.last_checkin_at,
    lc.last_health_status
FROM facility.room r
JOIN facility.lab_station ls
    ON ls.room_id = r.room_id
LEFT JOIN facility.device d
    ON d.current_station_id = ls.station_id
LEFT JOIN LATERAL (
    SELECT
        dc.checkin_at AS last_checkin_at,
        dc.health_status AS last_health_status
    FROM facility.device_checkin dc
    WHERE dc.device_id = d.device_id
    ORDER BY dc.checkin_at DESC, dc.device_checkin_id DESC
    LIMIT 1
) lc
    ON true;

COMMENT ON VIEW delivery.v_room_station_readiness IS
    'Safe readiness view for room/station/device state and latest checkin health.';

CREATE OR REPLACE VIEW delivery.v_proctor_room_roster AS
SELECT
    es.exam_sitting_id,
    esr.exam_sitting_room_id,
    r.room_id,
    r.room_code,
    ls.station_id,
    ls.station_code,
    ea.exam_assignment_id,
    ea.student_id,
    sp.student_code,
    p.person_id,
    p.full_name,
    cp.photo_ref,
    ea.assignment_status,
    esa.status AS station_assignment_status
FROM delivery.exam_station_assignment esa
JOIN delivery.exam_assignment ea
    ON ea.exam_assignment_id = esa.exam_assignment_id
JOIN delivery.exam_sitting_room esr
    ON esr.exam_sitting_room_id = esa.exam_sitting_room_id
JOIN delivery.exam_sitting es
    ON es.exam_sitting_id = esr.exam_sitting_id
JOIN facility.room r
    ON r.room_id = esr.room_id
JOIN facility.lab_station ls
    ON ls.station_id = esa.station_id
JOIN identity.student_profile sp
    ON sp.student_id = ea.student_id
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
    ON true;

COMMENT ON VIEW delivery.v_proctor_room_roster IS
    'Operational proctor roster view with identifiable student/person/photo data; restricted access required.';

GRANT SELECT ON TABLE delivery.v_exam_sitting_room_summary TO exam_sys_app;
GRANT SELECT ON TABLE delivery.v_room_station_readiness TO exam_sys_app;
GRANT SELECT ON TABLE delivery.v_proctor_room_roster TO exam_sys_app;

GRANT SELECT ON TABLE delivery.v_exam_sitting_room_summary TO exam_sys_readonly;
GRANT SELECT ON TABLE delivery.v_room_station_readiness TO exam_sys_readonly;

-- Do not expose identifiable roster broadly.
REVOKE SELECT ON TABLE delivery.v_proctor_room_roster FROM exam_sys_readonly;

-- Ensure migration metadata includes all Phase 3.0 migrations.
INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0028_create_facility_schema_and_room_tables.sql', 'Create facility schema with room and lab station tables', NULL, current_user),
    ('0029_create_device_registry_tables.sql', 'Create facility device, registration, and check-in tables with security hardening', NULL, current_user),
    ('0030_record_phase3_0_1_versions.sql', 'Record Phase 3.0.1 migration versions', NULL, current_user),
    ('0031_create_identity_person_photo.sql', 'Create identity.person_photo with historical tracking and restricted readonly access', NULL, current_user),
    ('0032_create_delivery_schema_and_sitting_tables.sql', 'Create delivery schema and foundational exam sitting and sitting room tables', NULL, current_user),
    ('0033_create_proctor_assignment_table.sql', 'Create delivery.proctor_assignment table and indexes', NULL, current_user),
    ('0034_record_phase3_0_2_versions.sql', 'Record Phase 3.0.2 migration versions', NULL, current_user),
    ('0035_create_exam_assignment_and_station_assignment_tables.sql', 'Create delivery.exam_assignment and delivery.exam_station_assignment tables with constraints and indexes', NULL, current_user),
    ('0036_record_phase3_0_3_versions.sql', 'Record Phase 3.0.3 migration versions', NULL, current_user),
    ('0037_create_incident_transfer_reschedule_tables.sql', 'Create delivery exam incident, station transfer, and reschedule tables with conditional exam_session FKs', NULL, current_user),
    ('0038_record_phase3_0_4_versions.sql', 'Record Phase 3.0.4 migration versions', NULL, current_user),
    ('0039_add_phase3_0_hardening_views_and_metadata.sql', 'Add Phase 3.0 hardening, safe views, FK lookup index completion, and metadata backfill', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
