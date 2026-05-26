-- Phase 4.3 source: docs/phase_4_submission_autosave_seal_capture_pipeline.md
-- Creates submission seal record and immutable sealed answer snapshot tables.

CREATE TABLE IF NOT EXISTS submission.submission_seal (
    submission_seal_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_submission_id bigint NOT NULL,
    seal_idempotency_key varchar(255) NOT NULL,
    seal_status varchar(30) NOT NULL,
    seal_reason varchar(50) NOT NULL,
    sealed_at timestamptz NOT NULL DEFAULT now(),
    sealed_by bigint NULL,
    server_time_at_seal timestamptz NOT NULL DEFAULT now(),
    answer_count integer NOT NULL DEFAULT 0,
    submission_hash char(64) NULL,
    metadata_json jsonb NULL,
    CONSTRAINT uq_submission_submission_seal_exam_submission UNIQUE (exam_submission_id),
    CONSTRAINT uq_submission_submission_seal_idempotency UNIQUE (exam_submission_id, seal_idempotency_key),
    CONSTRAINT ck_submission_submission_seal_answer_count CHECK (answer_count >= 0),
    CONSTRAINT ck_submission_submission_seal_status CHECK (
        seal_status IN ('SEALED', 'FAILED', 'VOIDED', 'SUPERSEDED')
    ),
    CONSTRAINT ck_submission_submission_seal_reason CHECK (
        seal_reason IN (
            'STUDENT_SUBMIT',
            'TIME_EXPIRED',
            'PROCTOR_FORCE_CLOSE',
            'ADMIN_FORCE_CLOSE',
            'SYSTEM_RECOVERY_SEAL'
        )
    ),
    CONSTRAINT fk_submission_submission_seal_exam_submission FOREIGN KEY (exam_submission_id)
        REFERENCES submission.exam_submission(exam_submission_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_submission_submission_seal_sealed_by FOREIGN KEY (sealed_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS submission.sealed_answer (
    sealed_answer_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    submission_seal_id bigint NOT NULL,
    exam_submission_id bigint NOT NULL,
    generated_exam_question_id bigint NOT NULL,
    answer_state_id bigint NULL,
    answer_type varchar(50) NOT NULL,
    answer_text text NULL,
    answer_payload_json jsonb NULL,
    answer_hash char(64) NULL,
    answer_length integer NULL,
    sealed_at timestamptz NOT NULL DEFAULT now(),
    metadata_json jsonb NULL,
    CONSTRAINT uq_submission_sealed_answer_seal_question UNIQUE (submission_seal_id, generated_exam_question_id),
    CONSTRAINT uq_submission_sealed_answer_submission_question UNIQUE (exam_submission_id, generated_exam_question_id),
    CONSTRAINT ck_submission_sealed_answer_content_presence CHECK (
        answer_text IS NOT NULL OR answer_payload_json IS NOT NULL OR answer_hash IS NOT NULL
    ),
    CONSTRAINT ck_submission_sealed_answer_answer_length CHECK (
        answer_length IS NULL OR answer_length >= 0
    ),
    CONSTRAINT fk_submission_sealed_answer_submission_seal FOREIGN KEY (submission_seal_id)
        REFERENCES submission.submission_seal(submission_seal_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_submission_sealed_answer_exam_submission FOREIGN KEY (exam_submission_id)
        REFERENCES submission.exam_submission(exam_submission_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_submission_sealed_answer_generated_exam_question FOREIGN KEY (generated_exam_question_id)
        REFERENCES delivery.generated_exam_question(generated_exam_question_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_submission_sealed_answer_answer_state FOREIGN KEY (answer_state_id)
        REFERENCES submission.answer_state(answer_state_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_submission_submission_seal_exam_submission_id
    ON submission.submission_seal (exam_submission_id);

CREATE INDEX IF NOT EXISTS idx_submission_submission_seal_sealed_by
    ON submission.submission_seal (sealed_by);

CREATE INDEX IF NOT EXISTS idx_submission_submission_seal_sealed_at
    ON submission.submission_seal (sealed_at);

CREATE INDEX IF NOT EXISTS idx_submission_submission_seal_seal_status
    ON submission.submission_seal (seal_status);

CREATE INDEX IF NOT EXISTS idx_submission_submission_seal_seal_reason
    ON submission.submission_seal (seal_reason);

CREATE INDEX IF NOT EXISTS idx_submission_sealed_answer_submission_seal_id
    ON submission.sealed_answer (submission_seal_id);

CREATE INDEX IF NOT EXISTS idx_submission_sealed_answer_exam_submission_id
    ON submission.sealed_answer (exam_submission_id);

CREATE INDEX IF NOT EXISTS idx_submission_sealed_answer_generated_exam_question_id
    ON submission.sealed_answer (generated_exam_question_id);

CREATE INDEX IF NOT EXISTS idx_submission_sealed_answer_answer_state_id
    ON submission.sealed_answer (answer_state_id);

CREATE INDEX IF NOT EXISTS idx_submission_sealed_answer_answer_hash
    ON submission.sealed_answer (answer_hash);

GRANT SELECT, INSERT, UPDATE ON TABLE submission.submission_seal TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE submission.sealed_answer TO exam_sys_app;

REVOKE SELECT ON TABLE submission.submission_seal FROM exam_sys_readonly;
REVOKE SELECT ON TABLE submission.sealed_answer FROM exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA submission TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA submission TO exam_sys_readonly;
