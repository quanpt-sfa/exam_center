-- Verifies required constraints for student answer file asset metadata safety and integrity.

DO
$$
DECLARE
    missing_constraints text := '';
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints tc
        WHERE tc.table_schema = 'submission'
          AND tc.table_name = 'answer_file_asset'
          AND tc.constraint_type = 'PRIMARY KEY'
    ) THEN
        missing_constraints := missing_constraints || CASE WHEN missing_constraints = '' THEN '' ELSE ', ' END || 'primary key';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints tc
        WHERE tc.table_schema = 'submission'
          AND tc.table_name = 'answer_file_asset'
          AND tc.constraint_name = 'ck_submission_afa_file_size_bytes'
          AND tc.constraint_type = 'CHECK'
    ) THEN
        missing_constraints := missing_constraints || CASE WHEN missing_constraints = '' THEN '' ELSE ', ' END || 'ck_submission_afa_file_size_bytes';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints tc
        WHERE tc.table_schema = 'submission'
          AND tc.table_name = 'answer_file_asset'
          AND tc.constraint_name = 'ck_submission_afa_sha256_length'
          AND tc.constraint_type = 'CHECK'
    ) THEN
        missing_constraints := missing_constraints || CASE WHEN missing_constraints = '' THEN '' ELSE ', ' END || 'ck_submission_afa_sha256_length';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints tc
        WHERE tc.table_schema = 'submission'
          AND tc.table_name = 'answer_file_asset'
          AND tc.constraint_name = 'ck_submission_afa_asset_status'
          AND tc.constraint_type = 'CHECK'
    ) THEN
        missing_constraints := missing_constraints || CASE WHEN missing_constraints = '' THEN '' ELSE ', ' END || 'ck_submission_afa_asset_status';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints tc
        WHERE tc.table_schema = 'submission'
          AND tc.table_name = 'answer_file_asset'
          AND tc.constraint_name = 'ck_submission_afa_superseded_at'
          AND tc.constraint_type = 'CHECK'
    ) THEN
        missing_constraints := missing_constraints || CASE WHEN missing_constraints = '' THEN '' ELSE ', ' END || 'ck_submission_afa_superseded_at';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints tc
        WHERE tc.table_schema = 'submission'
          AND tc.table_name = 'answer_file_asset'
          AND tc.constraint_name = 'fk_submission_afa_exam_submission'
          AND tc.constraint_type = 'FOREIGN KEY'
    ) THEN
        missing_constraints := missing_constraints || CASE WHEN missing_constraints = '' THEN '' ELSE ', ' END || 'fk_submission_afa_exam_submission';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints tc
        WHERE tc.table_schema = 'submission'
          AND tc.table_name = 'answer_file_asset'
          AND tc.constraint_name = 'fk_submission_afa_generated_exam_question'
          AND tc.constraint_type = 'FOREIGN KEY'
    ) THEN
        missing_constraints := missing_constraints || CASE WHEN missing_constraints = '' THEN '' ELSE ', ' END || 'fk_submission_afa_generated_exam_question';
    END IF;

    IF missing_constraints <> '' THEN
        RAISE EXCEPTION 'Missing submission.answer_file_asset constraints: %', missing_constraints;
    END IF;

    RAISE NOTICE 'PASS: submission.answer_file_asset constraints exist.';
END
$$;
