-- Phase 3.3.1 source: docs/phase_3_0_facility_proctoring_foundation.md
-- Records migration versions for final Phase 3 hardening idempotently.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0054_add_phase3_final_hardening_and_integrity_views.sql', 'Add final Phase 3 runtime hardening, validation views, and transition-readiness summaries', NULL, current_user),
    ('0055_record_phase3_3_versions.sql', 'Record Phase 3.3.1 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
