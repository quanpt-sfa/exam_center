-- Phase 3.0.4 source: docs/phase_3_0_facility_proctoring_foundation.md
-- Record Phase 3.0.4 migration versions idempotently.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0037_create_incident_transfer_reschedule_tables.sql', 'Create delivery exam incident, station transfer, and reschedule tables with conditional exam_session FKs', NULL, current_user),
    ('0038_record_phase3_0_4_versions.sql', 'Record Phase 3.0.4 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
