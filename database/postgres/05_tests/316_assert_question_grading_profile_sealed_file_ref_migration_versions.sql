-- Verifies migration metadata includes the SEALED_FILE_REF question_grading_profile contract update.

DO
$$
DECLARE
    missing_versions text := '';
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM app_meta.schema_migrations
        WHERE version = '0132_allow_sealed_file_ref_in_question_grading_profile.sql'
    ) THEN
        missing_versions := missing_versions || CASE WHEN missing_versions = '' THEN '' ELSE ', ' END || '0132_allow_sealed_file_ref_in_question_grading_profile.sql';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM app_meta.schema_migrations
        WHERE version = '0133_record_allow_sealed_file_ref_in_question_grading_profile_versions.sql'
    ) THEN
        missing_versions := missing_versions || CASE WHEN missing_versions = '' THEN '' ELSE ', ' END || '0133_record_allow_sealed_file_ref_in_question_grading_profile_versions.sql';
    END IF;

    IF missing_versions <> '' THEN
        RAISE EXCEPTION 'Missing SEALED_FILE_REF question_grading_profile migration versions: %', missing_versions;
    END IF;

    RAISE NOTICE 'PASS: SEALED_FILE_REF question_grading_profile migration versions are recorded.';
END
$$;