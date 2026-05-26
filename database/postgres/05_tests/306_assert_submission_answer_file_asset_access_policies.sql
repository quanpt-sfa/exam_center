-- Verifies raw table access restrictions and safe view access for student answer file assets.

DO
$$
BEGIN
    IF has_table_privilege('exam_sys_app', 'submission.answer_file_asset', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on submission.answer_file_asset';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'submission.answer_file_asset', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on submission.answer_file_asset';
    END IF;

    IF NOT has_table_privilege('exam_sys_app', 'submission.v_answer_file_asset_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_app must have SELECT on submission.v_answer_file_asset_summary';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'submission.v_answer_file_asset_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must have SELECT on submission.v_answer_file_asset_summary';
    END IF;

    RAISE NOTICE 'PASS: submission.answer_file_asset access policies are valid.';
END
$$;

