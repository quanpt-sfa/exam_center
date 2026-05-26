-- Phase 5.1 source: docs/phase_5a_individual_grading_runtime_design.md
-- Records migration versions for Phase 5.1 grading runtime foundation.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0079_create_grading_job_and_run_tables.sql', 'Create Phase 5.1 grading runtime foundation tables grading_job and grading_run', NULL, current_user),
    ('0080_record_phase5_1_versions.sql', 'Record Phase 5.1 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
