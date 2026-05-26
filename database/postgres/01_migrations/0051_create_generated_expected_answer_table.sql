-- Phase 3.2.2 source: docs/phase_2_assessment_generator_pipeline.md
-- Creates generated expected answer snapshot table for grading-by-snapshot later phases.

CREATE TABLE IF NOT EXISTS delivery.generated_expected_answer (
    generated_expected_answer_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    generated_exam_question_id bigint NOT NULL,
    reference_solution_id bigint NULL,
    answer_order integer NOT NULL DEFAULT 1,
    solution_type varchar(50) NOT NULL,
    expected_payload text NULL,
    expected_payload_json jsonb NULL,
    expected_hash char(64) NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by bigint NULL,
    metadata_json jsonb NULL,
    CONSTRAINT uq_delivery_generated_expected_answer_question_order UNIQUE (generated_exam_question_id, answer_order),
    CONSTRAINT ck_delivery_generated_expected_answer_order CHECK (answer_order > 0),
    CONSTRAINT ck_delivery_generated_expected_answer_payload CHECK (
        expected_payload IS NOT NULL OR expected_payload_json IS NOT NULL OR expected_hash IS NOT NULL
    ),
    CONSTRAINT ck_delivery_generated_expected_answer_solution_type CHECK (
        solution_type IN (
            'SQL_RESULT',
            'SQL_TEXT',
            'ACCOUNTING_REPORT',
            'API_NORMALIZED_DATA',
            'RUBRIC',
            'MANUAL',
            'OTHER'
        )
    ),
    CONSTRAINT fk_delivery_generated_expected_answer_question FOREIGN KEY (generated_exam_question_id)
        REFERENCES delivery.generated_exam_question(generated_exam_question_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_generated_expected_answer_reference_solution FOREIGN KEY (reference_solution_id)
        REFERENCES assessment.reference_solution(reference_solution_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_delivery_generated_expected_answer_created_by FOREIGN KEY (created_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_expected_answer_question_id
    ON delivery.generated_expected_answer (generated_exam_question_id);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_expected_answer_reference_solution_id
    ON delivery.generated_expected_answer (reference_solution_id);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_expected_answer_solution_type
    ON delivery.generated_expected_answer (solution_type);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_expected_answer_created_by
    ON delivery.generated_expected_answer (created_by);

GRANT SELECT, INSERT, UPDATE ON TABLE delivery.generated_expected_answer TO exam_sys_app;

-- Expected answer snapshots are highly sensitive and must not be broadly readable.
REVOKE SELECT ON TABLE delivery.generated_expected_answer FROM exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA delivery TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA delivery TO exam_sys_readonly;
