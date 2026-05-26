-- Phase 3.0.1 source: docs/phase_3_0_facility_proctoring_foundation.md
-- Record Phase 3.0.1 migration versions idempotently.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0028_create_facility_schema_and_room_tables.sql', 'Create facility schema with room and lab station tables', NULL, current_user),
    ('0029_create_device_registry_tables.sql', 'Create facility device, registration, and check-in tables with security hardening', NULL, current_user),
    ('0030_record_phase3_0_1_versions.sql', 'Record Phase 3.0.1 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;