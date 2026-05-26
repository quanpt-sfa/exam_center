-- Phase 5.3 source: docs/phase_5a_individual_grading_runtime_design.md
-- Creates grading actual-result and expected-vs-actual comparison evidence tables.

CREATE TABLE IF NOT EXISTS grading.actual_result (
    actual_result_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    question_grading_task_id bigint NOT NULL,
    result_type varchar(50) NOT NULL,
    result_payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    result_artifact_ref text NULL,
    result_hash varchar(128) NULL,
    row_count bigint NULL,
    runtime_ms integer NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uq_gr_ar_question_task UNIQUE (question_grading_task_id),
    CONSTRAINT ck_gr_ar_result_type CHECK (
        result_type IN (
            'SQL_RESULT_SET',
            'SQL_RUNTIME_ERROR',
            'PYTHON_OUTPUT',
            'PYTHON_RUNTIME_ERROR',
            'R_OUTPUT',
            'R_RUNTIME_ERROR',
            'MISA_NORMALIZED_DATA',
            'AMIS_NORMALIZED_DATA',
            'FILE_EXTRACTED_DATA',
            'TEXT_RULE_RESULT',
            'MANUAL_INPUT',
            'OTHER'
        )
    ),
    CONSTRAINT ck_gr_ar_row_count CHECK (row_count IS NULL OR row_count >= 0),
    CONSTRAINT ck_gr_ar_runtime_ms CHECK (runtime_ms IS NULL OR runtime_ms >= 0),
    CONSTRAINT fk_gr_ar_question_task FOREIGN KEY (question_grading_task_id)
        REFERENCES grading.question_grading_task(question_grading_task_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS grading.expected_actual_comparison (
    comparison_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    question_grading_task_id bigint NOT NULL,
    generated_expected_answer_id bigint NULL,
    actual_result_id bigint NULL,
    comparison_method varchar(80) NOT NULL,
    comparison_status varchar(30) NOT NULL,
    expected_hash varchar(128) NULL,
    actual_hash varchar(128) NULL,
    comparison_payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    mismatch_summary text NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uq_gr_eac_question_task UNIQUE (question_grading_task_id),
    CONSTRAINT ck_gr_eac_comparison_method CHECK (
        comparison_method IN (
            'EXACT_RESULT_SET',
            'ORDER_INSENSITIVE_RESULT_SET',
            'NUMERIC_TOLERANCE',
            'TEXT_RULE',
            'ACCOUNTING_BALANCE_CHECK',
            'LEDGER_RECONCILIATION',
            'API_FIELD_MATCH',
            'FILE_ARTIFACT_MATCH',
            'MANUAL_RUBRIC',
            'CUSTOM'
        )
    ),
    CONSTRAINT ck_gr_eac_comparison_status CHECK (
        comparison_status IN ('MATCH', 'PARTIAL_MATCH', 'MISMATCH', 'ERROR', 'NEEDS_REVIEW')
    ),
    CONSTRAINT fk_gr_eac_question_task FOREIGN KEY (question_grading_task_id)
        REFERENCES grading.question_grading_task(question_grading_task_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_gr_eac_expected_answer FOREIGN KEY (generated_expected_answer_id)
        REFERENCES delivery.generated_expected_answer(generated_expected_answer_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_gr_eac_actual_result FOREIGN KEY (actual_result_id)
        REFERENCES grading.actual_result(actual_result_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_gr_ar_question_task_id
    ON grading.actual_result (question_grading_task_id);

CREATE INDEX IF NOT EXISTS idx_gr_ar_result_type
    ON grading.actual_result (result_type);

CREATE INDEX IF NOT EXISTS idx_gr_ar_result_hash
    ON grading.actual_result (result_hash);

CREATE INDEX IF NOT EXISTS idx_gr_ar_created_at
    ON grading.actual_result (created_at);

CREATE INDEX IF NOT EXISTS idx_gr_eac_question_task_id
    ON grading.expected_actual_comparison (question_grading_task_id);

CREATE INDEX IF NOT EXISTS idx_gr_eac_expected_answer_id
    ON grading.expected_actual_comparison (generated_expected_answer_id);

CREATE INDEX IF NOT EXISTS idx_gr_eac_actual_result_id
    ON grading.expected_actual_comparison (actual_result_id);

CREATE INDEX IF NOT EXISTS idx_gr_eac_comparison_method
    ON grading.expected_actual_comparison (comparison_method);

CREATE INDEX IF NOT EXISTS idx_gr_eac_comparison_status
    ON grading.expected_actual_comparison (comparison_status);

CREATE INDEX IF NOT EXISTS idx_gr_eac_created_at
    ON grading.expected_actual_comparison (created_at);

GRANT SELECT, INSERT, UPDATE ON TABLE grading.actual_result TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE grading.expected_actual_comparison TO exam_sys_app;

REVOKE DELETE ON TABLE grading.actual_result FROM exam_sys_app;
REVOKE DELETE ON TABLE grading.expected_actual_comparison FROM exam_sys_app;

REVOKE SELECT ON TABLE grading.actual_result FROM exam_sys_readonly;
REVOKE SELECT ON TABLE grading.expected_actual_comparison FROM exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA grading TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA grading TO exam_sys_readonly;

REVOKE ALL ON TABLE grading.actual_result FROM PUBLIC;
REVOKE ALL ON TABLE grading.expected_actual_comparison FROM PUBLIC;
