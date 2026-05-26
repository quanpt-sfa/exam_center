-- Phase 5.6 source: docs/phase_5a_individual_grading_runtime_design.md
-- Records migration versions for Phase 5A final hardening.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0089_add_phase5a_safe_views_and_grants.sql', 'Add Phase 5A safe views, grants, and final hardening rules', NULL, current_user),
    ('0090_record_phase5a_versions.sql', 'Record Phase 5A final migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
