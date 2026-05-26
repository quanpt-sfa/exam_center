-- Phase 5.2 source: docs/phase_5a_individual_grading_runtime_design.md
-- Creates question-level grading dispatch table for individual grading runtime.

CREATE TABLE IF NOT EXISTS grading.question_grading_task (
    question_grading_task_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    grading_run_id bigint NOT NULL,
    grading_job_id bigint NOT NULL,
    exam_submission_id bigint NOT NULL,
    submission_seal_id bigint NOT NULL,
    sealed_answer_id bigint NULL,
    generated_exam_question_id bigint NULL,
    generated_expected_answer_id bigint NULL,
    question_grading_profile_id bigint NULL,
    grading_engine_id bigint NULL,
    input_source varchar(50) NOT NULL,
    answer_language varchar(50) NOT NULL DEFAULT 'NONE',
    requires_capture boolean NOT NULL DEFAULT false,
    capture_job_id bigint NULL,
    capture_dataset_id bigint NULL,
    capture_artifact_id bigint NULL,
    task_status varchar(30) NOT NULL DEFAULT 'QUEUED',
    max_score numeric(10,2) NULL,
    started_at timestamptz NULL,
    finished_at timestamptz NULL,
    error_code varchar(100) NULL,
    error_message text NULL,
    profile_snapshot_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    expected_snapshot_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT ck_gr_qgt_input_source CHECK (
        input_source IN (
            'SEALED_TEXT_ANSWER',
            'SEALED_JSON_ANSWER',
            'STUDENT_DATABASE_CAPTURE',
            'MISA_DATABASE_CAPTURE',
            'AMIS_API_CAPTURE',
            'FILE_ARTIFACT_CAPTURE',
            'MANUAL'
        )
    ),
    CONSTRAINT ck_gr_qgt_answer_language CHECK (
        answer_language IN ('SQL', 'PYTHON', 'R', 'TEXT', 'JSON', 'NONE', 'OTHER')
    ),
    CONSTRAINT ck_gr_qgt_task_status CHECK (
        task_status IN (
            'QUEUED',
            'RUNNING',
            'COMPLETED',
            'FAILED',
            'NEEDS_REVIEW',
            'SKIPPED',
            'WAITING_CAPTURE'
        )
    ),
    CONSTRAINT ck_gr_qgt_max_score CHECK (
        max_score IS NULL OR max_score > 0
    ),
    CONSTRAINT ck_gr_qgt_finished_started CHECK (
        finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at
    ),
    CONSTRAINT ck_gr_qgt_sealed_source_consistency CHECK (
        input_source NOT IN ('SEALED_TEXT_ANSWER', 'SEALED_JSON_ANSWER')
        OR sealed_answer_id IS NOT NULL
        OR task_status IN ('NEEDS_REVIEW', 'SKIPPED')
    ),
    CONSTRAINT ck_gr_qgt_capture_required_consistency CHECK (
        NOT requires_capture
        OR capture_job_id IS NOT NULL
        OR capture_dataset_id IS NOT NULL
        OR capture_artifact_id IS NOT NULL
        OR task_status IN ('WAITING_CAPTURE', 'NEEDS_REVIEW')
    ),
    CONSTRAINT ck_gr_qgt_capture_absent_when_not_required CHECK (
        requires_capture
        OR (
            capture_job_id IS NULL
            AND capture_dataset_id IS NULL
            AND capture_artifact_id IS NULL
        )
    ),
    CONSTRAINT ck_gr_qgt_updated_at CHECK (
        updated_at IS NULL OR updated_at >= created_at
    ),
    CONSTRAINT fk_gr_qgt_grading_run FOREIGN KEY (grading_run_id)
        REFERENCES grading.grading_run(grading_run_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_gr_qgt_grading_job FOREIGN KEY (grading_job_id)
        REFERENCES grading.grading_job(grading_job_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_gr_qgt_exam_submission FOREIGN KEY (exam_submission_id)
        REFERENCES submission.exam_submission(exam_submission_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_gr_qgt_submission_seal FOREIGN KEY (submission_seal_id)
        REFERENCES submission.submission_seal(submission_seal_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_gr_qgt_sealed_answer FOREIGN KEY (sealed_answer_id)
        REFERENCES submission.sealed_answer(sealed_answer_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_gr_qgt_generated_question FOREIGN KEY (generated_exam_question_id)
        REFERENCES delivery.generated_exam_question(generated_exam_question_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_gr_qgt_generated_expected FOREIGN KEY (generated_expected_answer_id)
        REFERENCES delivery.generated_expected_answer(generated_expected_answer_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_gr_qgt_question_profile FOREIGN KEY (question_grading_profile_id)
        REFERENCES assessment.question_grading_profile(question_grading_profile_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_gr_qgt_grading_engine FOREIGN KEY (grading_engine_id)
        REFERENCES grading.grading_engine(grading_engine_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_gr_qgt_capture_job FOREIGN KEY (capture_job_id)
        REFERENCES capture.capture_job(capture_job_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_gr_qgt_capture_dataset FOREIGN KEY (capture_dataset_id)
        REFERENCES capture.capture_dataset(capture_dataset_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_gr_qgt_capture_artifact FOREIGN KEY (capture_artifact_id)
        REFERENCES capture.capture_artifact(capture_artifact_id)
        ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_gr_qgt_run_sealed_answer
    ON grading.question_grading_task (grading_run_id, sealed_answer_id)
    WHERE sealed_answer_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_gr_qgt_run_gen_question_no_sealed
    ON grading.question_grading_task (grading_run_id, generated_exam_question_id)
    WHERE sealed_answer_id IS NULL AND generated_exam_question_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_gr_qgt_grading_run_id
    ON grading.question_grading_task (grading_run_id);

CREATE INDEX IF NOT EXISTS idx_gr_qgt_grading_job_id
    ON grading.question_grading_task (grading_job_id);

CREATE INDEX IF NOT EXISTS idx_gr_qgt_exam_submission_id
    ON grading.question_grading_task (exam_submission_id);

CREATE INDEX IF NOT EXISTS idx_gr_qgt_submission_seal_id
    ON grading.question_grading_task (submission_seal_id);

CREATE INDEX IF NOT EXISTS idx_gr_qgt_sealed_answer_id
    ON grading.question_grading_task (sealed_answer_id);

CREATE INDEX IF NOT EXISTS idx_gr_qgt_generated_question_id
    ON grading.question_grading_task (generated_exam_question_id);

CREATE INDEX IF NOT EXISTS idx_gr_qgt_generated_expected_id
    ON grading.question_grading_task (generated_expected_answer_id);

CREATE INDEX IF NOT EXISTS idx_gr_qgt_question_profile_id
    ON grading.question_grading_task (question_grading_profile_id);

CREATE INDEX IF NOT EXISTS idx_gr_qgt_grading_engine_id
    ON grading.question_grading_task (grading_engine_id);

CREATE INDEX IF NOT EXISTS idx_gr_qgt_capture_job_id
    ON grading.question_grading_task (capture_job_id);

CREATE INDEX IF NOT EXISTS idx_gr_qgt_capture_dataset_id
    ON grading.question_grading_task (capture_dataset_id);

CREATE INDEX IF NOT EXISTS idx_gr_qgt_capture_artifact_id
    ON grading.question_grading_task (capture_artifact_id);

CREATE INDEX IF NOT EXISTS idx_gr_qgt_task_status
    ON grading.question_grading_task (task_status);

CREATE INDEX IF NOT EXISTS idx_gr_qgt_input_source
    ON grading.question_grading_task (input_source);

GRANT SELECT, INSERT, UPDATE ON TABLE grading.question_grading_task TO exam_sys_app;
REVOKE DELETE ON TABLE grading.question_grading_task FROM exam_sys_app;

REVOKE SELECT ON TABLE grading.question_grading_task FROM exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA grading TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA grading TO exam_sys_readonly;

REVOKE ALL ON TABLE grading.question_grading_task FROM PUBLIC;
