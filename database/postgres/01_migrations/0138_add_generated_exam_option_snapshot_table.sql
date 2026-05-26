-- Phase MVQ-3 source: docs/deployment_readiness/mvq3_multiple_choice_option_snapshot_note.md
-- Adds generated multiple-choice option snapshots so runtime payloads and submissions can use
-- session-stable generated option identities while grading keeps an internal authored-option mapping.

CREATE TABLE IF NOT EXISTS delivery.generated_exam_option (
    generated_exam_option_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    generated_exam_question_id bigint NOT NULL,
    original_option_id integer NOT NULL,
    option_order integer NOT NULL,
    option_label varchar(10) NOT NULL,
    rendered_option_text text NOT NULL,
    rendered_option_payload_json jsonb NULL,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_delivery_generated_exam_option_question_order UNIQUE (generated_exam_question_id, option_order),
    CONSTRAINT uq_delivery_generated_exam_option_question_original UNIQUE (generated_exam_question_id, original_option_id),
    CONSTRAINT ck_delivery_generated_exam_option_original_option_id CHECK (original_option_id > 0),
    CONSTRAINT ck_delivery_generated_exam_option_order CHECK (option_order > 0),
    CONSTRAINT ck_delivery_generated_exam_option_label CHECK (length(trim(option_label)) > 0),
    CONSTRAINT ck_delivery_generated_exam_option_text CHECK (length(trim(rendered_option_text)) > 0),
    CONSTRAINT fk_delivery_generated_exam_option_question FOREIGN KEY (generated_exam_question_id)
        REFERENCES delivery.generated_exam_question(generated_exam_question_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_exam_option_question_id
    ON delivery.generated_exam_option (generated_exam_question_id);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_exam_option_order
    ON delivery.generated_exam_option (option_order);

GRANT SELECT, INSERT, UPDATE ON TABLE delivery.generated_exam_option TO exam_sys_app;
GRANT SELECT ON TABLE delivery.generated_exam_option TO exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA delivery TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA delivery TO exam_sys_readonly;