-- Record auth session migration versions.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0094_create_identity_user_session.sql', 'Create identity.user_session for persisted refresh token lifecycle', NULL, current_user),
    ('0095_record_auth_session_versions.sql', 'Record auth session persistence migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
