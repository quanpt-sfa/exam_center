-- Phase 4.4 source: docs/phase_4_submission_autosave_seal_capture_pipeline.md
-- Creates answer conflict and recovery metadata table.

CREATE TABLE IF NOT EXISTS submission.answer_conflict (
    answer_conflict_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_submission_id bigint NOT NULL,
    generated_exam_question_id bigint NOT NULL,
    answer_state_id bigint NULL,
    client_version integer NULL,
    server_version integer NULL,
    conflict_type varchar(50) NOT NULL,
    client_payload_json jsonb NULL,
    server_payload_json jsonb NULL,
    detected_at timestamptz NOT NULL DEFAULT now(),
    resolved_status varchar(30) NOT NULL,
    resolved_at timestamptz NULL,
    resolved_by bigint NULL,
    note text NULL,
    CONSTRAINT ck_submission_answer_conflict_client_version CHECK (
        client_version IS NULL OR client_version > 0
    ),
    CONSTRAINT ck_submission_answer_conflict_server_version CHECK (
        server_version IS NULL OR server_version > 0
    ),
    CONSTRAINT ck_submission_answer_conflict_resolved_at CHECK (
        resolved_at IS NULL OR resolved_at >= detected_at
    ),
    CONSTRAINT ck_submission_answer_conflict_type CHECK (
        conflict_type IN (
            'VERSION_MISMATCH',
            'SAVE_AFTER_SEAL',
            'LATE_SAVE',
            'CLIENT_SERVER_DIVERGENCE',
            'DUPLICATE_BATCH_DIFFERENT_PAYLOAD'
        )
    ),
    CONSTRAINT ck_submission_answer_conflict_resolved_status CHECK (
        resolved_status IN (
            'UNRESOLVED',
            'SERVER_WINS',
            'CLIENT_ACCEPTED',
            'MANUAL_REVIEW',
            'IGNORED'
        )
    ),
    CONSTRAINT fk_submission_answer_conflict_exam_submission FOREIGN KEY (exam_submission_id)
        REFERENCES submission.exam_submission(exam_submission_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_submission_answer_conflict_generated_exam_question FOREIGN KEY (generated_exam_question_id)
        REFERENCES delivery.generated_exam_question(generated_exam_question_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_submission_answer_conflict_answer_state FOREIGN KEY (answer_state_id)
        REFERENCES submission.answer_state(answer_state_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_submission_answer_conflict_resolved_by FOREIGN KEY (resolved_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_submission_answer_conflict_exam_submission_id
    ON submission.answer_conflict (exam_submission_id);

CREATE INDEX IF NOT EXISTS idx_submission_answer_conflict_generated_exam_question_id
    ON submission.answer_conflict (generated_exam_question_id);

CREATE INDEX IF NOT EXISTS idx_submission_answer_conflict_answer_state_id
    ON submission.answer_conflict (answer_state_id);

CREATE INDEX IF NOT EXISTS idx_submission_answer_conflict_resolved_status
    ON submission.answer_conflict (resolved_status);

CREATE INDEX IF NOT EXISTS idx_submission_answer_conflict_detected_at
    ON submission.answer_conflict (detected_at);

CREATE INDEX IF NOT EXISTS idx_submission_answer_conflict_resolved_by
    ON submission.answer_conflict (resolved_by);

GRANT SELECT, INSERT, UPDATE ON TABLE submission.answer_conflict TO exam_sys_app;
REVOKE SELECT ON TABLE submission.answer_conflict FROM exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA submission TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA submission TO exam_sys_readonly;
