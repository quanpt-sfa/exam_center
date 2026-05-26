-- Phase 5.4 source: docs/phase_5a_individual_grading_runtime_design.md
-- Creates question-level and submission-level scoring tables.

CREATE TABLE IF NOT EXISTS grading.question_score (
    question_score_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    question_grading_task_id bigint NOT NULL,
    exam_submission_id bigint NOT NULL,
    submission_seal_id bigint NOT NULL,
    sealed_answer_id bigint NULL,
    generated_exam_question_id bigint NULL,
    raw_score numeric(10,2) NOT NULL DEFAULT 0,
    max_score numeric(10,2) NOT NULL,
    score_percent numeric(7,4) NULL,
    score_status varchar(30) NOT NULL,
    scored_at timestamptz NOT NULL DEFAULT now(),
    scored_by_engine_id bigint NULL,
    requires_manual_review boolean NOT NULL DEFAULT false,
    feedback_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_gr_qs_question_task UNIQUE (question_grading_task_id),
    CONSTRAINT ck_gr_qs_score_status CHECK (
        score_status IN (
            'SCORED',
            'PARTIAL',
            'ZERO',
            'ERROR',
            'NEEDS_REVIEW',
            'MANUAL_OVERRIDE',
            'VOIDED'
        )
    ),
    CONSTRAINT ck_gr_qs_raw_score_non_negative CHECK (raw_score >= 0),
    CONSTRAINT ck_gr_qs_max_score_positive CHECK (max_score > 0),
    CONSTRAINT ck_gr_qs_raw_not_exceed_max CHECK (
        raw_score <= max_score OR score_status = 'MANUAL_OVERRIDE'
    ),
    CONSTRAINT ck_gr_qs_score_percent_non_negative CHECK (
        score_percent IS NULL OR score_percent >= 0
    ),
    CONSTRAINT ck_gr_qs_updated_at CHECK (
        updated_at IS NULL OR updated_at >= created_at
    ),
    CONSTRAINT fk_gr_qs_question_task FOREIGN KEY (question_grading_task_id)
        REFERENCES grading.question_grading_task(question_grading_task_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_gr_qs_exam_submission FOREIGN KEY (exam_submission_id)
        REFERENCES submission.exam_submission(exam_submission_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_gr_qs_submission_seal FOREIGN KEY (submission_seal_id)
        REFERENCES submission.submission_seal(submission_seal_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_gr_qs_sealed_answer FOREIGN KEY (sealed_answer_id)
        REFERENCES submission.sealed_answer(sealed_answer_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_gr_qs_generated_question FOREIGN KEY (generated_exam_question_id)
        REFERENCES delivery.generated_exam_question(generated_exam_question_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_gr_qs_scored_engine FOREIGN KEY (scored_by_engine_id)
        REFERENCES grading.grading_engine(grading_engine_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS grading.submission_score (
    submission_score_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    grading_job_id bigint NOT NULL,
    exam_submission_id bigint NOT NULL,
    submission_seal_id bigint NOT NULL,
    score_version_no integer NOT NULL DEFAULT 1,
    is_current boolean NOT NULL DEFAULT true,
    total_raw_score numeric(10,2) NOT NULL DEFAULT 0,
    total_max_score numeric(10,2) NOT NULL DEFAULT 0,
    final_score numeric(10,2) NULL,
    score_status varchar(30) NOT NULL DEFAULT 'DRAFT',
    scored_at timestamptz NOT NULL DEFAULT now(),
    finalized_at timestamptz NULL,
    finalized_by bigint NULL,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_gr_ss_submission_seal_version UNIQUE (submission_seal_id, score_version_no),
    CONSTRAINT ck_gr_ss_score_status CHECK (
        score_status IN ('DRAFT', 'COMPUTED', 'NEEDS_REVIEW', 'FINALIZED', 'VOIDED')
    ),
    CONSTRAINT ck_gr_ss_version_positive CHECK (score_version_no > 0),
    CONSTRAINT ck_gr_ss_total_raw_non_negative CHECK (total_raw_score >= 0),
    CONSTRAINT ck_gr_ss_total_max_non_negative CHECK (total_max_score >= 0),
    CONSTRAINT ck_gr_ss_final_score_non_negative CHECK (
        final_score IS NULL OR final_score >= 0
    ),
    CONSTRAINT ck_gr_ss_finalized_at_requires_status CHECK (
        finalized_at IS NULL OR score_status = 'FINALIZED'
    ),
    CONSTRAINT ck_gr_ss_updated_at CHECK (
        updated_at IS NULL OR updated_at >= created_at
    ),
    CONSTRAINT fk_gr_ss_grading_job FOREIGN KEY (grading_job_id)
        REFERENCES grading.grading_job(grading_job_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_gr_ss_exam_submission FOREIGN KEY (exam_submission_id)
        REFERENCES submission.exam_submission(exam_submission_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_gr_ss_submission_seal FOREIGN KEY (submission_seal_id)
        REFERENCES submission.submission_seal(submission_seal_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_gr_ss_finalized_by FOREIGN KEY (finalized_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_gr_ss_current_submission_seal
    ON grading.submission_score (submission_seal_id)
    WHERE is_current = true AND score_status <> 'VOIDED';

CREATE INDEX IF NOT EXISTS idx_gr_qs_question_task_id
    ON grading.question_score (question_grading_task_id);

CREATE INDEX IF NOT EXISTS idx_gr_qs_exam_submission_id
    ON grading.question_score (exam_submission_id);

CREATE INDEX IF NOT EXISTS idx_gr_qs_submission_seal_id
    ON grading.question_score (submission_seal_id);

CREATE INDEX IF NOT EXISTS idx_gr_qs_sealed_answer_id
    ON grading.question_score (sealed_answer_id);

CREATE INDEX IF NOT EXISTS idx_gr_qs_generated_question_id
    ON grading.question_score (generated_exam_question_id);

CREATE INDEX IF NOT EXISTS idx_gr_qs_score_status
    ON grading.question_score (score_status);

CREATE INDEX IF NOT EXISTS idx_gr_qs_requires_manual_review
    ON grading.question_score (requires_manual_review);

CREATE INDEX IF NOT EXISTS idx_gr_qs_scored_at
    ON grading.question_score (scored_at);

CREATE INDEX IF NOT EXISTS idx_gr_ss_grading_job_id
    ON grading.submission_score (grading_job_id);

CREATE INDEX IF NOT EXISTS idx_gr_ss_exam_submission_id
    ON grading.submission_score (exam_submission_id);

CREATE INDEX IF NOT EXISTS idx_gr_ss_submission_seal_id
    ON grading.submission_score (submission_seal_id);

CREATE INDEX IF NOT EXISTS idx_gr_ss_score_status
    ON grading.submission_score (score_status);

CREATE INDEX IF NOT EXISTS idx_gr_ss_is_current
    ON grading.submission_score (is_current);

CREATE INDEX IF NOT EXISTS idx_gr_ss_scored_at
    ON grading.submission_score (scored_at);

CREATE INDEX IF NOT EXISTS idx_gr_ss_finalized_at
    ON grading.submission_score (finalized_at);

GRANT SELECT, INSERT, UPDATE ON TABLE grading.question_score TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE grading.submission_score TO exam_sys_app;

REVOKE DELETE ON TABLE grading.question_score FROM exam_sys_app;
REVOKE DELETE ON TABLE grading.submission_score FROM exam_sys_app;

REVOKE SELECT ON TABLE grading.question_score FROM exam_sys_readonly;
REVOKE SELECT ON TABLE grading.submission_score FROM exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA grading TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA grading TO exam_sys_readonly;

REVOKE ALL ON TABLE grading.question_score FROM PUBLIC;
REVOKE ALL ON TABLE grading.submission_score FROM PUBLIC;
