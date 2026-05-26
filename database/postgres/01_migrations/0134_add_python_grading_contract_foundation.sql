ALTER TABLE assessment.question_template
    DROP CONSTRAINT IF EXISTS ck_assessment_question_template_question_type;

ALTER TABLE assessment.question_template
    ADD CONSTRAINT ck_assessment_question_template_question_type CHECK (
        question_type IN (
            'SQL_QUERY',
            'SQL_DDL',
            'SQL_PROCEDURE',
            'MISA_TRANSACTION',
            'MISA_REPORT',
            'AMIS_REPORT',
            'MANUAL_TEXT',
            'FILE_UPLOAD',
            'PYTHON_FUNCTION'
        )
    );

ALTER TABLE delivery.generated_exam_question
    DROP CONSTRAINT IF EXISTS ck_delivery_generated_exam_question_type;

ALTER TABLE delivery.generated_exam_question
    ADD CONSTRAINT ck_delivery_generated_exam_question_type CHECK (
        question_type IN (
            'SQL_QUERY',
            'SQL_DDL',
            'MISA_TASK',
            'AMIS_TASK',
            'MULTIPLE_CHOICE',
            'TEXT',
            'FILE_UPLOAD',
            'MANUAL',
            'PYTHON_FUNCTION'
        )
    );

ALTER TABLE assessment.question_grading_profile
    DROP CONSTRAINT IF EXISTS ck_assessment_question_grading_profile_input_source;

ALTER TABLE assessment.question_grading_profile
    ADD CONSTRAINT ck_assessment_question_grading_profile_input_source CHECK (
        input_source IN (
            'SEALED_TEXT_ANSWER',
            'SEALED_JSON_ANSWER',
            'SEALED_FILE_REF',
            'STUDENT_DATABASE_CAPTURE',
            'MISA_DATABASE_CAPTURE',
            'AMIS_API_CAPTURE',
            'FILE_ARTIFACT_CAPTURE',
            'MANUAL'
        )
    );

ALTER TABLE assessment.question_grading_profile
    DROP CONSTRAINT IF EXISTS ck_assessment_question_grading_profile_comparison_method;

ALTER TABLE assessment.question_grading_profile
    ADD CONSTRAINT ck_assessment_question_grading_profile_comparison_method CHECK (
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
            'PYTHON_TEST_CASES',
            'CUSTOM'
        )
    );

ALTER TABLE grading.expected_actual_comparison
    DROP CONSTRAINT IF EXISTS ck_gr_eac_comparison_method;

ALTER TABLE grading.expected_actual_comparison
    ADD CONSTRAINT ck_gr_eac_comparison_method CHECK (
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
            'PYTHON_TEST_CASES',
            'CUSTOM'
        )
    );

CREATE TABLE IF NOT EXISTS assessment.python_test_case (
    python_test_case_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    question_template_id bigint NOT NULL,
    case_name varchar(150) NULL,
    case_description text NULL,
    visibility varchar(20) NOT NULL,
    input_payload_json jsonb NOT NULL,
    expected_output_json jsonb NOT NULL,
    comparison_mode varchar(50) NOT NULL,
    weight numeric(10,4) NOT NULL DEFAULT 1,
    timeout_override_seconds integer NULL,
    max_output_bytes_override integer NULL,
    display_order integer NOT NULL DEFAULT 1,
    is_active boolean NOT NULL DEFAULT true,
    feedback_on_failure text NULL,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_assessment_python_test_case_question_order UNIQUE (question_template_id, display_order),
    CONSTRAINT ck_assessment_python_test_case_visibility CHECK (
        visibility IN ('PUBLIC', 'HIDDEN')
    ),
    CONSTRAINT ck_assessment_python_test_case_comparison_mode CHECK (
        comparison_mode IN (
            'EXACT_JSON',
            'NUMERIC_TOLERANCE',
            'UNORDERED_JSON_ARRAY',
            'STRING_NORMALIZED'
        )
    ),
    CONSTRAINT ck_assessment_python_test_case_weight_non_negative CHECK (weight >= 0),
    CONSTRAINT ck_assessment_python_test_case_display_order_positive CHECK (display_order > 0),
    CONSTRAINT ck_assessment_python_test_case_timeout_positive CHECK (
        timeout_override_seconds IS NULL OR timeout_override_seconds > 0
    ),
    CONSTRAINT ck_assessment_python_test_case_max_output_positive CHECK (
        max_output_bytes_override IS NULL OR max_output_bytes_override > 0
    ),
    CONSTRAINT ck_assessment_python_test_case_updated_at CHECK (
        updated_at IS NULL OR updated_at >= created_at
    ),
    CONSTRAINT fk_assessment_python_test_case_question_template FOREIGN KEY (question_template_id)
        REFERENCES assessment.question_template(question_template_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_assessment_python_test_case_question_template_id
    ON assessment.python_test_case (question_template_id);

CREATE INDEX IF NOT EXISTS idx_assessment_python_test_case_active_order
    ON assessment.python_test_case (question_template_id, is_active, display_order);

CREATE INDEX IF NOT EXISTS idx_assessment_python_test_case_visibility
    ON assessment.python_test_case (visibility);

COMMENT ON TABLE assessment.python_test_case IS
    'Python function grading test-case contract for future sandboxed auto-grading. Hidden cases must never be exposed to student runtime.';

GRANT SELECT, INSERT, UPDATE ON TABLE assessment.python_test_case TO exam_sys_app;
REVOKE DELETE ON TABLE assessment.python_test_case FROM exam_sys_app;

REVOKE SELECT ON TABLE assessment.python_test_case FROM exam_sys_readonly;

REVOKE ALL ON TABLE assessment.python_test_case FROM PUBLIC;