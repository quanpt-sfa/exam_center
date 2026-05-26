-- Record importing/ops migration versions.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0091_create_importing_and_ops_schemas_and_tables.sql', 'Create importing and ops schemas with staging/audit tables', NULL, current_user),
    ('0092_seed_import_templates_and_ops_commands.sql', 'Seed import templates and ops command/scope registries', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
