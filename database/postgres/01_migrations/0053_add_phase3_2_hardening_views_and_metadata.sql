-- Phase 3.2.3 source: docs/phase_2_assessment_generator_pipeline.md
-- Hardening, safe views, and metadata backfill for generated exam snapshots.

-- Ensure FK lookup indexes for Phase 3.2 tables (idempotent, non-duplicative).
CREATE INDEX IF NOT EXISTS idx_delivery_generated_exam_instance_exam_version_id
    ON delivery.generated_exam_instance (exam_version_id);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_exam_instance_blueprint_id
    ON delivery.generated_exam_instance (blueprint_id);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_exam_instance_generated_by
    ON delivery.generated_exam_instance (generated_by);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_exam_instance_voided_by
    ON delivery.generated_exam_instance (voided_by);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_exam_question_instance_id
    ON delivery.generated_exam_question (generated_exam_instance_id);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_exam_question_template_id
    ON delivery.generated_exam_question (question_template_id);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_exam_question_blueprint_rule_id
    ON delivery.generated_exam_question (blueprint_rule_id);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_question_parameter_question_id
    ON delivery.generated_question_parameter (generated_exam_question_id);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_question_parameter_definition_id
    ON delivery.generated_question_parameter (parameter_definition_id);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_expected_answer_question_id
    ON delivery.generated_expected_answer (generated_exam_question_id);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_expected_answer_reference_solution_id
    ON delivery.generated_expected_answer (reference_solution_id);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_expected_answer_created_by
    ON delivery.generated_expected_answer (created_by);

-- Generated snapshots are append-only operational records; avoid physical delete by app role.
REVOKE DELETE ON TABLE delivery.generated_exam_instance FROM exam_sys_app;
REVOKE DELETE ON TABLE delivery.generated_exam_question FROM exam_sys_app;
REVOKE DELETE ON TABLE delivery.generated_question_parameter FROM exam_sys_app;
REVOKE DELETE ON TABLE delivery.generated_expected_answer FROM exam_sys_app;

-- Sensitive direct table access restrictions for readonly role.
REVOKE SELECT ON TABLE delivery.generated_exam_instance FROM exam_sys_readonly;
REVOKE SELECT ON TABLE delivery.generated_exam_question FROM exam_sys_readonly;
REVOKE SELECT ON TABLE delivery.generated_question_parameter FROM exam_sys_readonly;
REVOKE SELECT ON TABLE delivery.generated_expected_answer FROM exam_sys_readonly;

CREATE OR REPLACE VIEW delivery.v_student_generated_exam AS
SELECT
    gei.generated_exam_instance_id,
    gei.exam_session_id,
    gei.generation_status,
    geq.generated_exam_question_id,
    geq.question_order,
    geq.question_code,
    geq.question_type,
    geq.rendered_question_text,
    geq.rendered_question_payload_json,
    geq.score
FROM delivery.generated_exam_instance gei
JOIN delivery.generated_exam_question geq
    ON geq.generated_exam_instance_id = gei.generated_exam_instance_id
WHERE gei.generation_status IN ('GENERATED', 'VOIDED');

COMMENT ON VIEW delivery.v_student_generated_exam IS
    'Safe student-facing generated exam view without expected answers, raw parameter snapshots, or sensitive metadata.';

CREATE OR REPLACE VIEW delivery.v_proctor_generated_exam_summary AS
SELECT
    ea.exam_sitting_id,
    ea.exam_assignment_id,
    ea.student_id,
    es.exam_session_id,
    gei.generated_exam_instance_id,
    gei.generation_status,
    gei.generated_at,
    COALESCE(gq.question_count, 0) AS question_count,
    COALESCE(gq.total_generated_score, 0::numeric) AS total_generated_score
FROM delivery.exam_session es
JOIN delivery.exam_assignment ea
    ON ea.exam_assignment_id = es.exam_assignment_id
LEFT JOIN delivery.generated_exam_instance gei
    ON gei.exam_session_id = es.exam_session_id
LEFT JOIN (
    SELECT
        generated_exam_instance_id,
        COUNT(*) AS question_count,
        SUM(score) AS total_generated_score
    FROM delivery.generated_exam_question
    GROUP BY generated_exam_instance_id
) gq
    ON gq.generated_exam_instance_id = gei.generated_exam_instance_id;

COMMENT ON VIEW delivery.v_proctor_generated_exam_summary IS
    'Safe proctor/admin generated exam status view without expected answers, raw parameter values, or solution payloads.';

CREATE OR REPLACE VIEW delivery.v_generated_exam_audit_summary AS
SELECT
    gei.generated_exam_instance_id,
    gei.exam_session_id,
    gei.exam_version_id,
    gei.blueprint_id,
    gei.generation_mode,
    gei.generation_status,
    gei.generator_name,
    gei.generator_version,
    gei.snapshot_version,
    gei.instance_hash,
    gei.generated_at,
    gei.voided_at,
    gei.voided_by
FROM delivery.generated_exam_instance gei;

COMMENT ON VIEW delivery.v_generated_exam_audit_summary IS
    'Operational generated exam audit summary without expected answers, raw parameter values, or raw metadata_json.';

GRANT SELECT ON TABLE delivery.v_student_generated_exam TO exam_sys_app;
GRANT SELECT ON TABLE delivery.v_proctor_generated_exam_summary TO exam_sys_app;
GRANT SELECT ON TABLE delivery.v_generated_exam_audit_summary TO exam_sys_app;

-- Keep broad readonly limited to audit-safe generated summary only.
REVOKE SELECT ON TABLE delivery.v_student_generated_exam FROM exam_sys_readonly;
REVOKE SELECT ON TABLE delivery.v_proctor_generated_exam_summary FROM exam_sys_readonly;
GRANT SELECT ON TABLE delivery.v_generated_exam_audit_summary TO exam_sys_readonly;

-- Ensure migration metadata includes all Phase 3.2 migrations.
INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0048_create_generated_exam_instance.sql', 'Create delivery.generated_exam_instance immutable snapshot table with constraints/indexes and hardened grants', NULL, current_user),
    ('0049_record_phase3_2_1_versions.sql', 'Record Phase 3.2.1 migration versions', NULL, current_user),
    ('0050_create_generated_exam_question_tables.sql', 'Create generated_exam_question and generated_question_parameter snapshot tables', NULL, current_user),
    ('0051_create_generated_expected_answer_table.sql', 'Create generated_expected_answer snapshot table with hardening', NULL, current_user),
    ('0052_record_phase3_2_2_versions.sql', 'Record Phase 3.2.2 migration versions', NULL, current_user),
    ('0053_add_phase3_2_hardening_views_and_metadata.sql', 'Add Phase 3.2 hardening, safe views, and metadata backfill', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
