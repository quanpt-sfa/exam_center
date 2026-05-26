-- Phase 2.4 source: docs/phase_2_assessment_generator_pipeline.md
-- Creates design-time grader module and grading profile tables.

CREATE TABLE IF NOT EXISTS assessment.grader_module (
    module_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    module_code varchar(100) NOT NULL,
    module_name varchar(255) NOT NULL,
    description text NULL,
    status varchar(30) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_assessment_grader_module_module_code UNIQUE (module_code),
    CONSTRAINT ck_assessment_grader_module_status_nonempty CHECK (length(trim(status)) > 0),
    CONSTRAINT ck_assessment_grader_module_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS assessment.grader_module_version (
    module_version_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    module_id bigint NOT NULL,
    version_no varchar(50) NOT NULL,
    runtime_type varchar(50) NOT NULL,
    artifact_ref text NULL,
    status varchar(30) NOT NULL,
    released_at timestamptz NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_assessment_grader_module_version_module_version_no UNIQUE (module_id, version_no),
    CONSTRAINT ck_assessment_grader_module_version_runtime_type CHECK (
        runtime_type IN ('PYTHON', 'DOTNET', 'SQL_PROC', 'EXTERNAL_SERVICE', 'MANUAL')
    ),
    CONSTRAINT ck_assessment_grader_module_version_status_nonempty CHECK (length(trim(status)) > 0),
    CONSTRAINT ck_assessment_grader_module_version_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at),
    CONSTRAINT fk_assessment_grader_module_version_module FOREIGN KEY (module_id)
        REFERENCES assessment.grader_module(module_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS assessment.grading_profile (
    grading_profile_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_version_id bigint NOT NULL,
    question_template_id bigint NULL,
    blueprint_rule_id bigint NULL,
    module_version_id bigint NOT NULL,
    profile_code varchar(100) NOT NULL,
    profile_config_json jsonb NULL,
    status varchar(30) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_assessment_grading_profile_exam_version_profile_code UNIQUE (exam_version_id, profile_code),
    CONSTRAINT ck_assessment_grading_profile_subject_scope CHECK (
        question_template_id IS NOT NULL OR blueprint_rule_id IS NOT NULL
    ),
    CONSTRAINT ck_assessment_grading_profile_status CHECK (status IN ('DRAFT', 'ACTIVE', 'RETIRED', 'VOIDED')),
    CONSTRAINT ck_assessment_grading_profile_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at),
    CONSTRAINT fk_assessment_grading_profile_exam_version FOREIGN KEY (exam_version_id)
        REFERENCES assessment.exam_version(exam_version_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_assessment_grading_profile_question_template FOREIGN KEY (question_template_id)
        REFERENCES assessment.question_template(question_template_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_assessment_grading_profile_blueprint_rule FOREIGN KEY (blueprint_rule_id)
        REFERENCES assessment.exam_blueprint_rule(blueprint_rule_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_assessment_grading_profile_module_version FOREIGN KEY (module_version_id)
        REFERENCES assessment.grader_module_version(module_version_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_assessment_grader_module_version_module_id
    ON assessment.grader_module_version (module_id);

CREATE INDEX IF NOT EXISTS idx_assessment_grading_profile_exam_version_id
    ON assessment.grading_profile (exam_version_id);

CREATE INDEX IF NOT EXISTS idx_assessment_grading_profile_question_template_id
    ON assessment.grading_profile (question_template_id);

CREATE INDEX IF NOT EXISTS idx_assessment_grading_profile_blueprint_rule_id
    ON assessment.grading_profile (blueprint_rule_id);

CREATE INDEX IF NOT EXISTS idx_assessment_grading_profile_module_version_id
    ON assessment.grading_profile (module_version_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE assessment.grader_module TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE assessment.grader_module_version TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE assessment.grading_profile TO exam_sys_app;

GRANT SELECT ON TABLE assessment.grader_module TO exam_sys_readonly;
GRANT SELECT ON TABLE assessment.grader_module_version TO exam_sys_readonly;

-- Grading profile may contain answer-adjacent config; restrict direct readonly access.
REVOKE SELECT ON TABLE assessment.grading_profile FROM exam_sys_readonly;

CREATE OR REPLACE VIEW assessment.v_grading_profile_summary AS
SELECT
    gp.grading_profile_id,
    gp.exam_version_id,
    gp.question_template_id,
    gp.blueprint_rule_id,
    gp.module_version_id,
    gp.profile_code,
    gp.status,
    gp.created_at,
    gp.updated_at
FROM assessment.grading_profile gp;

COMMENT ON VIEW assessment.v_grading_profile_summary IS
    'Safe readonly grading profile summary without profile_config_json.';

GRANT SELECT ON TABLE assessment.v_grading_profile_summary TO exam_sys_readonly;
GRANT SELECT ON TABLE assessment.v_grading_profile_summary TO exam_sys_app;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA assessment TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA assessment TO exam_sys_readonly;
