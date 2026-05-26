-- Verifies raw table access restrictions and safe view access.

DO
$$
BEGIN
    IF has_table_privilege('exam_sys_app', 'assessment.exam_version_paper_asset', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on assessment.exam_version_paper_asset';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'assessment.exam_version_paper_asset', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on assessment.exam_version_paper_asset';
    END IF;

    IF NOT has_table_privilege('exam_sys_app', 'assessment.v_exam_version_paper_asset_admin_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_app must have SELECT on assessment.v_exam_version_paper_asset_admin_summary';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'assessment.v_exam_version_paper_asset_admin_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must have SELECT on assessment.v_exam_version_paper_asset_admin_summary';
    END IF;

    RAISE NOTICE 'PASS: visual paper asset access policies are valid.';
END
$$;
