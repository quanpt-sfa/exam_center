-- Verifies migration metadata for visual paper asset foundation is recorded.

DO
$$
DECLARE
    missing_versions text := '';
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM app_meta.schema_migrations
        WHERE version = '0108_create_exam_version_paper_asset.sql'
    ) THEN
        missing_versions := missing_versions || CASE WHEN missing_versions = '' THEN '' ELSE ', ' END || '0108_create_exam_version_paper_asset.sql';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM app_meta.schema_migrations
        WHERE version = '0109_record_exam_version_paper_asset_versions.sql'
    ) THEN
        missing_versions := missing_versions || CASE WHEN missing_versions = '' THEN '' ELSE ', ' END || '0109_record_exam_version_paper_asset_versions.sql';
    END IF;

    IF missing_versions <> '' THEN
        RAISE EXCEPTION 'Missing visual paper asset migration versions: %', missing_versions;
    END IF;

    RAISE NOTICE 'PASS: visual paper asset migration versions are recorded.';
END
$$;
