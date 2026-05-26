-- Phase 4.2 source: docs/phase_4_submission_autosave_seal_capture_pipeline.md
-- Creates answer state and lightweight autosave metadata tables.

CREATE TABLE IF NOT EXISTS submission.answer_state (
    answer_state_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_submission_id bigint NOT NULL,
    generated_exam_question_id bigint NOT NULL,
    answer_type varchar(50) NOT NULL,
    answer_text text NULL,
    answer_payload_json jsonb NULL,
    answer_hash char(64) NULL,
    answer_length integer NULL,
    client_version integer NOT NULL DEFAULT 1,
    server_version integer NOT NULL DEFAULT 1,
    client_saved_at timestamptz NULL,
    last_saved_at timestamptz NOT NULL DEFAULT now(),
    last_saved_by_device_id bigint NULL,
    last_saved_by_station_id bigint NULL,
    answer_status varchar(30) NOT NULL,
    metadata_json jsonb NULL,
    CONSTRAINT uq_submission_answer_state_submission_question UNIQUE (exam_submission_id, generated_exam_question_id),
    CONSTRAINT ck_submission_answer_state_content_presence CHECK (
        answer_text IS NOT NULL OR answer_payload_json IS NOT NULL OR answer_hash IS NOT NULL
    ),
    CONSTRAINT ck_submission_answer_state_answer_length CHECK (
        answer_length IS NULL OR answer_length >= 0
    ),
    CONSTRAINT ck_submission_answer_state_client_version CHECK (client_version > 0),
    CONSTRAINT ck_submission_answer_state_server_version CHECK (server_version > 0),
    CONSTRAINT ck_submission_answer_state_answer_type CHECK (
        answer_type IN (
            'SQL_TEXT',
            'TEXT',
            'JSON',
            'FILE_REF',
            'ACCOUNTING_TASK',
            'API_TASK',
            'MANUAL'
        )
    ),
    CONSTRAINT ck_submission_answer_state_answer_status CHECK (
        answer_status IN (
            'DRAFT',
            'ACCEPTED',
            'LATE_ACCEPTED',
            'LATE_REJECTED',
            'REJECTED',
            'SUPERSEDED',
            'SEALED'
        )
    ),
    CONSTRAINT fk_submission_answer_state_exam_submission FOREIGN KEY (exam_submission_id)
        REFERENCES submission.exam_submission(exam_submission_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_submission_answer_state_generated_exam_question FOREIGN KEY (generated_exam_question_id)
        REFERENCES delivery.generated_exam_question(generated_exam_question_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_submission_answer_state_last_saved_by_device FOREIGN KEY (last_saved_by_device_id)
        REFERENCES facility.device(device_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_submission_answer_state_last_saved_by_station FOREIGN KEY (last_saved_by_station_id)
        REFERENCES facility.lab_station(station_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS submission.answer_save_batch (
    answer_save_batch_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_submission_id bigint NOT NULL,
    idempotency_key varchar(255) NOT NULL,
    client_sequence_no bigint NULL,
    client_saved_at timestamptz NULL,
    server_received_at timestamptz NOT NULL DEFAULT now(),
    device_id bigint NULL,
    station_id bigint NULL,
    batch_status varchar(30) NOT NULL,
    accepted_item_count integer NOT NULL DEFAULT 0,
    rejected_item_count integer NOT NULL DEFAULT 0,
    metadata_json jsonb NULL,
    CONSTRAINT uq_submission_answer_save_batch_submission_idempotency UNIQUE (exam_submission_id, idempotency_key),
    CONSTRAINT ck_submission_answer_save_batch_accepted_item_count CHECK (accepted_item_count >= 0),
    CONSTRAINT ck_submission_answer_save_batch_rejected_item_count CHECK (rejected_item_count >= 0),
    CONSTRAINT ck_submission_answer_save_batch_status CHECK (
        batch_status IN (
            'RECEIVED',
            'APPLIED',
            'PARTIALLY_APPLIED',
            'DUPLICATE',
            'REJECTED',
            'IGNORED_AFTER_SEAL'
        )
    ),
    CONSTRAINT fk_submission_answer_save_batch_exam_submission FOREIGN KEY (exam_submission_id)
        REFERENCES submission.exam_submission(exam_submission_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_submission_answer_save_batch_device FOREIGN KEY (device_id)
        REFERENCES facility.device(device_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_submission_answer_save_batch_station FOREIGN KEY (station_id)
        REFERENCES facility.lab_station(station_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS submission.answer_save_item (
    answer_save_item_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    answer_save_batch_id bigint NOT NULL,
    generated_exam_question_id bigint NOT NULL,
    answer_state_id bigint NULL,
    client_version integer NULL,
    server_version integer NULL,
    answer_hash char(64) NULL,
    answer_length integer NULL,
    item_status varchar(30) NOT NULL,
    saved_at timestamptz NOT NULL DEFAULT now(),
    error_code varchar(100) NULL,
    error_message text NULL,
    CONSTRAINT uq_submission_answer_save_item_batch_question UNIQUE (answer_save_batch_id, generated_exam_question_id),
    CONSTRAINT ck_submission_answer_save_item_answer_length CHECK (
        answer_length IS NULL OR answer_length >= 0
    ),
    CONSTRAINT ck_submission_answer_save_item_status CHECK (
        item_status IN (
            'APPLIED',
            'DUPLICATE',
            'REJECTED',
            'IGNORED_AFTER_SEAL',
            'CONFLICT'
        )
    ),
    CONSTRAINT fk_submission_answer_save_item_answer_save_batch FOREIGN KEY (answer_save_batch_id)
        REFERENCES submission.answer_save_batch(answer_save_batch_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_submission_answer_save_item_generated_exam_question FOREIGN KEY (generated_exam_question_id)
        REFERENCES delivery.generated_exam_question(generated_exam_question_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_submission_answer_save_item_answer_state FOREIGN KEY (answer_state_id)
        REFERENCES submission.answer_state(answer_state_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_submission_answer_state_exam_submission_id
    ON submission.answer_state (exam_submission_id);

CREATE INDEX IF NOT EXISTS idx_submission_answer_state_generated_exam_question_id
    ON submission.answer_state (generated_exam_question_id);

CREATE INDEX IF NOT EXISTS idx_submission_answer_state_last_saved_at
    ON submission.answer_state (last_saved_at);

CREATE INDEX IF NOT EXISTS idx_submission_answer_state_last_saved_by_device_id
    ON submission.answer_state (last_saved_by_device_id);

CREATE INDEX IF NOT EXISTS idx_submission_answer_state_last_saved_by_station_id
    ON submission.answer_state (last_saved_by_station_id);

CREATE INDEX IF NOT EXISTS idx_submission_answer_state_answer_status
    ON submission.answer_state (answer_status);

CREATE INDEX IF NOT EXISTS idx_submission_answer_save_batch_exam_submission_id
    ON submission.answer_save_batch (exam_submission_id);

CREATE INDEX IF NOT EXISTS idx_submission_answer_save_batch_server_received_at
    ON submission.answer_save_batch (server_received_at);

CREATE INDEX IF NOT EXISTS idx_submission_answer_save_batch_device_id
    ON submission.answer_save_batch (device_id);

CREATE INDEX IF NOT EXISTS idx_submission_answer_save_batch_station_id
    ON submission.answer_save_batch (station_id);

CREATE INDEX IF NOT EXISTS idx_submission_answer_save_batch_batch_status
    ON submission.answer_save_batch (batch_status);

CREATE INDEX IF NOT EXISTS idx_submission_answer_save_item_answer_save_batch_id
    ON submission.answer_save_item (answer_save_batch_id);

CREATE INDEX IF NOT EXISTS idx_submission_answer_save_item_generated_exam_question_id
    ON submission.answer_save_item (generated_exam_question_id);

CREATE INDEX IF NOT EXISTS idx_submission_answer_save_item_answer_state_id
    ON submission.answer_save_item (answer_state_id);

CREATE INDEX IF NOT EXISTS idx_submission_answer_save_item_item_status
    ON submission.answer_save_item (item_status);

CREATE INDEX IF NOT EXISTS idx_submission_answer_save_item_saved_at
    ON submission.answer_save_item (saved_at);

-- Sensitive runtime tables: app role can read/write without DELETE; readonly direct SELECT is blocked.
GRANT SELECT, INSERT, UPDATE ON TABLE submission.answer_state TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE submission.answer_save_batch TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE submission.answer_save_item TO exam_sys_app;

REVOKE SELECT ON TABLE submission.answer_state FROM exam_sys_readonly;
REVOKE SELECT ON TABLE submission.answer_save_batch FROM exam_sys_readonly;
REVOKE SELECT ON TABLE submission.answer_save_item FROM exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA submission TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA submission TO exam_sys_readonly;
