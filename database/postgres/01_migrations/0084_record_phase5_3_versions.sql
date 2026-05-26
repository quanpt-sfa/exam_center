-- Phase 5.3 source: docs/phase_5a_individual_grading_runtime_design.md
-- Records migration versions for Phase 5.3 grading evidence tables.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0083_create_actual_result_and_comparison_tables.sql', 'Create Phase 5.3 grading.actual_result and grading.expected_actual_comparison tables', NULL, current_user),
    ('0084_record_phase5_3_versions.sql', 'Record Phase 5.3 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
