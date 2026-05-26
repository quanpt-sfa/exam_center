-- Verifies indexes and active-file uniqueness policy for student answer file assets.

DO
$$
DECLARE
    missing_indexes text := '';
    predicate_sql text;
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'submission'
          AND indexname = 'idx_submission_afa_exam_submission_id'
    ) THEN
        missing_indexes := missing_indexes || CASE WHEN missing_indexes = '' THEN '' ELSE ', ' END || 'idx_submission_afa_exam_submission_id';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'submission'
          AND indexname = 'idx_submission_afa_generated_exam_question_id'
    ) THEN
        missing_indexes := missing_indexes || CASE WHEN missing_indexes = '' THEN '' ELSE ', ' END || 'idx_submission_afa_generated_exam_question_id';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'submission'
          AND indexname = 'idx_submission_afa_answer_state_id'
    ) THEN
        missing_indexes := missing_indexes || CASE WHEN missing_indexes = '' THEN '' ELSE ', ' END || 'idx_submission_afa_answer_state_id';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'submission'
          AND indexname = 'idx_submission_afa_submission_seal_id'
    ) THEN
        missing_indexes := missing_indexes || CASE WHEN missing_indexes = '' THEN '' ELSE ', ' END || 'idx_submission_afa_submission_seal_id';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'submission'
          AND indexname = 'idx_submission_afa_sealed_answer_id'
    ) THEN
        missing_indexes := missing_indexes || CASE WHEN missing_indexes = '' THEN '' ELSE ', ' END || 'idx_submission_afa_sealed_answer_id';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'submission'
          AND indexname = 'idx_submission_afa_sha256_hash'
    ) THEN
        missing_indexes := missing_indexes || CASE WHEN missing_indexes = '' THEN '' ELSE ', ' END || 'idx_submission_afa_sha256_hash';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'submission'
          AND indexname = 'idx_submission_afa_asset_status'
    ) THEN
        missing_indexes := missing_indexes || CASE WHEN missing_indexes = '' THEN '' ELSE ', ' END || 'idx_submission_afa_asset_status';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'submission'
          AND indexname = 'idx_submission_afa_uploaded_at'
    ) THEN
        missing_indexes := missing_indexes || CASE WHEN missing_indexes = '' THEN '' ELSE ', ' END || 'idx_submission_afa_uploaded_at';
    END IF;

    IF missing_indexes <> '' THEN
        RAISE EXCEPTION 'Missing submission.answer_file_asset indexes: %', missing_indexes;
    END IF;

    SELECT pg_get_expr(i.indpred, i.indrelid)
    INTO predicate_sql
    FROM pg_index i
    JOIN pg_class c
      ON c.oid = i.indexrelid
    JOIN pg_namespace n
      ON n.oid = c.relnamespace
    WHERE n.nspname = 'submission'
      AND c.relname = 'ux_submission_afa_one_active_per_submission_question';

    IF predicate_sql IS NULL THEN
        RAISE EXCEPTION 'Missing unique partial index ux_submission_afa_one_active_per_submission_question';
    END IF;

    IF predicate_sql NOT ILIKE '%asset_status%'
       OR predicate_sql NOT ILIKE '%ACTIVE%' THEN
        RAISE EXCEPTION 'Unexpected uniqueness predicate for active answer file asset: %', predicate_sql;
    END IF;

    RAISE NOTICE 'PASS: submission.answer_file_asset indexes and uniqueness policy are valid.';
END
$$;

