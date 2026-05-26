-- Phase 3.1.1 source: docs/phase_3_0_facility_proctoring_foundation.md
-- Record Phase 3.1.1 migration versions idempotently.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0040_create_exam_session_core_tables.sql', 'Create delivery exam_session and exam_checkin_verification runtime core tables with constraints and indexes', NULL, current_user),
    ('0041_record_phase3_1_1_versions.sql', 'Record Phase 3.1.1 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
