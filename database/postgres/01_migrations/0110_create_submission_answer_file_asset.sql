-- Student answer file attachment foundation.
-- Stores metadata only; file bytes remain outside PostgreSQL.

CREATE TABLE IF NOT EXISTS submission.answer_file_asset (
    answer_file_asset_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_submission_id bigint NOT NULL,
    generated_exam_question_id bigint NOT NULL,
    answer_state_id bigint NULL,
    submission_seal_id bigint NULL,
    sealed_answer_id bigint NULL,
    original_filename varchar(500) NOT NULL,
    stored_filename varchar(500) NOT NULL,
    internal_storage_key text NOT NULL,
    mime_type varchar(255) NOT NULL,
    file_size_bytes bigint NOT NULL,
    sha256_hash char(64) NOT NULL,
    asset_status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    uploaded_at timestamptz NOT NULL DEFAULT now(),
    uploaded_by bigint NULL,
    superseded_at timestamptz NULL,
    superseded_by bigint NULL,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT ck_submission_afa_file_size_bytes CHECK (
        file_size_bytes > 0
    ),
    CONSTRAINT ck_submission_afa_sha256_length CHECK (
        length(sha256_hash) = 64
    ),
    CONSTRAINT ck_submission_afa_asset_status CHECK (
        asset_status IN ('ACTIVE', 'SUPERSEDED', 'SEALED', 'VOIDED', 'REJECTED')
    ),
    CONSTRAINT ck_submission_afa_superseded_at CHECK (
        superseded_at IS NULL OR superseded_at >= uploaded_at
    ),
    CONSTRAINT fk_submission_afa_exam_submission FOREIGN KEY (exam_submission_id)
        REFERENCES submission.exam_submission(exam_submission_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_submission_afa_generated_exam_question FOREIGN KEY (generated_exam_question_id)
        REFERENCES delivery.generated_exam_question(generated_exam_question_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_submission_afa_answer_state FOREIGN KEY (answer_state_id)
        REFERENCES submission.answer_state(answer_state_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_submission_afa_submission_seal FOREIGN KEY (submission_seal_id)
        REFERENCES submission.submission_seal(submission_seal_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_submission_afa_sealed_answer FOREIGN KEY (sealed_answer_id)
        REFERENCES submission.sealed_answer(sealed_answer_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_submission_afa_uploaded_by FOREIGN KEY (uploaded_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_submission_afa_superseded_by FOREIGN KEY (superseded_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

COMMENT ON TABLE submission.answer_file_asset IS
    'Student-submitted answer file metadata and audit trail. Raw file bytes are stored outside PostgreSQL.';

CREATE INDEX IF NOT EXISTS idx_submission_afa_exam_submission_id
    ON submission.answer_file_asset (exam_submission_id);

CREATE INDEX IF NOT EXISTS idx_submission_afa_generated_exam_question_id
    ON submission.answer_file_asset (generated_exam_question_id);

CREATE INDEX IF NOT EXISTS idx_submission_afa_answer_state_id
    ON submission.answer_file_asset (answer_state_id);

CREATE INDEX IF NOT EXISTS idx_submission_afa_submission_seal_id
    ON submission.answer_file_asset (submission_seal_id);

CREATE INDEX IF NOT EXISTS idx_submission_afa_sealed_answer_id
    ON submission.answer_file_asset (sealed_answer_id);

CREATE INDEX IF NOT EXISTS idx_submission_afa_sha256_hash
    ON submission.answer_file_asset (sha256_hash);

CREATE INDEX IF NOT EXISTS idx_submission_afa_asset_status
    ON submission.answer_file_asset (asset_status);

CREATE INDEX IF NOT EXISTS idx_submission_afa_uploaded_at
    ON submission.answer_file_asset (uploaded_at);

CREATE UNIQUE INDEX IF NOT EXISTS ux_submission_afa_one_active_per_submission_question
    ON submission.answer_file_asset (exam_submission_id, generated_exam_question_id)
    WHERE asset_status = 'ACTIVE';

CREATE OR REPLACE VIEW submission.v_answer_file_asset_summary AS
SELECT
    answer_file_asset_id,
    exam_submission_id,
    generated_exam_question_id,
    answer_state_id,
    submission_seal_id,
    sealed_answer_id,
    original_filename,
    mime_type,
    file_size_bytes,
    sha256_hash,
    asset_status,
    uploaded_at,
    uploaded_by,
    superseded_at,
    superseded_by
FROM submission.answer_file_asset;

COMMENT ON VIEW submission.v_answer_file_asset_summary IS
    'Safe summary of student answer file assets without storage key or stored filename.';

GRANT SELECT, INSERT, UPDATE ON TABLE submission.answer_file_asset TO exam_sys_app;
REVOKE DELETE ON TABLE submission.answer_file_asset FROM exam_sys_app;

REVOKE SELECT ON TABLE submission.answer_file_asset FROM exam_sys_readonly;

GRANT SELECT ON TABLE submission.v_answer_file_asset_summary TO exam_sys_app;
GRANT SELECT ON TABLE submission.v_answer_file_asset_summary TO exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA submission TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA submission TO exam_sys_readonly;

