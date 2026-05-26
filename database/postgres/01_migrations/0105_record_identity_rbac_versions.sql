-- Record identity RBAC migration versions.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0102_add_identity_permission_and_role_permission.sql', 'Add identity permission catalog and role-permission mapping tables', NULL, current_user),
    ('0103_seed_identity_permission_catalog_and_role_mappings.sql', 'Seed baseline identity permission catalog and role mappings', NULL, current_user),
    ('0104_add_identity_authorization_helpers.sql', 'Add identity authorization helper views and functions', NULL, current_user),
    ('0105_record_identity_rbac_versions.sql', 'Record identity RBAC migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;