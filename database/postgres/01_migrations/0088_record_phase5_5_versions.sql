-- Phase 5.5 source: docs/phase_5a_individual_grading_runtime_design.md
-- Records migration versions for Phase 5.5 manual review and audit tables.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0087_create_manual_review_score_adjustment_and_grading_event_tables.sql', 'Create Phase 5.5 grading.manual_review_queue, grading.score_adjustment, and grading.grading_event tables', NULL, current_user),
    ('0088_record_phase5_5_versions.sql', 'Record Phase 5.5 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
