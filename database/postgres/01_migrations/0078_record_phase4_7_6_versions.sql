-- Phase 4.7.6 source: docs/phase_4_7_assessment_modality_grading_profile_foundation.md
-- Records migration versions for Phase 4.7.6 hardening and safe views.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0077_add_phase4_7_safe_views_and_grants.sql', 'Add final Phase 4.7 safe views and least-privilege grant hardening', NULL, current_user),
    ('0078_record_phase4_7_6_versions.sql', 'Record Phase 4.7.6 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;