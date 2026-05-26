-- Phase 2.4 source: docs/phase_2_assessment_generator_pipeline.md
-- Seeds grader modules and one initial version v1 for each module.

INSERT INTO assessment.grader_module (module_code, module_name, description, status)
VALUES
    ('SQL_QUERY_GRADER', 'SQL Query Grader', 'Grades SQL query answers by semantic and result comparison.', 'ACTIVE'),
    ('SQL_DDL_GRADER', 'SQL DDL Grader', 'Grades SQL DDL statements by structural validation rules.', 'ACTIVE'),
    ('MISA_GRADER', 'MISA Grader', 'Grades MISA transaction/report artifacts.', 'ACTIVE'),
    ('AMIS_GRADER', 'AMIS Grader', 'Grades AMIS transaction/report artifacts.', 'ACTIVE'),
    ('MANUAL_RUBRIC_GRADER', 'Manual Rubric Grader', 'Manual rubric-based grading workflow.', 'ACTIVE')
ON CONFLICT (module_code) DO UPDATE
SET
    module_name = EXCLUDED.module_name,
    description = EXCLUDED.description,
    status = EXCLUDED.status;

WITH seed_versions AS (
    SELECT *
    FROM (VALUES
        ('SQL_QUERY_GRADER', 'v1', 'PYTHON', 'ACTIVE'),
        ('SQL_DDL_GRADER', 'v1', 'PYTHON', 'ACTIVE'),
        ('MISA_GRADER', 'v1', 'EXTERNAL_SERVICE', 'ACTIVE'),
        ('AMIS_GRADER', 'v1', 'EXTERNAL_SERVICE', 'ACTIVE'),
        ('MANUAL_RUBRIC_GRADER', 'v1', 'MANUAL', 'ACTIVE')
    ) AS v(module_code, version_no, runtime_type, status)
)
INSERT INTO assessment.grader_module_version (
    module_id,
    version_no,
    runtime_type,
    artifact_ref,
    status,
    released_at
)
SELECT
    gm.module_id,
    sv.version_no,
    sv.runtime_type,
    NULL,
    sv.status,
    now()
FROM seed_versions sv
JOIN assessment.grader_module gm
    ON gm.module_code = sv.module_code
ON CONFLICT (module_id, version_no) DO UPDATE
SET
    runtime_type = EXCLUDED.runtime_type,
    artifact_ref = EXCLUDED.artifact_ref,
    status = EXCLUDED.status,
    released_at = EXCLUDED.released_at;
