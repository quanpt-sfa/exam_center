-- Verifies migration metadata for student answer file attachment foundation is recorded.

DO
$$
DECLARE
    missing_versions text := '';
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM app_meta.schema_migrations
        WHERE version = '0110_create_submission_answer_file_asset.sql'
    ) THEN
        missing_versions := missing_versions || CASE WHEN missing_versions = '' THEN '' ELSE ', ' END || '0110_create_submission_answer_file_asset.sql';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM app_meta.schema_migrations
        WHERE version = '0111_record_submission_answer_file_asset_versions.sql'
    ) THEN
        missing_versions := missing_versions || CASE WHEN missing_versions = '' THEN '' ELSE ', ' END || '0111_record_submission_answer_file_asset_versions.sql';
    END IF;

    IF missing_versions <> '' THEN
        RAISE EXCEPTION 'Missing submission.answer_file_asset migration versions: %', missing_versions;
    END IF;

    RAISE NOTICE 'PASS: submission.answer_file_asset migration versions are recorded.';
END
$$;

