-- Verifies migration metadata coverage for all Phase 3.2-3.3 migrations.

DO
$$
DECLARE
    version_name text;
    missing_versions text := '';
    expected_count integer;
BEGIN
    FOREACH version_name IN ARRAY ARRAY[
        '0048_create_generated_exam_instance.sql',
        '0049_record_phase3_2_1_versions.sql',
        '0050_create_generated_exam_question_tables.sql',
        '0051_create_generated_expected_answer_table.sql',
        '0052_record_phase3_2_2_versions.sql',
        '0053_add_phase3_2_hardening_views_and_metadata.sql',
        '0054_add_phase3_final_hardening_and_integrity_views.sql',
        '0055_record_phase3_3_versions.sql'
    ]
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM app_meta.schema_migrations m
            WHERE m.version = version_name
        ) THEN
            missing_versions := missing_versions || CASE WHEN missing_versions = '' THEN '' ELSE ', ' END || version_name;
        END IF;
    END LOOP;

    IF missing_versions <> '' THEN
        RAISE EXCEPTION 'Missing migration metadata records: %', missing_versions;
    END IF;

    SELECT COUNT(*)
    INTO expected_count
    FROM app_meta.schema_migrations
    WHERE version LIKE '005%' OR version IN (
        '0048_create_generated_exam_instance.sql',
        '0049_record_phase3_2_1_versions.sql'
    );

    IF expected_count < 8 THEN
        RAISE EXCEPTION 'Expected at least 8 metadata records covering 3.2-3.3 range but found %', expected_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 3 final metadata coverage is complete for 3.2-3.3 migrations.';
END
$$;
