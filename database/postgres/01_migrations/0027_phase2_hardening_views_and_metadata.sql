-- Phase 2.5 hardening
-- - Ensure safe readonly views for assessment design-time reporting
-- - Ensure sensitive answer-bearing/config tables are not directly readable by readonly
-- - Ensure FK lookup indexes are present for Phase 2
-- - Ensure migration metadata includes all Phase 2 migrations

-- Re-assert sensitive table restrictions for readonly role.
REVOKE SELECT ON TABLE assessment.reference_solution FROM exam_sys_readonly;
REVOKE SELECT ON TABLE assessment.grading_profile FROM exam_sys_readonly;

-- Ensure FK lookup indexes exist for all Phase 2 foreign keys (non-duplicative via IF NOT EXISTS).
CREATE INDEX IF NOT EXISTS idx_assessment_exam_class_section_id
    ON assessment.exam (class_section_id);

CREATE INDEX IF NOT EXISTS idx_assessment_exam_assessment_type_id
    ON assessment.exam (assessment_type_id);

CREATE INDEX IF NOT EXISTS idx_assessment_exam_created_by
    ON assessment.exam (created_by);

CREATE INDEX IF NOT EXISTS idx_assessment_exam_version_exam_id
    ON assessment.exam_version (exam_id);

CREATE INDEX IF NOT EXISTS idx_assessment_exam_version_published_by
    ON assessment.exam_version (published_by);

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

CREATE INDEX IF NOT EXISTS idx_assessment_reference_solution_question_template_id
    ON assessment.reference_solution (question_template_id);

CREATE INDEX IF NOT EXISTS idx_assessment_reference_solution_created_by
    ON assessment.reference_solution (created_by);

CREATE INDEX IF NOT EXISTS idx_assessment_question_attachment_template_id
    ON assessment.question_attachment (question_template_id);

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

-- Safe readonly view for exam version reporting.
CREATE OR REPLACE VIEW assessment.v_exam_version_summary AS
SELECT
    ev.exam_version_id,
    ev.exam_id,
    e.class_section_id,
    e.assessment_type_id,
    atp.type_code AS assessment_type_code,
    e.exam_code,
    e.exam_name,
    e.exam_status,
    ev.version_no,
    ev.version_label,
    ev.duration_seconds,
    ev.total_score,
    ev.shuffle_questions,
    ev.shuffle_options,
    ev.randomization_mode,
    ev.status,
    ev.published_at,
    ev.published_by,
    ev.created_at,
    ev.updated_at
FROM assessment.exam_version ev
JOIN assessment.exam e
    ON e.exam_id = ev.exam_id
JOIN assessment.assessment_type atp
    ON atp.assessment_type_id = e.assessment_type_id;

COMMENT ON VIEW assessment.v_exam_version_summary IS
    'Safe readonly summary view for exam versions without answer-bearing content.';

-- Safe readonly view for question templates.
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

-- Safe readonly view for exam blueprint structure.
CREATE OR REPLACE VIEW assessment.v_exam_blueprint_summary AS
SELECT
    eb.blueprint_id,
    eb.exam_version_id,
    eb.blueprint_code,
    eb.blueprint_name,
    eb.total_questions,
    eb.total_score,
    eb.randomization_mode,
    eb.status AS blueprint_status,
    ebs.blueprint_section_id,
    ebs.section_code,
    ebs.section_name,
    ebs.section_order,
    ebs.shuffle_within_section,
    ebr.blueprint_rule_id,
    ebr.question_bank_id,
    ebr.question_type,
    ebr.topic_code,
    ebr.skill_code,
    ebr.difficulty_level,
    ebr.number_of_questions,
    ebr.score_per_question,
    ebr.selection_strategy,
    ebr.allow_replacement,
    ebr.rule_order
FROM assessment.exam_blueprint eb
LEFT JOIN assessment.exam_blueprint_section ebs
    ON ebs.blueprint_id = eb.blueprint_id
LEFT JOIN assessment.exam_blueprint_rule ebr
    ON ebr.blueprint_section_id = ebs.blueprint_section_id;

COMMENT ON VIEW assessment.v_exam_blueprint_summary IS
    'Safe readonly summary for blueprint/section/rule design-time structure.';

GRANT SELECT ON TABLE assessment.v_exam_version_summary TO exam_sys_readonly;
GRANT SELECT ON TABLE assessment.v_question_template_summary TO exam_sys_readonly;
GRANT SELECT ON TABLE assessment.v_exam_blueprint_summary TO exam_sys_readonly;

GRANT SELECT ON TABLE assessment.v_exam_version_summary TO exam_sys_app;
GRANT SELECT ON TABLE assessment.v_question_template_summary TO exam_sys_app;
GRANT SELECT ON TABLE assessment.v_exam_blueprint_summary TO exam_sys_app;

-- Ensure metadata has a complete Phase 2 migration record set.
INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0015_create_assessment_schema.sql', 'Create assessment schema for Phase 2.1', NULL, current_user),
    ('0016_create_assessment_core_exam_tables.sql', 'Create assessment_type, exam, and exam_version core tables', NULL, current_user),
    ('0017_seed_assessment_types.sql', 'Seed assessment.assessment_type lookup values', NULL, current_user),
    ('0018_record_phase2_1_versions.sql', 'Record Phase 2.1 migration versions', NULL, current_user),
    ('0019_create_question_bank_and_templates.sql', 'Create question bank, templates, template-bank mapping, and parameter definitions', NULL, current_user),
    ('0020_create_reference_solution_and_question_attachment.sql', 'Create reference solution, question attachment, and safe summary view with hardened readonly access', NULL, current_user),
    ('0021_record_phase2_2_versions.sql', 'Record Phase 2.2 migration versions', NULL, current_user),
    ('0022_create_exam_blueprint_tables.sql', 'Create exam blueprint, section, rule, and rule-question tables', NULL, current_user),
    ('0023_record_phase2_3_versions.sql', 'Record Phase 2.3 migration versions', NULL, current_user),
    ('0024_create_grader_module_and_profile_tables.sql', 'Create grader_module, grader_module_version, grading_profile, and safe summary view', NULL, current_user),
    ('0025_seed_grader_modules.sql', 'Seed grader modules and initial v1 module versions', NULL, current_user),
    ('0026_record_phase2_4_versions.sql', 'Record Phase 2.4 migration versions', NULL, current_user),
    ('0027_phase2_hardening_views_and_metadata.sql', 'Apply Phase 2.5 hardening, safe views, FK index checks, and metadata backfill', NULL, current_user)
ON CONFLICT (version) DO NOTHING;