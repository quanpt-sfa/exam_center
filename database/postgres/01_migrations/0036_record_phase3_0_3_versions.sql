-- Phase 3.0.3 source: docs/phase_3_0_facility_proctoring_foundation.md
-- Record Phase 3.0.3 migration versions idempotently.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0035_create_exam_assignment_and_station_assignment_tables.sql', 'Create delivery.exam_assignment and delivery.exam_station_assignment tables with constraints and indexes', NULL, current_user),
    ('0036_record_phase3_0_3_versions.sql', 'Record Phase 3.0.3 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
