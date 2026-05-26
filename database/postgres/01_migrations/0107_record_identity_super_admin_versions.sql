-- Record identity super-admin RBAC migration versions.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0106_add_identity_super_admin_role_semantics.sql', 'Add super-admin role semantics and RBAC helper updates', NULL, current_user),
    ('0107_record_identity_super_admin_versions.sql', 'Record identity super-admin RBAC migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;