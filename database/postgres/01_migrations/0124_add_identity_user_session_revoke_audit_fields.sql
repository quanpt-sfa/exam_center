ALTER TABLE identity.user_session
    ADD COLUMN IF NOT EXISTS revoked_by_user_id bigint NULL,
    ADD COLUMN IF NOT EXISTS revoke_actor_role text NULL,
    ADD COLUMN IF NOT EXISTS revoke_context_json jsonb NULL;

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_identity_user_session_revoked_by_user'
    ) THEN
        ALTER TABLE identity.user_session
            ADD CONSTRAINT fk_identity_user_session_revoked_by_user
            FOREIGN KEY (revoked_by_user_id)
            REFERENCES identity.app_user(user_id)
            ON DELETE SET NULL;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_identity_user_session_revoked_by_user_id
    ON identity.user_session (revoked_by_user_id)
    WHERE revoked_by_user_id IS NOT NULL;

COMMENT ON COLUMN identity.user_session.revoked_by_user_id IS
    'User ID of the actor who revoked the refresh session.';

COMMENT ON COLUMN identity.user_session.revoke_actor_role IS
    'Role used by the actor when revoking the refresh session.';

COMMENT ON COLUMN identity.user_session.revoke_context_json IS
    'Non-secret audit context for administrative or proctor-driven session revocation.';