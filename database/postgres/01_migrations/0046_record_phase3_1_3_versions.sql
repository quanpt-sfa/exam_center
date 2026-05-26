-- Phase 3.1.3 source: docs/phase_3_0_facility_proctoring_foundation.md
-- Record migration versions for Phase 3.1.3 idempotently.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0045_create_exam_session_time_adjustment_and_event_tables.sql', 'Create exam_session_time_adjustment and exam_session_event with constraints, indexes, and hardened access', NULL, current_user),
    ('0046_record_phase3_1_3_versions.sql', 'Record Phase 3.1.3 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
