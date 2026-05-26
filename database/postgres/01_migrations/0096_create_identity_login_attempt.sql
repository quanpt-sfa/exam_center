-- Add persisted login attempt tracking for minimal brute-force protection.

CREATE TABLE IF NOT EXISTS identity.login_attempt (
    login_attempt_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username_or_email text NOT NULL,
    user_id bigint NULL,
    ip_address text NULL,
    user_agent text NULL,
    success boolean NOT NULL,
    failure_reason text NULL,
    attempted_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_identity_login_attempt_user FOREIGN KEY (user_id)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_identity_login_attempt_identifier_attempted_at
    ON identity.login_attempt (lower(username_or_email), attempted_at DESC);

CREATE INDEX IF NOT EXISTS idx_identity_login_attempt_ip_attempted_at
    ON identity.login_attempt (ip_address, attempted_at DESC)
    WHERE ip_address IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_identity_login_attempt_success_attempted_at
    ON identity.login_attempt (success, attempted_at DESC);

COMMENT ON TABLE identity.login_attempt IS
    'Audit and lockout foundation for login attempts (success/failure).';

DO
$$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_app') THEN
        GRANT SELECT, INSERT ON TABLE identity.login_attempt TO exam_sys_app;
        GRANT USAGE, SELECT ON SEQUENCE identity.login_attempt_login_attempt_id_seq TO exam_sys_app;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_readonly') THEN
        REVOKE ALL ON TABLE identity.login_attempt FROM exam_sys_readonly;
        REVOKE ALL ON SEQUENCE identity.login_attempt_login_attempt_id_seq FROM exam_sys_readonly;
    END IF;
END
$$;

REVOKE ALL ON TABLE identity.login_attempt FROM PUBLIC;
REVOKE ALL ON SEQUENCE identity.login_attempt_login_attempt_id_seq FROM PUBLIC;
