-- Phase 5.5 source: docs/phase_5a_individual_grading_runtime_design.md
-- Creates manual review queue, score adjustment audit, and grading event tables.

CREATE TABLE IF NOT EXISTS grading.manual_review_queue (
    manual_review_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_submission_id bigint NOT NULL,
    submission_seal_id bigint NOT NULL,
    question_grading_task_id bigint NULL,
    question_score_id bigint NULL,
    submission_score_id bigint NULL,
    review_reason varchar(80) NOT NULL,
    review_status varchar(30) NOT NULL DEFAULT 'OPEN',
    assigned_to bigint NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz NULL,
    resolved_by bigint NULL,
    note text NULL,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NULL,
    CONSTRAINT ck_gr_mrq_review_reason CHECK (
        review_reason IN (
            'SQL_RUNTIME_ERROR',
            'PYTHON_RUNTIME_ERROR',
            'R_RUNTIME_ERROR',
            'MISSING_EXPECTED_ANSWER',
            'MISSING_CAPTURE',
            'UNSUPPORTED_QUESTION_TYPE',
            'AMBIGUOUS_RESULT',
            'MISMATCH_NEEDS_HUMAN',
            'TECHNICAL_INCIDENT',
            'STUDENT_COMPLAINT',
            'MANUAL_RUBRIC_REQUIRED',
            'OTHER'
        )
    ),
    CONSTRAINT ck_gr_mrq_review_status CHECK (
        review_status IN ('OPEN', 'ASSIGNED', 'RESOLVED', 'REJECTED', 'CANCELLED')
    ),
    CONSTRAINT ck_gr_mrq_resolved_status CHECK (
        resolved_at IS NULL OR review_status IN ('RESOLVED', 'REJECTED', 'CANCELLED')
    ),
    CONSTRAINT ck_gr_mrq_resolved_by_requires_resolved_at CHECK (
        resolved_by IS NULL OR resolved_at IS NOT NULL
    ),
    CONSTRAINT ck_gr_mrq_updated_at CHECK (
        updated_at IS NULL OR updated_at >= created_at
    ),
    CONSTRAINT fk_gr_mrq_exam_submission FOREIGN KEY (exam_submission_id)
        REFERENCES submission.exam_submission(exam_submission_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_gr_mrq_submission_seal FOREIGN KEY (submission_seal_id)
        REFERENCES submission.submission_seal(submission_seal_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_gr_mrq_question_task FOREIGN KEY (question_grading_task_id)
        REFERENCES grading.question_grading_task(question_grading_task_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_gr_mrq_question_score FOREIGN KEY (question_score_id)
        REFERENCES grading.question_score(question_score_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_gr_mrq_submission_score FOREIGN KEY (submission_score_id)
        REFERENCES grading.submission_score(submission_score_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_gr_mrq_assigned_to FOREIGN KEY (assigned_to)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_gr_mrq_resolved_by FOREIGN KEY (resolved_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS grading.score_adjustment (
    score_adjustment_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    question_score_id bigint NULL,
    submission_score_id bigint NULL,
    adjustment_type varchar(50) NOT NULL,
    old_score numeric(10,2) NULL,
    new_score numeric(10,2) NOT NULL,
    reason text NOT NULL,
    adjusted_by bigint NOT NULL,
    adjusted_at timestamptz NOT NULL DEFAULT now(),
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT ck_gr_sa_adjustment_type CHECK (
        adjustment_type IN (
            'MANUAL_OVERRIDE',
            'TECHNICAL_CORRECTION',
            'APPEAL_ADJUSTMENT',
            'POLICY_ADJUSTMENT'
        )
    ),
    CONSTRAINT ck_gr_sa_target_present CHECK (
        question_score_id IS NOT NULL OR submission_score_id IS NOT NULL
    ),
    CONSTRAINT ck_gr_sa_old_score_non_negative CHECK (
        old_score IS NULL OR old_score >= 0
    ),
    CONSTRAINT ck_gr_sa_new_score_non_negative CHECK (new_score >= 0),
    CONSTRAINT fk_gr_sa_question_score FOREIGN KEY (question_score_id)
        REFERENCES grading.question_score(question_score_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_gr_sa_submission_score FOREIGN KEY (submission_score_id)
        REFERENCES grading.submission_score(submission_score_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_gr_sa_adjusted_by FOREIGN KEY (adjusted_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS grading.grading_event (
    grading_event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    grading_job_id bigint NULL,
    grading_run_id bigint NULL,
    question_grading_task_id bigint NULL,
    event_type varchar(80) NOT NULL,
    event_at timestamptz NOT NULL DEFAULT now(),
    actor_user_id bigint NULL,
    worker_id varchar(150) NULL,
    event_payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_gr_ge_event_type CHECK (
        event_type IN (
            'JOB_QUEUED',
            'JOB_STARTED',
            'JOB_COMPLETED',
            'JOB_FAILED',
            'RUN_STARTED',
            'RUN_COMPLETED',
            'RUN_FAILED',
            'TASK_QUEUED',
            'TASK_STARTED',
            'TASK_COMPLETED',
            'TASK_FAILED',
            'COMPARISON_COMPLETED',
            'SCORE_CREATED',
            'REVIEW_CREATED',
            'SCORE_ADJUSTED',
            'OTHER'
        )
    ),
    CONSTRAINT ck_gr_ge_target_present CHECK (
        grading_job_id IS NOT NULL
        OR grading_run_id IS NOT NULL
        OR question_grading_task_id IS NOT NULL
    ),
    CONSTRAINT fk_gr_ge_grading_job FOREIGN KEY (grading_job_id)
        REFERENCES grading.grading_job(grading_job_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_gr_ge_grading_run FOREIGN KEY (grading_run_id)
        REFERENCES grading.grading_run(grading_run_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_gr_ge_question_task FOREIGN KEY (question_grading_task_id)
        REFERENCES grading.question_grading_task(question_grading_task_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_gr_ge_actor_user FOREIGN KEY (actor_user_id)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_gr_mrq_exam_submission_id
    ON grading.manual_review_queue (exam_submission_id);

CREATE INDEX IF NOT EXISTS idx_gr_mrq_submission_seal_id
    ON grading.manual_review_queue (submission_seal_id);

CREATE INDEX IF NOT EXISTS idx_gr_mrq_question_task_id
    ON grading.manual_review_queue (question_grading_task_id);

CREATE INDEX IF NOT EXISTS idx_gr_mrq_question_score_id
    ON grading.manual_review_queue (question_score_id);

CREATE INDEX IF NOT EXISTS idx_gr_mrq_submission_score_id
    ON grading.manual_review_queue (submission_score_id);

CREATE INDEX IF NOT EXISTS idx_gr_mrq_review_reason
    ON grading.manual_review_queue (review_reason);

CREATE INDEX IF NOT EXISTS idx_gr_mrq_review_status
    ON grading.manual_review_queue (review_status);

CREATE INDEX IF NOT EXISTS idx_gr_mrq_assigned_to
    ON grading.manual_review_queue (assigned_to);

CREATE INDEX IF NOT EXISTS idx_gr_mrq_created_at
    ON grading.manual_review_queue (created_at);

CREATE INDEX IF NOT EXISTS idx_gr_sa_question_score_id
    ON grading.score_adjustment (question_score_id);

CREATE INDEX IF NOT EXISTS idx_gr_sa_submission_score_id
    ON grading.score_adjustment (submission_score_id);

CREATE INDEX IF NOT EXISTS idx_gr_sa_adjustment_type
    ON grading.score_adjustment (adjustment_type);

CREATE INDEX IF NOT EXISTS idx_gr_sa_adjusted_by
    ON grading.score_adjustment (adjusted_by);

CREATE INDEX IF NOT EXISTS idx_gr_sa_adjusted_at
    ON grading.score_adjustment (adjusted_at);

CREATE INDEX IF NOT EXISTS idx_gr_ge_grading_job_id
    ON grading.grading_event (grading_job_id);

CREATE INDEX IF NOT EXISTS idx_gr_ge_grading_run_id
    ON grading.grading_event (grading_run_id);

CREATE INDEX IF NOT EXISTS idx_gr_ge_question_task_id
    ON grading.grading_event (question_grading_task_id);

CREATE INDEX IF NOT EXISTS idx_gr_ge_event_type
    ON grading.grading_event (event_type);

CREATE INDEX IF NOT EXISTS idx_gr_ge_event_at
    ON grading.grading_event (event_at);

CREATE INDEX IF NOT EXISTS idx_gr_ge_worker_id
    ON grading.grading_event (worker_id);

CREATE INDEX IF NOT EXISTS idx_gr_ge_actor_user_id
    ON grading.grading_event (actor_user_id);

GRANT SELECT, INSERT, UPDATE ON TABLE grading.manual_review_queue TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE grading.score_adjustment TO exam_sys_app;
GRANT SELECT, INSERT ON TABLE grading.grading_event TO exam_sys_app;

REVOKE DELETE ON TABLE grading.manual_review_queue FROM exam_sys_app;
REVOKE DELETE ON TABLE grading.score_adjustment FROM exam_sys_app;
REVOKE DELETE ON TABLE grading.grading_event FROM exam_sys_app;

REVOKE SELECT ON TABLE grading.manual_review_queue FROM exam_sys_readonly;
REVOKE SELECT ON TABLE grading.score_adjustment FROM exam_sys_readonly;
REVOKE SELECT ON TABLE grading.grading_event FROM exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA grading TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA grading TO exam_sys_readonly;

REVOKE ALL ON TABLE grading.manual_review_queue FROM PUBLIC;
REVOKE ALL ON TABLE grading.score_adjustment FROM PUBLIC;
REVOKE ALL ON TABLE grading.grading_event FROM PUBLIC;
