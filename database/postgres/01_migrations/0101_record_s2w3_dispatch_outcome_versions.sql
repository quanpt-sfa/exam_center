-- Record S2W-3.2 dispatcher outcome persistence migration versions.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0100_create_submission_dispatch_outcome_table.sql', 'Create submission dispatch outcome audit table and latest view', NULL, current_user),
    ('0101_record_s2w3_dispatch_outcome_versions.sql', 'Record S2W-3.2 dispatcher outcome persistence migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
