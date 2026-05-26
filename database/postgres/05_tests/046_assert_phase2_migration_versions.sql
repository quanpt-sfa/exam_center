-- Verifies migration metadata includes all Phase 2 migrations.

DO
$$
DECLARE
    missing_versions text;
BEGIN
    IF to_regclass('app_meta.schema_migrations') IS NULL THEN
        RAISE EXCEPTION 'Migration metadata table app_meta.schema_migrations is missing.';
    END IF;

    SELECT string_agg(expected.version, ', ' ORDER BY expected.version)
    INTO missing_versions
    FROM (
        SELECT unnest(
            ARRAY[
                '0015_create_assessment_schema.sql',
                '0016_create_assessment_core_exam_tables.sql',
                '0017_seed_assessment_types.sql',
                '0018_record_phase2_1_versions.sql',
                '0019_create_question_bank_and_templates.sql',
                '0020_create_reference_solution_and_question_attachment.sql',
                '0021_record_phase2_2_versions.sql',
                '0022_create_exam_blueprint_tables.sql',
                '0023_record_phase2_3_versions.sql',
                '0024_create_grader_module_and_profile_tables.sql',
                '0025_seed_grader_modules.sql',
                '0026_record_phase2_4_versions.sql',
                '0027_phase2_hardening_views_and_metadata.sql'
            ]
        ) AS version
    ) expected
    LEFT JOIN app_meta.schema_migrations sm
      ON sm.version = expected.version
    WHERE sm.version IS NULL;

    IF missing_versions IS NOT NULL THEN
        RAISE EXCEPTION 'Missing Phase 2 migration version records: %', missing_versions;
    END IF;

    RAISE NOTICE 'PASS: Migration metadata includes all Phase 2 versions.';
END
$$;