-- Phase 2.2 source: docs/phase_2_assessment_generator_pipeline.md
-- Creates question bank, template, template mapping, and parameter definition tables.

CREATE TABLE IF NOT EXISTS assessment.question_bank (
    question_bank_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    course_id bigint NULL,
    bank_code varchar(100) NOT NULL,
    bank_name varchar(255) NOT NULL,
    description text NULL,
    owner_user_id bigint NULL,
    status varchar(30) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_assessment_question_bank_bank_code UNIQUE (bank_code),
    CONSTRAINT ck_assessment_question_bank_status CHECK (status IN ('DRAFT', 'ACTIVE', 'RETIRED', 'ARCHIVED')),
    CONSTRAINT ck_assessment_question_bank_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at),
    CONSTRAINT fk_assessment_question_bank_course FOREIGN KEY (course_id)
        REFERENCES academic.course(course_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_assessment_question_bank_owner_user FOREIGN KEY (owner_user_id)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS assessment.question_template (
    question_template_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    template_code varchar(100) NOT NULL,
    question_type varchar(50) NOT NULL,
    title varchar(500) NULL,
    template_text text NOT NULL,
    topic_code varchar(100) NULL,
    skill_code varchar(100) NULL,
    difficulty_level varchar(30) NULL,
    default_score numeric(10,2) NOT NULL,
    generator_type varchar(50) NOT NULL,
    generator_version varchar(100) NULL,
    status varchar(30) NOT NULL,
    created_by bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_assessment_question_template_template_code UNIQUE (template_code),
    CONSTRAINT ck_assessment_question_template_default_score CHECK (default_score > 0),
    CONSTRAINT ck_assessment_question_template_question_type CHECK (
        question_type IN (
            'SQL_QUERY',
            'SQL_DDL',
            'SQL_PROCEDURE',
            'MISA_TRANSACTION',
            'MISA_REPORT',
            'AMIS_REPORT',
            'MANUAL_TEXT',
            'FILE_UPLOAD'
        )
    ),
    CONSTRAINT ck_assessment_question_template_generator_type CHECK (
        generator_type IN ('STATIC', 'PARAMETERIZED', 'DATASET_BASED', 'RULE_BASED', 'EXTERNAL_SOURCE_BASED')
    ),
    CONSTRAINT ck_assessment_question_template_status CHECK (status IN ('DRAFT', 'ACTIVE', 'RETIRED', 'VOIDED')),
    CONSTRAINT ck_assessment_question_template_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at),
    CONSTRAINT fk_assessment_question_template_created_by FOREIGN KEY (created_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS assessment.question_template_bank (
    question_template_bank_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    question_bank_id bigint NOT NULL,
    question_template_id bigint NOT NULL,
    added_at timestamptz NOT NULL DEFAULT now(),
    added_by bigint NULL,
    is_active boolean NOT NULL DEFAULT true,
    CONSTRAINT uq_assessment_question_template_bank_question_bank_template UNIQUE (question_bank_id, question_template_id),
    CONSTRAINT fk_assessment_question_template_bank_question_bank FOREIGN KEY (question_bank_id)
        REFERENCES assessment.question_bank(question_bank_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_assessment_question_template_bank_question_template FOREIGN KEY (question_template_id)
        REFERENCES assessment.question_template(question_template_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_assessment_question_template_bank_added_by FOREIGN KEY (added_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS assessment.question_parameter_definition (
    parameter_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    question_template_id bigint NOT NULL,
    parameter_name varchar(100) NOT NULL,
    parameter_type varchar(50) NOT NULL,
    generation_rule_json jsonb NOT NULL,
    default_value_json jsonb NULL,
    is_required boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_assessment_question_parameter_definition_template_parameter UNIQUE (question_template_id, parameter_name),
    CONSTRAINT ck_assessment_question_parameter_definition_parameter_type CHECK (
        parameter_type IN ('STRING', 'INTEGER', 'DECIMAL', 'DATE', 'BOOLEAN', 'ENUM', 'JSON')
    ),
    CONSTRAINT ck_assessment_question_parameter_definition_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at),
    CONSTRAINT fk_assessment_question_parameter_definition_template FOREIGN KEY (question_template_id)
        REFERENCES assessment.question_template(question_template_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_assessment_question_bank_course_id
    ON assessment.question_bank (course_id);

CREATE INDEX IF NOT EXISTS idx_assessment_question_bank_owner_user_id
    ON assessment.question_bank (owner_user_id);

CREATE INDEX IF NOT EXISTS idx_assessment_question_template_created_by
    ON assessment.question_template (created_by);

CREATE INDEX IF NOT EXISTS idx_assessment_question_template_bank_question_bank_id
    ON assessment.question_template_bank (question_bank_id);

CREATE INDEX IF NOT EXISTS idx_assessment_question_template_bank_question_template_id
    ON assessment.question_template_bank (question_template_id);

CREATE INDEX IF NOT EXISTS idx_assessment_question_template_bank_added_by
    ON assessment.question_template_bank (added_by);

CREATE INDEX IF NOT EXISTS idx_assessment_question_parameter_definition_template_id
    ON assessment.question_parameter_definition (question_template_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE assessment.question_bank TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE assessment.question_template TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE assessment.question_template_bank TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE assessment.question_parameter_definition TO exam_sys_app;

GRANT SELECT ON TABLE assessment.question_bank TO exam_sys_readonly;
GRANT SELECT ON TABLE assessment.question_template TO exam_sys_readonly;
GRANT SELECT ON TABLE assessment.question_template_bank TO exam_sys_readonly;
GRANT SELECT ON TABLE assessment.question_parameter_definition TO exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA assessment TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA assessment TO exam_sys_readonly;
