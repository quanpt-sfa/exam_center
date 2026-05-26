-- Phase 3.1.2 source: docs/phase_3_0_facility_proctoring_foundation.md
-- Records migration versions for Phase 3.1.2 idempotently.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0042_create_exam_session_device_binding.sql', 'Create delivery exam_session_device_binding with binding constraints, indexes, and hardened access', NULL, current_user),
    ('0043_attach_exam_session_foreign_keys.sql', 'Attach/ensure exam_session foreign keys and indexes for phase 3.0 operational tables', NULL, current_user),
    ('0044_record_phase3_1_2_versions.sql', 'Record Phase 3.1.2 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
