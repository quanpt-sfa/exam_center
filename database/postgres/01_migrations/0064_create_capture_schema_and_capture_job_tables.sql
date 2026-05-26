-- Phase 4.5 source: docs/phase_4_submission_autosave_seal_capture_pipeline.md
-- Creates capture schema and post-seal capture foundation tables.

CREATE SCHEMA IF NOT EXISTS capture;

COMMENT ON SCHEMA capture IS
    'Post-seal capture schema: asynchronous capture jobs, artifacts, datasets, dataset rows, and capture events.';

ALTER SCHEMA capture OWNER TO exam_sys_owner;

GRANT USAGE ON SCHEMA capture TO exam_sys_app;
GRANT USAGE ON SCHEMA capture TO exam_sys_readonly;
GRANT CREATE ON SCHEMA capture TO exam_sys_owner;

CREATE TABLE IF NOT EXISTS capture.capture_job (
    capture_job_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_submission_id bigint NOT NULL,
    submission_seal_id bigint NOT NULL,
    exam_session_id bigint NOT NULL,
    generated_exam_instance_id bigint NOT NULL,
    idempotency_key varchar(255) NOT NULL,
    capture_type varchar(50) NOT NULL,
    capture_status varchar(30) NOT NULL,
    requested_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz NULL,
    finished_at timestamptz NULL,
    attempt_count integer NOT NULL DEFAULT 0,
    requested_by bigint NULL,
    worker_id varchar(255) NULL,
    error_code varchar(100) NULL,
    error_message text NULL,
    metadata_json jsonb NULL,
    CONSTRAINT uq_capture_capture_job_submission_capture_type UNIQUE (exam_submission_id, capture_type),
    CONSTRAINT uq_capture_capture_job_submission_idempotency UNIQUE (exam_submission_id, idempotency_key),
    CONSTRAINT ck_capture_capture_job_attempt_count CHECK (attempt_count >= 0),
    CONSTRAINT ck_capture_capture_job_finished_started CHECK (
        finished_at IS NULL OR started_at IS NOT NULL
    ),
    CONSTRAINT ck_capture_capture_job_finished_after_started CHECK (
        finished_at IS NULL OR finished_at >= started_at
    ),
    CONSTRAINT ck_capture_capture_job_type CHECK (
        capture_type IN (
            'SQL_QUERY_TEXT_ONLY',
            'SQL_EXECUTION_PREP',
            'STUDENT_DATABASE_SNAPSHOT',
            'MISA_DATABASE_SNAPSHOT',
            'AMIS_API_RAW_PULL',
            'AMIS_API_NORMALIZED_PULL',
            'FILE_ARTIFACT',
            'OTHER'
        )
    ),
    CONSTRAINT ck_capture_capture_job_status CHECK (
        capture_status IN (
            'QUEUED',
            'RUNNING',
            'COMPLETED',
            'FAILED',
            'CANCELLED',
            'SKIPPED'
        )
    ),
    CONSTRAINT fk_capture_capture_job_exam_submission FOREIGN KEY (exam_submission_id)
        REFERENCES submission.exam_submission(exam_submission_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_capture_capture_job_submission_seal FOREIGN KEY (submission_seal_id)
        REFERENCES submission.submission_seal(submission_seal_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_capture_capture_job_exam_session FOREIGN KEY (exam_session_id)
        REFERENCES delivery.exam_session(exam_session_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_capture_capture_job_generated_exam_instance FOREIGN KEY (generated_exam_instance_id)
        REFERENCES delivery.generated_exam_instance(generated_exam_instance_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_capture_capture_job_requested_by FOREIGN KEY (requested_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS capture.capture_artifact (
    capture_artifact_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    capture_job_id bigint NOT NULL,
    artifact_type varchar(50) NOT NULL,
    artifact_ref text NOT NULL,
    artifact_hash char(64) NULL,
    artifact_size_bytes bigint NULL,
    content_type varchar(255) NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    metadata_json jsonb NULL,
    CONSTRAINT ck_capture_capture_artifact_size CHECK (
        artifact_size_bytes IS NULL OR artifact_size_bytes >= 0
    ),
    CONSTRAINT ck_capture_capture_artifact_type CHECK (
        artifact_type IN (
            'RAW_JSON',
            'NORMALIZED_JSON',
            'CSV',
            'PARQUET',
            'SQL_DUMP',
            'DB_BACKUP',
            'SCREENSHOT',
            'LOG',
            'OTHER'
        )
    ),
    CONSTRAINT fk_capture_capture_artifact_capture_job FOREIGN KEY (capture_job_id)
        REFERENCES capture.capture_job(capture_job_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS capture.capture_dataset (
    capture_dataset_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    capture_job_id bigint NOT NULL,
    dataset_name varchar(255) NOT NULL,
    dataset_schema_json jsonb NULL,
    row_count bigint NOT NULL DEFAULT 0,
    dataset_hash char(64) NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    metadata_json jsonb NULL,
    CONSTRAINT uq_capture_capture_dataset_job_name UNIQUE (capture_job_id, dataset_name),
    CONSTRAINT ck_capture_capture_dataset_row_count CHECK (row_count >= 0),
    CONSTRAINT fk_capture_capture_dataset_capture_job FOREIGN KEY (capture_job_id)
        REFERENCES capture.capture_job(capture_job_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS capture.capture_dataset_row (
    capture_dataset_row_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    capture_dataset_id bigint NOT NULL,
    row_no bigint NOT NULL,
    row_payload_json jsonb NOT NULL,
    row_hash char(64) NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_capture_capture_dataset_row_dataset_row_no UNIQUE (capture_dataset_id, row_no),
    CONSTRAINT ck_capture_capture_dataset_row_row_no CHECK (row_no > 0),
    CONSTRAINT fk_capture_capture_dataset_row_capture_dataset FOREIGN KEY (capture_dataset_id)
        REFERENCES capture.capture_dataset(capture_dataset_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS capture.capture_job_event (
    capture_job_event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    capture_job_id bigint NOT NULL,
    event_type varchar(100) NOT NULL,
    event_at timestamptz NOT NULL DEFAULT now(),
    actor_user_id bigint NULL,
    event_payload_json jsonb NULL,
    CONSTRAINT ck_capture_capture_job_event_type CHECK (
        event_type IN (
            'CAPTURE_QUEUED',
            'CAPTURE_STARTED',
            'CAPTURE_RETRIED',
            'CAPTURE_COMPLETED',
            'CAPTURE_FAILED',
            'CAPTURE_CANCELLED',
            'ARTIFACT_CREATED',
            'DATASET_CREATED'
        )
    ),
    CONSTRAINT fk_capture_capture_job_event_capture_job FOREIGN KEY (capture_job_id)
        REFERENCES capture.capture_job(capture_job_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_capture_capture_job_event_actor_user FOREIGN KEY (actor_user_id)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_capture_capture_job_exam_submission_id
    ON capture.capture_job (exam_submission_id);

CREATE INDEX IF NOT EXISTS idx_capture_capture_job_submission_seal_id
    ON capture.capture_job (submission_seal_id);

CREATE INDEX IF NOT EXISTS idx_capture_capture_job_exam_session_id
    ON capture.capture_job (exam_session_id);

CREATE INDEX IF NOT EXISTS idx_capture_capture_job_generated_exam_instance_id
    ON capture.capture_job (generated_exam_instance_id);

CREATE INDEX IF NOT EXISTS idx_capture_capture_job_capture_status
    ON capture.capture_job (capture_status);

CREATE INDEX IF NOT EXISTS idx_capture_capture_job_capture_type
    ON capture.capture_job (capture_type);

CREATE INDEX IF NOT EXISTS idx_capture_capture_job_requested_at
    ON capture.capture_job (requested_at);

CREATE INDEX IF NOT EXISTS idx_capture_capture_job_started_at
    ON capture.capture_job (started_at);

CREATE INDEX IF NOT EXISTS idx_capture_capture_job_finished_at
    ON capture.capture_job (finished_at);

CREATE INDEX IF NOT EXISTS idx_capture_capture_job_requested_by
    ON capture.capture_job (requested_by);

CREATE INDEX IF NOT EXISTS idx_capture_capture_artifact_capture_job_id
    ON capture.capture_artifact (capture_job_id);

CREATE INDEX IF NOT EXISTS idx_capture_capture_artifact_artifact_type
    ON capture.capture_artifact (artifact_type);

CREATE INDEX IF NOT EXISTS idx_capture_capture_artifact_created_at
    ON capture.capture_artifact (created_at);

CREATE INDEX IF NOT EXISTS idx_capture_capture_dataset_capture_job_id
    ON capture.capture_dataset (capture_job_id);

CREATE INDEX IF NOT EXISTS idx_capture_capture_dataset_dataset_name
    ON capture.capture_dataset (dataset_name);

CREATE INDEX IF NOT EXISTS idx_capture_capture_dataset_created_at
    ON capture.capture_dataset (created_at);

CREATE INDEX IF NOT EXISTS idx_capture_capture_dataset_row_capture_dataset_id
    ON capture.capture_dataset_row (capture_dataset_id);

CREATE INDEX IF NOT EXISTS idx_capture_capture_dataset_row_row_no
    ON capture.capture_dataset_row (row_no);

CREATE INDEX IF NOT EXISTS idx_capture_capture_job_event_capture_job_id
    ON capture.capture_job_event (capture_job_id);

CREATE INDEX IF NOT EXISTS idx_capture_capture_job_event_event_type
    ON capture.capture_job_event (event_type);

CREATE INDEX IF NOT EXISTS idx_capture_capture_job_event_event_at
    ON capture.capture_job_event (event_at);

CREATE INDEX IF NOT EXISTS idx_capture_capture_job_event_actor_user_id
    ON capture.capture_job_event (actor_user_id);

-- Capture tables are sensitive runtime artifacts; keep readonly off direct table access.
GRANT SELECT, INSERT, UPDATE ON TABLE capture.capture_job TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE capture.capture_artifact TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE capture.capture_dataset TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE capture.capture_dataset_row TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE capture.capture_job_event TO exam_sys_app;

REVOKE SELECT ON TABLE capture.capture_job FROM exam_sys_readonly;
REVOKE SELECT ON TABLE capture.capture_artifact FROM exam_sys_readonly;
REVOKE SELECT ON TABLE capture.capture_dataset FROM exam_sys_readonly;
REVOKE SELECT ON TABLE capture.capture_dataset_row FROM exam_sys_readonly;
REVOKE SELECT ON TABLE capture.capture_job_event FROM exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA capture TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA capture TO exam_sys_readonly;
