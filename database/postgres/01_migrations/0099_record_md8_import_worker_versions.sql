-- Record MD-8 import worker migration versions.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0098_add_import_job_worker_claim_columns.sql', 'Add import job worker claim/retry lifecycle columns and statuses', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
