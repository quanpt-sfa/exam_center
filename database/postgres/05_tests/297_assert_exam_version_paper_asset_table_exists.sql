-- Verifies exam version visual paper asset table and safe summary view exist.

DO
$$
BEGIN
    IF to_regclass('assessment.exam_version_paper_asset') IS NULL THEN
        RAISE EXCEPTION 'Table assessment.exam_version_paper_asset does not exist';
    END IF;

    IF to_regclass('assessment.v_exam_version_paper_asset_admin_summary') IS NULL THEN
        RAISE EXCEPTION 'View assessment.v_exam_version_paper_asset_admin_summary does not exist';
    END IF;

    RAISE NOTICE 'PASS: visual paper asset table/view exist.';
END
$$;
