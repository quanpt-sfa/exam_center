-- Phase 5.1 source: docs/phase_5a_individual_grading_runtime_design.md
-- Creates individual grading runtime foundation tables: grading_job and grading_run.

CREATE TABLE IF NOT EXISTS grading.grading_job (
    grading_job_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_submission_id bigint NOT NULL,
    submission_seal_id bigint NOT NULL,
    exam_session_id bigint NULL,
    generated_exam_instance_id bigint NULL,
    grading_mode varchar(30) NOT NULL DEFAULT 'AUTO',
    grading_status varchar(30) NOT NULL DEFAULT 'QUEUED',
    idempotency_key varchar(200) NOT NULL,
    requested_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz NULL,
    finished_at timestamptz NULL,
    requested_by bigint NULL,
    attempt_count integer NOT NULL DEFAULT 0,
    error_code varchar(100) NULL,
    error_message text NULL,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_grading_grading_job_submission_idempotency UNIQUE (exam_submission_id, idempotency_key),
    CONSTRAINT ck_grading_grading_job_mode CHECK (
        grading_mode IN ('AUTO', 'MANUAL', 'HYBRID', 'REGRADING')
    ),
    CONSTRAINT ck_grading_grading_job_status CHECK (
        grading_status IN (
            'QUEUED',
            'RUNNING',
            'COMPLETED',
            'PARTIALLY_FAILED',
            'FAILED',
            'NEEDS_REVIEW',
            'CANCELLED'
        )
    ),
    CONSTRAINT ck_grading_grading_job_attempt_count CHECK (attempt_count >= 0),
    CONSTRAINT ck_grading_grading_job_finished_started_order CHECK (
        finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at
    ),
    CONSTRAINT ck_grading_grading_job_updated_at CHECK (
        updated_at IS NULL OR updated_at >= created_at
    ),
    CONSTRAINT fk_grading_grading_job_exam_submission FOREIGN KEY (exam_submission_id)
        REFERENCES submission.exam_submission(exam_submission_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_grading_grading_job_submission_seal FOREIGN KEY (submission_seal_id)
        REFERENCES submission.submission_seal(submission_seal_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_grading_grading_job_exam_session FOREIGN KEY (exam_session_id)
        REFERENCES delivery.exam_session(exam_session_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_grading_grading_job_generated_instance FOREIGN KEY (generated_exam_instance_id)
        REFERENCES delivery.generated_exam_instance(generated_exam_instance_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_grading_grading_job_requested_by FOREIGN KEY (requested_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS grading.grading_run (
    grading_run_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    grading_job_id bigint NOT NULL,
    run_no integer NOT NULL,
    run_status varchar(30) NOT NULL DEFAULT 'RUNNING',
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz NULL,
    worker_id varchar(150) NULL,
    engine_batch_version varchar(100) NULL,
    error_code varchar(100) NULL,
    error_message text NULL,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_grading_grading_run_job_run_no UNIQUE (grading_job_id, run_no),
    CONSTRAINT ck_grading_grading_run_status CHECK (
        run_status IN ('RUNNING', 'COMPLETED', 'PARTIALLY_FAILED', 'FAILED', 'CANCELLED')
    ),
    CONSTRAINT ck_grading_grading_run_run_no CHECK (run_no > 0),
    CONSTRAINT ck_grading_grading_run_finished_started_order CHECK (
        finished_at IS NULL OR finished_at >= started_at
    ),
    CONSTRAINT fk_grading_grading_run_grading_job FOREIGN KEY (grading_job_id)
        REFERENCES grading.grading_job(grading_job_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_grading_grading_job_exam_submission_id
    ON grading.grading_job (exam_submission_id);

CREATE INDEX IF NOT EXISTS idx_grading_grading_job_submission_seal_id
    ON grading.grading_job (submission_seal_id);

CREATE INDEX IF NOT EXISTS idx_grading_grading_job_exam_session_id
    ON grading.grading_job (exam_session_id);

CREATE INDEX IF NOT EXISTS idx_grading_grading_job_generated_instance_id
    ON grading.grading_job (generated_exam_instance_id);

CREATE INDEX IF NOT EXISTS idx_grading_grading_job_status
    ON grading.grading_job (grading_status);

CREATE INDEX IF NOT EXISTS idx_grading_grading_job_mode
    ON grading.grading_job (grading_mode);

CREATE INDEX IF NOT EXISTS idx_grading_grading_job_requested_at
    ON grading.grading_job (requested_at);

CREATE INDEX IF NOT EXISTS idx_grading_grading_run_job_id
    ON grading.grading_run (grading_job_id);

CREATE INDEX IF NOT EXISTS idx_grading_grading_run_status
    ON grading.grading_run (run_status);

CREATE INDEX IF NOT EXISTS idx_grading_grading_run_started_at
    ON grading.grading_run (started_at);

CREATE INDEX IF NOT EXISTS idx_grading_grading_run_worker_id
    ON grading.grading_run (worker_id);

GRANT SELECT, INSERT, UPDATE ON TABLE grading.grading_job TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE grading.grading_run TO exam_sys_app;

REVOKE DELETE ON TABLE grading.grading_job FROM exam_sys_app;
REVOKE DELETE ON TABLE grading.grading_run FROM exam_sys_app;

REVOKE SELECT ON TABLE grading.grading_job FROM exam_sys_readonly;
REVOKE SELECT ON TABLE grading.grading_run FROM exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA grading TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA grading TO exam_sys_readonly;

REVOKE ALL ON TABLE grading.grading_job FROM PUBLIC;
REVOKE ALL ON TABLE grading.grading_run FROM PUBLIC;
