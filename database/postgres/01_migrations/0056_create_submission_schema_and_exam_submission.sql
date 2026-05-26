-- Phase 4.1 source: docs/phase_4_submission_autosave_seal_capture_pipeline.md
-- Creates submission schema and official exam submission container table.

CREATE SCHEMA IF NOT EXISTS submission;

COMMENT ON SCHEMA submission IS
    'Submission runtime schema: official submission container and later autosave/seal artifacts.';

ALTER SCHEMA submission OWNER TO exam_sys_owner;

GRANT USAGE ON SCHEMA submission TO exam_sys_app;
GRANT USAGE ON SCHEMA submission TO exam_sys_readonly;
GRANT CREATE ON SCHEMA submission TO exam_sys_owner;

CREATE TABLE IF NOT EXISTS submission.exam_submission (
    exam_submission_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_session_id bigint NOT NULL,
    generated_exam_instance_id bigint NOT NULL,
    submission_status varchar(30) NOT NULL,
    opened_at timestamptz NOT NULL DEFAULT now(),
    first_saved_at timestamptz NULL,
    last_saved_at timestamptz NULL,
    submitted_at timestamptz NULL,
    sealed_at timestamptz NULL,
    seal_reason varchar(50) NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    created_by bigint NULL,
    metadata_json jsonb NULL,
    CONSTRAINT uq_submission_exam_submission_exam_session UNIQUE (exam_session_id),
    CONSTRAINT uq_submission_exam_submission_generated_instance UNIQUE (generated_exam_instance_id),
    CONSTRAINT ck_submission_exam_submission_submitted_at CHECK (
        submitted_at IS NULL OR submitted_at >= opened_at
    ),
    CONSTRAINT ck_submission_exam_submission_sealed_at CHECK (
        sealed_at IS NULL OR sealed_at >= opened_at
    ),
    CONSTRAINT ck_submission_exam_submission_last_saved_window CHECK (
        last_saved_at IS NULL OR first_saved_at IS NULL OR last_saved_at >= first_saved_at
    ),
    CONSTRAINT ck_submission_exam_submission_status CHECK (
        submission_status IN (
            'DRAFT',
            'IN_PROGRESS',
            'SUBMITTED',
            'AUTO_SUBMITTED',
            'FORCE_SEALED',
            'EXPIRED_SEALED',
            'VOIDED'
        )
    ),
    CONSTRAINT ck_submission_exam_submission_seal_reason CHECK (
        seal_reason IS NULL OR seal_reason IN (
            'STUDENT_SUBMIT',
            'TIME_EXPIRED',
            'PROCTOR_FORCE_CLOSE',
            'ADMIN_FORCE_CLOSE',
            'SYSTEM_RECOVERY_SEAL'
        )
    ),
    CONSTRAINT fk_submission_exam_submission_exam_session FOREIGN KEY (exam_session_id)
        REFERENCES delivery.exam_session(exam_session_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_submission_exam_submission_generated_exam_instance FOREIGN KEY (generated_exam_instance_id)
        REFERENCES delivery.generated_exam_instance(generated_exam_instance_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_submission_exam_submission_created_by FOREIGN KEY (created_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

COMMENT ON TABLE submission.exam_submission IS
    'Official submission container for one exam_session and one generated_exam_instance.';

CREATE INDEX IF NOT EXISTS idx_submission_exam_submission_exam_session_id
    ON submission.exam_submission (exam_session_id);

CREATE INDEX IF NOT EXISTS idx_submission_exam_submission_generated_exam_instance_id
    ON submission.exam_submission (generated_exam_instance_id);

CREATE INDEX IF NOT EXISTS idx_submission_exam_submission_submission_status
    ON submission.exam_submission (submission_status);

CREATE INDEX IF NOT EXISTS idx_submission_exam_submission_last_saved_at
    ON submission.exam_submission (last_saved_at);

CREATE INDEX IF NOT EXISTS idx_submission_exam_submission_sealed_at
    ON submission.exam_submission (sealed_at);

CREATE INDEX IF NOT EXISTS idx_submission_exam_submission_created_by
    ON submission.exam_submission (created_by);

-- Phase style: app role starts with DML, hardening revokes are applied in later phases.
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE submission.exam_submission TO exam_sys_app;
GRANT SELECT ON TABLE submission.exam_submission TO exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA submission TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA submission TO exam_sys_readonly;