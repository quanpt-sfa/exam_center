-- Persisted refresh session state for auth hardening.

CREATE TABLE IF NOT EXISTS identity.user_session (
    session_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id bigint NOT NULL,
    refresh_jti text NOT NULL,
    refresh_token_hash text NOT NULL,
    issued_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz NULL,
    revoke_reason text NULL,
    replaced_by_session_id bigint NULL,
    user_agent text NULL,
    ip_address inet NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_identity_user_session_refresh_jti UNIQUE (refresh_jti),
    CONSTRAINT fk_identity_user_session_user FOREIGN KEY (user_id)
        REFERENCES identity.app_user(user_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_identity_user_session_replaced_by FOREIGN KEY (replaced_by_session_id)
        REFERENCES identity.user_session(session_id)
        ON DELETE SET NULL,
    CONSTRAINT ck_identity_user_session_expiry CHECK (expires_at >= issued_at),
    CONSTRAINT ck_identity_user_session_revoke_time CHECK (revoked_at IS NULL OR revoked_at >= issued_at),
    CONSTRAINT ck_identity_user_session_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at)
);

CREATE INDEX IF NOT EXISTS idx_identity_user_session_user_id
    ON identity.user_session (user_id);

CREATE INDEX IF NOT EXISTS idx_identity_user_session_expires_at
    ON identity.user_session (expires_at);

CREATE INDEX IF NOT EXISTS idx_identity_user_session_active
    ON identity.user_session (user_id, expires_at)
    WHERE revoked_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_identity_user_session_refresh_token_hash
    ON identity.user_session (refresh_token_hash);

COMMENT ON TABLE identity.user_session IS
    'Persisted refresh token sessions with rotation and revocation metadata.';

COMMENT ON COLUMN identity.user_session.refresh_token_hash IS
    'Hash of refresh token value; raw refresh token is never stored.';

DO
$$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE identity.user_session TO exam_sys_app;
        GRANT USAGE, SELECT ON SEQUENCE identity.user_session_session_id_seq TO exam_sys_app;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_readonly') THEN
        REVOKE ALL ON TABLE identity.user_session FROM exam_sys_readonly;
        REVOKE ALL ON SEQUENCE identity.user_session_session_id_seq FROM exam_sys_readonly;
    END IF;
END
$$;

REVOKE ALL ON TABLE identity.user_session FROM PUBLIC;
REVOKE ALL ON SEQUENCE identity.user_session_session_id_seq FROM PUBLIC;
