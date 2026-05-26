-- Verifies student answer file asset table and safe summary view exist.

DO
$$
BEGIN
    IF to_regclass('submission.answer_file_asset') IS NULL THEN
        RAISE EXCEPTION 'Table submission.answer_file_asset does not exist';
    END IF;

    IF to_regclass('submission.v_answer_file_asset_summary') IS NULL THEN
        RAISE EXCEPTION 'View submission.v_answer_file_asset_summary does not exist';
    END IF;

    RAISE NOTICE 'PASS: submission answer file asset table/view exist.';
END
$$;

