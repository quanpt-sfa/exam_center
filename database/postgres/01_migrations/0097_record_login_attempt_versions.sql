-- Record migration version for login attempt tracking foundation.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
	('0096_create_identity_login_attempt.sql', 'Create identity.login_attempt table for login lockout foundation', NULL, current_user),
	('0097_record_login_attempt_versions.sql', 'Record login attempt migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
