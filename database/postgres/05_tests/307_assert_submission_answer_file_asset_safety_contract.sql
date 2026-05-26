-- Verifies safe summary view and raw table schema do not expose storage keys, file bytes, or expected-answer fields.

DO
$$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'submission'
          AND table_name = 'v_answer_file_asset_summary'
          AND column_name IN ('internal_storage_key', 'stored_filename', 'storage_relative_path')
    ) THEN
        RAISE EXCEPTION 'submission.v_answer_file_asset_summary must not expose internal storage columns';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'submission'
          AND table_name = 'answer_file_asset'
          AND data_type = 'bytea'
    ) THEN
        RAISE EXCEPTION 'submission.answer_file_asset must not store raw file bytes';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'submission'
          AND table_name = 'answer_file_asset'
          AND column_name IN (
              'file_content',
              'file_bytes',
              'blob_data',
              'expected_answer',
              'expected_answer_json',
              'expected_payload',
              'expected_payload_json',
              'solution',
              'solution_json',
              'solution_payload',
              'solution_payload_json',
              'reference_solution_id',
              'grading_solution_data'
          )
    ) THEN
        RAISE EXCEPTION 'submission.answer_file_asset must not include raw file-byte or expected/solution columns';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'submission'
          AND table_name = 'v_answer_file_asset_summary'
          AND column_name IN (
              'expected_answer',
              'expected_answer_json',
              'solution_payload_json',
              'reference_solution_id'
          )
    ) THEN
        RAISE EXCEPTION 'submission.v_answer_file_asset_summary must not expose expected/solution columns';
    END IF;

    RAISE NOTICE 'PASS: submission.answer_file_asset safety contract is valid.';
END
$$;

