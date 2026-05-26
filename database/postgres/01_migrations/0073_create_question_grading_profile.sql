-- Phase 4.7.3 source: docs/phase_4_7_assessment_modality_grading_profile_foundation.md
-- Creates per-question grading profile foundation for input source and grading engine mapping.

CREATE TABLE IF NOT EXISTS assessment.question_grading_profile (
    question_grading_profile_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    question_template_id bigint NOT NULL,
    exam_version_id bigint NULL,
    input_source varchar(50) NOT NULL,
    answer_language varchar(50) NOT NULL DEFAULT 'NONE',
    requires_capture boolean NOT NULL DEFAULT false,
    required_capture_type varchar(50) NULL,
    capture_profile_id bigint NULL,
    grading_engine_id bigint NOT NULL,
    comparison_method varchar(80) NOT NULL,
    timeout_seconds integer NULL,
    max_score numeric(10,2) NULL,
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT ck_assessment_question_grading_profile_input_source CHECK (
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
    CONSTRAINT ck_assessment_question_grading_profile_answer_language CHECK (
        answer_language IN ('SQL', 'PYTHON', 'R', 'TEXT', 'JSON', 'NONE', 'OTHER')
    ),
    CONSTRAINT ck_assessment_question_grading_profile_required_capture_type CHECK (
        required_capture_type IS NULL
        OR required_capture_type IN (
            'SQLSERVER_DATABASE_SNAPSHOT',
            'POSTGRES_DATABASE_SNAPSHOT',
            'MISA_DATABASE_SNAPSHOT',
            'AMIS_API_PULL',
            'FILE_UPLOAD',
            'OTHER'
        )
    ),
    CONSTRAINT ck_assessment_question_grading_profile_comparison_method CHECK (
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
    CONSTRAINT ck_assessment_question_grading_profile_status CHECK (
        status IN ('DRAFT', 'ACTIVE', 'RETIRED', 'DISABLED')
    ),
    CONSTRAINT ck_assessment_question_grading_profile_timeout_seconds CHECK (
        timeout_seconds IS NULL OR timeout_seconds > 0
    ),
    CONSTRAINT ck_assessment_question_grading_profile_max_score CHECK (
        max_score IS NULL OR max_score > 0
    ),
    CONSTRAINT ck_assessment_question_grading_profile_capture_required_source CHECK (
        NOT requires_capture
        OR input_source IN (
            'STUDENT_DATABASE_CAPTURE',
            'MISA_DATABASE_CAPTURE',
            'AMIS_API_CAPTURE',
            'FILE_ARTIFACT_CAPTURE'
        )
    ),
    CONSTRAINT ck_assessment_question_grading_profile_capture_profile_consistency CHECK (
        (requires_capture AND capture_profile_id IS NOT NULL)
        OR (NOT requires_capture AND capture_profile_id IS NULL)
    ),
    CONSTRAINT ck_assessment_question_grading_profile_capture_type_consistency CHECK (
        (requires_capture AND required_capture_type IS NOT NULL)
        OR (NOT requires_capture AND required_capture_type IS NULL)
    ),
    CONSTRAINT ck_assessment_question_grading_profile_capture_input_requires_capture CHECK (
        requires_capture
        OR input_source NOT IN (
            'STUDENT_DATABASE_CAPTURE',
            'MISA_DATABASE_CAPTURE',
            'AMIS_API_CAPTURE',
            'FILE_ARTIFACT_CAPTURE'
        )
    ),
    CONSTRAINT ck_assessment_question_grading_profile_language_source_practical CHECK (
        answer_language NOT IN ('SQL', 'PYTHON', 'R')
        OR input_source IN ('SEALED_TEXT_ANSWER', 'SEALED_JSON_ANSWER')
    ),
    CONSTRAINT ck_assessment_question_grading_profile_updated_at CHECK (
        updated_at IS NULL OR updated_at >= created_at
    ),
    CONSTRAINT fk_assessment_question_grading_profile_question_template FOREIGN KEY (question_template_id)
        REFERENCES assessment.question_template(question_template_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_assessment_question_grading_profile_exam_version FOREIGN KEY (exam_version_id)
        REFERENCES assessment.exam_version(exam_version_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_assessment_question_grading_profile_capture_profile FOREIGN KEY (capture_profile_id)
        REFERENCES capture.capture_profile(capture_profile_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_assessment_question_grading_profile_grading_engine FOREIGN KEY (grading_engine_id)
        REFERENCES grading.grading_engine(grading_engine_id)
        ON DELETE RESTRICT
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_assessment_question_grading_profile_default_per_template
    ON assessment.question_grading_profile (question_template_id)
    WHERE exam_version_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_assessment_question_grading_profile_override_per_exam_template
    ON assessment.question_grading_profile (exam_version_id, question_template_id)
    WHERE exam_version_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_assessment_question_grading_profile_question_template_id
    ON assessment.question_grading_profile (question_template_id);

CREATE INDEX IF NOT EXISTS idx_assessment_question_grading_profile_exam_version_id
    ON assessment.question_grading_profile (exam_version_id);

CREATE INDEX IF NOT EXISTS idx_assessment_question_grading_profile_capture_profile_id
    ON assessment.question_grading_profile (capture_profile_id);

CREATE INDEX IF NOT EXISTS idx_assessment_question_grading_profile_grading_engine_id
    ON assessment.question_grading_profile (grading_engine_id);

CREATE INDEX IF NOT EXISTS idx_assessment_question_grading_profile_input_source
    ON assessment.question_grading_profile (input_source);

CREATE OR REPLACE VIEW assessment.v_question_grading_profile_summary AS
SELECT
    qgp.question_grading_profile_id,
    qgp.question_template_id,
    qgp.exam_version_id,
    qgp.input_source,
    qgp.answer_language,
    qgp.requires_capture,
    qgp.required_capture_type,
    cp.profile_code AS capture_profile_code,
    ge.engine_code AS grading_engine_code,
    qgp.comparison_method,
    qgp.timeout_seconds,
    qgp.max_score,
    qgp.status,
    qgp.created_at,
    qgp.updated_at
FROM assessment.question_grading_profile qgp
LEFT JOIN capture.capture_profile cp
    ON cp.capture_profile_id = qgp.capture_profile_id
JOIN grading.grading_engine ge
    ON ge.grading_engine_id = qgp.grading_engine_id;

COMMENT ON VIEW assessment.v_question_grading_profile_summary IS
    'Safe summary of question grading profile with capture and grading engine codes, without secrets.';

GRANT SELECT, INSERT, UPDATE ON TABLE assessment.question_grading_profile TO exam_sys_app;
REVOKE DELETE ON TABLE assessment.question_grading_profile FROM exam_sys_app;

REVOKE SELECT ON TABLE assessment.question_grading_profile FROM exam_sys_readonly;

GRANT SELECT ON TABLE assessment.v_question_grading_profile_summary TO exam_sys_app;
GRANT SELECT ON TABLE assessment.v_question_grading_profile_summary TO exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA assessment TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA assessment TO exam_sys_readonly;
