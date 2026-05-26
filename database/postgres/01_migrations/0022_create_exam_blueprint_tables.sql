-- Phase 2.3 source: docs/phase_2_assessment_generator_pipeline.md
-- Creates blueprint and randomization design tables.

CREATE TABLE IF NOT EXISTS assessment.exam_blueprint (
    blueprint_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_version_id bigint NOT NULL,
    blueprint_code varchar(100) NOT NULL,
    blueprint_name varchar(255) NOT NULL,
    total_questions integer NOT NULL,
    total_score numeric(10,2) NOT NULL,
    randomization_mode varchar(50) NOT NULL,
    status varchar(30) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_assessment_exam_blueprint_exam_version_blueprint_code UNIQUE (exam_version_id, blueprint_code),
    CONSTRAINT ck_assessment_exam_blueprint_total_questions CHECK (total_questions > 0),
    CONSTRAINT ck_assessment_exam_blueprint_total_score CHECK (total_score > 0),
    CONSTRAINT ck_assessment_exam_blueprint_randomization_mode CHECK (
        randomization_mode IN ('FIXED', 'RANDOM_FROM_BANK', 'PARAMETERIZED', 'HYBRID')
    ),
    CONSTRAINT ck_assessment_exam_blueprint_status CHECK (status IN ('DRAFT', 'ACTIVE', 'RETIRED')),
    CONSTRAINT ck_assessment_exam_blueprint_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at),
    CONSTRAINT fk_assessment_exam_blueprint_exam_version FOREIGN KEY (exam_version_id)
        REFERENCES assessment.exam_version(exam_version_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS assessment.exam_blueprint_section (
    blueprint_section_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    blueprint_id bigint NOT NULL,
    section_code varchar(100) NOT NULL,
    section_name varchar(255) NOT NULL,
    section_order integer NOT NULL,
    description text NULL,
    shuffle_within_section boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_assessment_exam_blueprint_section_blueprint_section_code UNIQUE (blueprint_id, section_code),
    CONSTRAINT uq_assessment_exam_blueprint_section_blueprint_section_order UNIQUE (blueprint_id, section_order),
    CONSTRAINT ck_assessment_exam_blueprint_section_order CHECK (section_order > 0),
    CONSTRAINT ck_assessment_exam_blueprint_section_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at),
    CONSTRAINT fk_assessment_exam_blueprint_section_blueprint FOREIGN KEY (blueprint_id)
        REFERENCES assessment.exam_blueprint(blueprint_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS assessment.exam_blueprint_rule (
    blueprint_rule_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    blueprint_section_id bigint NOT NULL,
    question_bank_id bigint NOT NULL,
    question_type varchar(50) NULL,
    topic_code varchar(100) NULL,
    skill_code varchar(100) NULL,
    difficulty_level varchar(30) NULL,
    number_of_questions integer NOT NULL,
    score_per_question numeric(10,2) NOT NULL,
    selection_strategy varchar(50) NOT NULL,
    allow_replacement boolean NOT NULL DEFAULT false,
    rule_order integer NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT ck_assessment_exam_blueprint_rule_number_of_questions CHECK (number_of_questions > 0),
    CONSTRAINT ck_assessment_exam_blueprint_rule_score_per_question CHECK (score_per_question > 0),
    CONSTRAINT ck_assessment_exam_blueprint_rule_rule_order CHECK (rule_order > 0),
    CONSTRAINT ck_assessment_exam_blueprint_rule_selection_strategy CHECK (
        selection_strategy IN ('SEEDED_RANDOM', 'FIXED_ORDER', 'BALANCED_RANDOM', 'MANUAL_LIST')
    ),
    CONSTRAINT ck_assessment_exam_blueprint_rule_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at),
    CONSTRAINT fk_assessment_exam_blueprint_rule_section FOREIGN KEY (blueprint_section_id)
        REFERENCES assessment.exam_blueprint_section(blueprint_section_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_assessment_exam_blueprint_rule_question_bank FOREIGN KEY (question_bank_id)
        REFERENCES assessment.question_bank(question_bank_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS assessment.exam_blueprint_rule_question (
    rule_question_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    blueprint_rule_id bigint NOT NULL,
    question_template_id bigint NOT NULL,
    weight numeric(10,4) NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_assessment_exam_blueprint_rule_question_rule_template UNIQUE (blueprint_rule_id, question_template_id),
    CONSTRAINT ck_assessment_exam_blueprint_rule_question_weight CHECK (weight IS NULL OR weight > 0),
    CONSTRAINT fk_assessment_exam_blueprint_rule_question_rule FOREIGN KEY (blueprint_rule_id)
        REFERENCES assessment.exam_blueprint_rule(blueprint_rule_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_assessment_exam_blueprint_rule_question_template FOREIGN KEY (question_template_id)
        REFERENCES assessment.question_template(question_template_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_assessment_exam_blueprint_exam_version_id
    ON assessment.exam_blueprint (exam_version_id);

CREATE INDEX IF NOT EXISTS idx_assessment_exam_blueprint_section_blueprint_id
    ON assessment.exam_blueprint_section (blueprint_id);

CREATE INDEX IF NOT EXISTS idx_assessment_exam_blueprint_rule_section_id
    ON assessment.exam_blueprint_rule (blueprint_section_id);

CREATE INDEX IF NOT EXISTS idx_assessment_exam_blueprint_rule_question_bank_id
    ON assessment.exam_blueprint_rule (question_bank_id);

CREATE INDEX IF NOT EXISTS idx_assessment_exam_blueprint_rule_question_rule_id
    ON assessment.exam_blueprint_rule_question (blueprint_rule_id);

CREATE INDEX IF NOT EXISTS idx_assessment_exam_blueprint_rule_question_template_id
    ON assessment.exam_blueprint_rule_question (question_template_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE assessment.exam_blueprint TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE assessment.exam_blueprint_section TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE assessment.exam_blueprint_rule TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE assessment.exam_blueprint_rule_question TO exam_sys_app;

GRANT SELECT ON TABLE assessment.exam_blueprint TO exam_sys_readonly;
GRANT SELECT ON TABLE assessment.exam_blueprint_section TO exam_sys_readonly;
GRANT SELECT ON TABLE assessment.exam_blueprint_rule TO exam_sys_readonly;
GRANT SELECT ON TABLE assessment.exam_blueprint_rule_question TO exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA assessment TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA assessment TO exam_sys_readonly;
