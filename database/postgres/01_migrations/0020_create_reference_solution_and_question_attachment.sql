-- Phase 2.2 source: docs/phase_2_assessment_generator_pipeline.md
-- Creates answer-bearing reference solution table and optional question attachment table.

CREATE TABLE IF NOT EXISTS assessment.reference_solution (
    reference_solution_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    question_template_id bigint NOT NULL,
    solution_type varchar(50) NOT NULL,
    solution_payload text NULL,
    solution_payload_json jsonb NULL,
    artifact_ref text NULL,
    solution_hash char(64) NULL,
    status varchar(30) NOT NULL,
    created_by bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT ck_assessment_reference_solution_solution_type CHECK (
        solution_type IN (
            'SQL_REFERENCE_QUERY',
            'SQL_EXPECTED_RESULT_STATIC',
            'ACCOUNTING_ENTRY_RULE',
            'REPORT_VALUE_RULE',
            'MANUAL_RUBRIC',
            'EXTERNAL_GRADER_CONFIG'
        )
    ),
    CONSTRAINT ck_assessment_reference_solution_status CHECK (status IN ('DRAFT', 'ACTIVE', 'RETIRED', 'VOIDED')),
    CONSTRAINT ck_assessment_reference_solution_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at),
    CONSTRAINT fk_assessment_reference_solution_question_template FOREIGN KEY (question_template_id)
        REFERENCES assessment.question_template(question_template_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_assessment_reference_solution_created_by FOREIGN KEY (created_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS assessment.question_attachment (
    question_attachment_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    question_template_id bigint NOT NULL,
    attachment_type varchar(50) NOT NULL,
    file_ref text NOT NULL,
    content_hash char(64) NULL,
    display_name varchar(255) NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_assessment_question_attachment_template FOREIGN KEY (question_template_id)
        REFERENCES assessment.question_template(question_template_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_assessment_reference_solution_question_template_id
    ON assessment.reference_solution (question_template_id);

CREATE INDEX IF NOT EXISTS idx_assessment_reference_solution_created_by
    ON assessment.reference_solution (created_by);

CREATE INDEX IF NOT EXISTS idx_assessment_question_attachment_template_id
    ON assessment.question_attachment (question_template_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE assessment.reference_solution TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE assessment.question_attachment TO exam_sys_app;

GRANT SELECT ON TABLE assessment.question_attachment TO exam_sys_readonly;

-- Answer-bearing payload table must never be broadly readable by readonly role.
REVOKE SELECT ON TABLE assessment.reference_solution FROM exam_sys_readonly;

CREATE OR REPLACE VIEW assessment.v_question_template_summary AS
SELECT
    qt.question_template_id,
    qt.template_code,
    qt.question_type,
    qt.title,
    qt.topic_code,
    qt.skill_code,
    qt.difficulty_level,
    qt.default_score,
    qt.generator_type,
    qt.generator_version,
    qt.status,
    qt.created_by,
    qt.created_at,
    qt.updated_at
FROM assessment.question_template qt;

COMMENT ON VIEW assessment.v_question_template_summary IS
    'Safe readonly summary for question templates without answer-bearing payload fields.';

GRANT SELECT ON TABLE assessment.v_question_template_summary TO exam_sys_readonly;
GRANT SELECT ON TABLE assessment.v_question_template_summary TO exam_sys_app;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA assessment TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA assessment TO exam_sys_readonly;
