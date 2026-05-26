-- Verifies no expected-answer fields are introduced and student-facing view does not expose storage paths.

DO
$$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'assessment'
          AND table_name = 'exam_version_paper_asset'
          AND column_name IN (
              'expected_payload',
              'expected_payload_json',
              'solution_payload',
              'solution_payload_json',
              'reference_solution_id',
              'sealed_answer_text'
          )
    ) THEN
        RAISE EXCEPTION 'assessment.exam_version_paper_asset must not include expected-answer payload fields';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'delivery'
          AND table_name = 'v_student_generated_exam'
          AND column_name IN (
              'storage_relative_path',
              'stored_filename',
              'original_filename',
              'artifact_ref',
              'file_ref'
          )
    ) THEN
        RAISE EXCEPTION 'delivery.v_student_generated_exam must not expose visual paper storage/file path columns';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'assessment'
          AND table_name = 'v_exam_version_paper_asset_admin_summary'
          AND column_name = 'storage_relative_path'
    ) THEN
        RAISE EXCEPTION 'assessment.v_exam_version_paper_asset_admin_summary must not expose storage_relative_path';
    END IF;

    RAISE NOTICE 'PASS: visual paper asset safety contract is valid.';
END
$$;
