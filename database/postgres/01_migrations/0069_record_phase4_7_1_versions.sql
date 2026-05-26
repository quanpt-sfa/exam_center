-- Phase 4.7.1 source: docs/phase_4_7_assessment_modality_grading_profile_foundation.md
-- Records migration versions for Phase 4.7.1 grading engine registry foundation.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0068_create_grading_schema_and_engine_registry.sql', 'Create grading schema and grading_engine registry with idempotent seed data', NULL, current_user),
    ('0069_record_phase4_7_1_versions.sql', 'Record Phase 4.7.1 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
