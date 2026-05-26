CREATE TABLE IF NOT EXISTS submission.submission_history (
    submission_history_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_submission_id bigint NOT NULL,
    exam_session_id bigint NULL,
    actor_user_id bigint NULL,
    actor_role varchar(50) NOT NULL,
    action_type varchar(50) NOT NULL,
    from_status varchar(30) NULL,
    to_status varchar(30) NOT NULL,
    reason_code varchar(50) NULL,
    note text NULL,
    context_json jsonb NULL,
    idempotency_key varchar(255) NULL,
    changed_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_submission_history_submission
        FOREIGN KEY (exam_submission_id)
        REFERENCES submission.exam_submission(exam_submission_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_submission_history_session
        FOREIGN KEY (exam_session_id)
        REFERENCES delivery.exam_session(exam_session_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_submission_history_actor
        FOREIGN KEY (actor_user_id)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL,
    CONSTRAINT ck_submission_history_to_status CHECK (
        to_status IN ('DRAFT', 'IN_PROGRESS', 'SUBMITTED', 'AUTO_SUBMITTED', 'FORCE_SEALED', 'EXPIRED_SEALED', 'VOIDED')
    ),
    CONSTRAINT ck_submission_history_from_status CHECK (
        from_status IS NULL
        OR from_status IN ('DRAFT', 'IN_PROGRESS', 'SUBMITTED', 'AUTO_SUBMITTED', 'FORCE_SEALED', 'EXPIRED_SEALED', 'VOIDED')
    )
);

CREATE INDEX IF NOT EXISTS idx_submission_history_submission_changed
    ON submission.submission_history (exam_submission_id, changed_at DESC, submission_history_id DESC);

CREATE INDEX IF NOT EXISTS idx_submission_history_session_changed
    ON submission.submission_history (exam_session_id, changed_at DESC, submission_history_id DESC)
    WHERE exam_session_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_submission_history_actor_changed
    ON submission.submission_history (actor_user_id, changed_at DESC, submission_history_id DESC)
    WHERE actor_user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_submission_history_action_changed
    ON submission.submission_history (action_type, changed_at DESC, submission_history_id DESC);

COMMENT ON TABLE submission.submission_history IS
    'Immutable lifecycle audit for authoritative submission status transitions.';

GRANT SELECT, INSERT ON TABLE submission.submission_history TO exam_sys_app;
REVOKE SELECT ON TABLE submission.submission_history FROM exam_sys_readonly;

GRANT USAGE, SELECT ON SEQUENCE submission.submission_history_submission_history_id_seq TO exam_sys_app;
GRANT USAGE, SELECT ON SEQUENCE submission.submission_history_submission_history_id_seq TO exam_sys_readonly;