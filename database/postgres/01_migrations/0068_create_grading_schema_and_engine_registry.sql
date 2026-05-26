-- Phase 4.7.1 source: docs/phase_4_7_assessment_modality_grading_profile_foundation.md
-- Creates grading schema and grading engine registry foundation.

CREATE SCHEMA IF NOT EXISTS grading;

COMMENT ON SCHEMA grading IS
'Grading configuration schema foundation for engine registry and later grading runtime phases.';

DO
$$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_owner') THEN
        ALTER SCHEMA grading OWNER TO exam_sys_owner;
        GRANT CREATE ON SCHEMA grading TO exam_sys_owner;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_app') THEN
        GRANT USAGE ON SCHEMA grading TO exam_sys_app;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_readonly') THEN
        GRANT USAGE ON SCHEMA grading TO exam_sys_readonly;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS grading.grading_engine (
    grading_engine_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    engine_code varchar(100) NOT NULL,
    engine_name varchar(255) NOT NULL,
    engine_category varchar(50) NOT NULL,
    runtime_kind varchar(50) NOT NULL,
    description text NULL,
    is_active boolean NOT NULL DEFAULT true,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_grading_engine_engine_code UNIQUE (engine_code),
    CONSTRAINT ck_grading_engine_engine_category CHECK (
        engine_category IN (
            'CODE_EXECUTION',
            'DATABASE_COMPARISON',
            'API_COMPARISON',
            'TEXT_RULE',
            'MANUAL',
            'MIXED'
        )
    ),
    CONSTRAINT ck_grading_engine_runtime_kind CHECK (
        runtime_kind IN (
            'INTERNAL_WORKER',
            'EXTERNAL_WORKER',
            'MANUAL',
            'FUTURE_EXTENSION'
        )
    ),
    CONSTRAINT ck_grading_engine_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at)
);

INSERT INTO grading.grading_engine (
    engine_code,
    engine_name,
    engine_category,
    runtime_kind,
    description,
    is_active,
    metadata_json
)
VALUES
    (
        'SQL_RESULT_COMPARATOR',
        'SQL Result Comparator',
        'CODE_EXECUTION',
        'INTERNAL_WORKER',
        'Compares SQL query execution result sets against expected snapshots.',
        true,
        '{}'::jsonb
    ),
    (
        'SQL_TEXT_RULE_CHECKER',
        'SQL Text Rule Checker',
        'TEXT_RULE',
        'INTERNAL_WORKER',
        'Evaluates SQL text-based rubric rules without full result execution.',
        true,
        '{}'::jsonb
    ),
    (
        'PYTHON_CODE_RUNNER',
        'Python Code Runner',
        'CODE_EXECUTION',
        'INTERNAL_WORKER',
        'Runs and evaluates Python code answers in controlled worker runtime.',
        true,
        '{}'::jsonb
    ),
    (
        'R_CODE_RUNNER',
        'R Code Runner',
        'CODE_EXECUTION',
        'INTERNAL_WORKER',
        'Runs and evaluates R code answers in controlled worker runtime.',
        true,
        '{}'::jsonb
    ),
    (
        'MISA_DATABASE_COMPARATOR',
        'MISA Database Comparator',
        'DATABASE_COMPARISON',
        'EXTERNAL_WORKER',
        'Compares extracted MISA database state against expected results.',
        true,
        '{}'::jsonb
    ),
    (
        'AMIS_API_DATA_COMPARATOR',
        'AMIS API Data Comparator',
        'API_COMPARISON',
        'EXTERNAL_WORKER',
        'Compares AMIS API-captured data against expected normalized output.',
        true,
        '{}'::jsonb
    ),
    (
        'FILE_ARTIFACT_COMPARATOR',
        'File Artifact Comparator',
        'MIXED',
        'EXTERNAL_WORKER',
        'Compares captured file artifacts and structured extraction outputs.',
        true,
        '{}'::jsonb
    ),
    (
        'MANUAL_RUBRIC',
        'Manual Rubric',
        'MANUAL',
        'MANUAL',
        'Manual evaluator rubric scoring engine placeholder.',
        true,
        '{}'::jsonb
    )
ON CONFLICT (engine_code)
DO UPDATE
SET
    engine_name = EXCLUDED.engine_name,
    engine_category = EXCLUDED.engine_category,
    runtime_kind = EXCLUDED.runtime_kind,
    description = EXCLUDED.description,
    is_active = EXCLUDED.is_active,
    metadata_json = EXCLUDED.metadata_json,
    updated_at = now();

DO
$$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_app') THEN
        GRANT SELECT, INSERT, UPDATE ON TABLE grading.grading_engine TO exam_sys_app;
        REVOKE DELETE ON TABLE grading.grading_engine FROM exam_sys_app;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA grading TO exam_sys_app;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_readonly') THEN
        GRANT SELECT ON TABLE grading.grading_engine TO exam_sys_readonly;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA grading TO exam_sys_readonly;
    END IF;
END
$$;
