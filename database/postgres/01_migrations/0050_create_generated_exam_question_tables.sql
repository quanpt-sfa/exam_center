-- Phase 3.2.2 source: docs/phase_2_assessment_generator_pipeline.md
-- Creates generated exam question and generated question parameter snapshot tables.

CREATE TABLE IF NOT EXISTS delivery.generated_exam_question (
    generated_exam_question_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    generated_exam_instance_id bigint NOT NULL,
    question_template_id bigint NOT NULL,
    blueprint_rule_id bigint NULL,
    question_order integer NOT NULL,
    question_code varchar(100) NULL,
    question_type varchar(50) NOT NULL,
    rendered_question_text text NOT NULL,
    rendered_question_payload_json jsonb NULL,
    score numeric(10,2) NOT NULL,
    metadata_json jsonb NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_delivery_generated_exam_question_instance_order UNIQUE (generated_exam_instance_id, question_order),
    CONSTRAINT ck_delivery_generated_exam_question_order CHECK (question_order > 0),
    CONSTRAINT ck_delivery_generated_exam_question_score CHECK (score > 0),
    CONSTRAINT ck_delivery_generated_exam_question_type CHECK (
        question_type IN (
            'SQL_QUERY',
            'SQL_DDL',
            'MISA_TASK',
            'AMIS_TASK',
            'MULTIPLE_CHOICE',
            'TEXT',
            'FILE_UPLOAD',
            'MANUAL'
        )
    ),
    CONSTRAINT fk_delivery_generated_exam_question_instance FOREIGN KEY (generated_exam_instance_id)
        REFERENCES delivery.generated_exam_instance(generated_exam_instance_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_generated_exam_question_template FOREIGN KEY (question_template_id)
        REFERENCES assessment.question_template(question_template_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_generated_exam_question_blueprint_rule FOREIGN KEY (blueprint_rule_id)
        REFERENCES assessment.exam_blueprint_rule(blueprint_rule_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS delivery.generated_question_parameter (
    generated_parameter_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    generated_exam_question_id bigint NOT NULL,
    parameter_definition_id bigint NULL,
    parameter_name varchar(100) NOT NULL,
    parameter_type varchar(50) NULL,
    parameter_value_json jsonb NOT NULL,
    parameter_display_value text NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_delivery_generated_question_parameter_question_name UNIQUE (generated_exam_question_id, parameter_name),
    CONSTRAINT fk_delivery_generated_question_parameter_question FOREIGN KEY (generated_exam_question_id)
        REFERENCES delivery.generated_exam_question(generated_exam_question_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_generated_question_parameter_definition FOREIGN KEY (parameter_definition_id)
        REFERENCES assessment.question_parameter_definition(parameter_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_exam_question_instance_id
    ON delivery.generated_exam_question (generated_exam_instance_id);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_exam_question_template_id
    ON delivery.generated_exam_question (question_template_id);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_exam_question_blueprint_rule_id
    ON delivery.generated_exam_question (blueprint_rule_id);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_exam_question_order
    ON delivery.generated_exam_question (question_order);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_question_parameter_question_id
    ON delivery.generated_question_parameter (generated_exam_question_id);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_question_parameter_definition_id
    ON delivery.generated_question_parameter (parameter_definition_id);

GRANT SELECT, INSERT, UPDATE ON TABLE delivery.generated_exam_question TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE delivery.generated_question_parameter TO exam_sys_app;

-- Parameter snapshots may reveal answer logic and are sensitive.
REVOKE SELECT ON TABLE delivery.generated_exam_question FROM exam_sys_readonly;
REVOKE SELECT ON TABLE delivery.generated_question_parameter FROM exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA delivery TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA delivery TO exam_sys_readonly;
