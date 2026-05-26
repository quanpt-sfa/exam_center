-- Verifies S2W-4.5 question_score schema readiness without modifying schema.

DO
$$
DECLARE
    v_question_score_exists boolean;
    v_missing_columns text;
    v_uq_question_task_exists boolean;
    v_status_check text;

    v_raw_score_non_negative_exists boolean;
    v_max_score_positive_exists boolean;
    v_raw_not_exceed_max_exists boolean;

    v_fk_question_task_exists boolean;
    v_fk_exam_submission_exists boolean;
    v_fk_submission_seal_exists boolean;
    v_fk_sealed_answer_exists boolean;
    v_fk_generated_question_exists boolean;
    v_fk_scored_engine_exists boolean;

    v_grading_event_exists boolean;
    v_event_type_check text;

    v_submission_score_exists boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'grading'
          AND table_name = 'question_score'
    ) INTO v_question_score_exists;

    IF NOT v_question_score_exists THEN
        RAISE EXCEPTION 'Expected table grading.question_score to exist.';
    END IF;

    WITH required_columns AS (
        SELECT unnest(
            ARRAY[
                'question_score_id',
                'question_grading_task_id',
                'exam_submission_id',
                'submission_seal_id',
                'sealed_answer_id',
                'generated_exam_question_id',
                'raw_score',
                'max_score',
                'score_percent',
                'score_status',
                'scored_at',
                'scored_by_engine_id',
                'requires_manual_review',
                'feedback_json',
                'metadata_json'
            ]
        ) AS column_name
    )
    SELECT string_agg(rc.column_name, ', ' ORDER BY rc.column_name)
    INTO v_missing_columns
    FROM required_columns rc
    LEFT JOIN information_schema.columns c
        ON c.table_schema = 'grading'
       AND c.table_name = 'question_score'
       AND c.column_name = rc.column_name
    WHERE c.column_name IS NULL;

    IF v_missing_columns IS NOT NULL THEN
        RAISE EXCEPTION 'Missing required columns on grading.question_score: %', v_missing_columns;
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t
            ON t.oid = c.conrelid
        JOIN pg_namespace n
            ON n.oid = t.relnamespace
        WHERE n.nspname = 'grading'
          AND t.relname = 'question_score'
          AND c.conname = 'uq_gr_qs_question_task'
          AND c.contype IN ('u', 'p')
    )
    OR EXISTS (
        SELECT 1
        FROM pg_indexes i
        WHERE i.schemaname = 'grading'
          AND i.tablename = 'question_score'
          AND i.indexname = 'uq_gr_qs_question_task'
    )
    INTO v_uq_question_task_exists;

    IF NOT v_uq_question_task_exists THEN
        RAISE EXCEPTION 'Expected uq_gr_qs_question_task unique constraint/index to exist on grading.question_score.';
    END IF;

    SELECT pg_get_constraintdef(c.oid)
    INTO v_status_check
    FROM pg_constraint c
    JOIN pg_class t
        ON t.oid = c.conrelid
    JOIN pg_namespace n
        ON n.oid = t.relnamespace
    WHERE n.nspname = 'grading'
      AND t.relname = 'question_score'
      AND c.conname = 'ck_gr_qs_score_status'
      AND c.contype = 'c'
    LIMIT 1;

    IF v_status_check IS NULL
       OR position('SCORED' in v_status_check) = 0
       OR position('PARTIAL' in v_status_check) = 0
       OR position('ZERO' in v_status_check) = 0
       OR position('ERROR' in v_status_check) = 0
       OR position('NEEDS_REVIEW' in v_status_check) = 0
       OR position('MANUAL_OVERRIDE' in v_status_check) = 0
       OR position('VOIDED' in v_status_check) = 0 THEN
        RAISE EXCEPTION 'Expected ck_gr_qs_score_status to allow SCORED/PARTIAL/ZERO/ERROR/NEEDS_REVIEW/MANUAL_OVERRIDE/VOIDED. Found: %', coalesce(v_status_check, '<missing>');
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t
            ON t.oid = c.conrelid
        JOIN pg_namespace n
            ON n.oid = t.relnamespace
        WHERE n.nspname = 'grading'
          AND t.relname = 'question_score'
          AND c.contype = 'c'
          AND (
                c.conname = 'ck_gr_qs_raw_score_non_negative'
             OR position('raw_score >= 0' in pg_get_constraintdef(c.oid)) > 0
          )
    ) INTO v_raw_score_non_negative_exists;

    SELECT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t
            ON t.oid = c.conrelid
        JOIN pg_namespace n
            ON n.oid = t.relnamespace
        WHERE n.nspname = 'grading'
          AND t.relname = 'question_score'
          AND c.contype = 'c'
          AND (
                c.conname = 'ck_gr_qs_max_score_positive'
             OR position('max_score > 0' in pg_get_constraintdef(c.oid)) > 0
          )
    ) INTO v_max_score_positive_exists;

    SELECT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t
            ON t.oid = c.conrelid
        JOIN pg_namespace n
            ON n.oid = t.relnamespace
        WHERE n.nspname = 'grading'
          AND t.relname = 'question_score'
          AND c.contype = 'c'
          AND (
                c.conname = 'ck_gr_qs_raw_not_exceed_max'
             OR (
                    position('raw_score <= max_score' in pg_get_constraintdef(c.oid)) > 0
                AND position('MANUAL_OVERRIDE' in pg_get_constraintdef(c.oid)) > 0
                )
          )
    ) INTO v_raw_not_exceed_max_exists;

    IF NOT v_raw_score_non_negative_exists THEN
        RAISE EXCEPTION 'Expected raw_score non-negative check to exist or be inferable on grading.question_score.';
    END IF;

    IF NOT v_max_score_positive_exists THEN
        RAISE EXCEPTION 'Expected max_score positive check to exist or be inferable on grading.question_score.';
    END IF;

    IF NOT v_raw_not_exceed_max_exists THEN
        RAISE EXCEPTION 'Expected raw_score <= max_score unless MANUAL_OVERRIDE check to exist or be inferable on grading.question_score.';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t
            ON t.oid = c.conrelid
        JOIN pg_namespace n
            ON n.oid = t.relnamespace
        WHERE n.nspname = 'grading'
          AND t.relname = 'question_score'
          AND c.conname = 'fk_gr_qs_question_task'
          AND c.contype = 'f'
    ) INTO v_fk_question_task_exists;

    SELECT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t
            ON t.oid = c.conrelid
        JOIN pg_namespace n
            ON n.oid = t.relnamespace
        WHERE n.nspname = 'grading'
          AND t.relname = 'question_score'
          AND c.conname = 'fk_gr_qs_exam_submission'
          AND c.contype = 'f'
    ) INTO v_fk_exam_submission_exists;

    SELECT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t
            ON t.oid = c.conrelid
        JOIN pg_namespace n
            ON n.oid = t.relnamespace
        WHERE n.nspname = 'grading'
          AND t.relname = 'question_score'
          AND c.conname = 'fk_gr_qs_submission_seal'
          AND c.contype = 'f'
    ) INTO v_fk_submission_seal_exists;

    SELECT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t
            ON t.oid = c.conrelid
        JOIN pg_namespace n
            ON n.oid = t.relnamespace
        WHERE n.nspname = 'grading'
          AND t.relname = 'question_score'
          AND c.conname = 'fk_gr_qs_sealed_answer'
          AND c.contype = 'f'
    ) INTO v_fk_sealed_answer_exists;

    SELECT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t
            ON t.oid = c.conrelid
        JOIN pg_namespace n
            ON n.oid = t.relnamespace
        WHERE n.nspname = 'grading'
          AND t.relname = 'question_score'
          AND c.conname = 'fk_gr_qs_generated_question'
          AND c.contype = 'f'
    ) INTO v_fk_generated_question_exists;

    SELECT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t
            ON t.oid = c.conrelid
        JOIN pg_namespace n
            ON n.oid = t.relnamespace
        WHERE n.nspname = 'grading'
          AND t.relname = 'question_score'
          AND c.conname = 'fk_gr_qs_scored_engine'
          AND c.contype = 'f'
    ) INTO v_fk_scored_engine_exists;

    IF NOT v_fk_question_task_exists THEN
        RAISE EXCEPTION 'Expected fk_gr_qs_question_task foreign key to exist or be inferable.';
    END IF;

    IF NOT v_fk_exam_submission_exists THEN
        RAISE EXCEPTION 'Expected fk_gr_qs_exam_submission foreign key to exist or be inferable.';
    END IF;

    IF NOT v_fk_submission_seal_exists THEN
        RAISE EXCEPTION 'Expected fk_gr_qs_submission_seal foreign key to exist or be inferable.';
    END IF;

    IF NOT v_fk_sealed_answer_exists THEN
        RAISE EXCEPTION 'Expected fk_gr_qs_sealed_answer foreign key to exist or be inferable.';
    END IF;

    IF NOT v_fk_generated_question_exists THEN
        RAISE EXCEPTION 'Expected fk_gr_qs_generated_question foreign key to exist or be inferable.';
    END IF;

    IF NOT v_fk_scored_engine_exists THEN
        RAISE EXCEPTION 'Expected fk_gr_qs_scored_engine foreign key to exist or be inferable.';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'grading'
          AND table_name = 'grading_event'
    ) INTO v_grading_event_exists;

    IF NOT v_grading_event_exists THEN
        RAISE EXCEPTION 'Expected table grading.grading_event to exist.';
    END IF;

    SELECT pg_get_constraintdef(c.oid)
    INTO v_event_type_check
    FROM pg_constraint c
    JOIN pg_class t
        ON t.oid = c.conrelid
    JOIN pg_namespace n
        ON n.oid = t.relnamespace
    WHERE n.nspname = 'grading'
      AND t.relname = 'grading_event'
      AND c.conname = 'ck_gr_ge_event_type'
      AND c.contype = 'c'
    LIMIT 1;

    IF v_event_type_check IS NULL
       OR position('SCORE_CREATED' in v_event_type_check) = 0 THEN
        RAISE EXCEPTION 'Expected ck_gr_ge_event_type to allow SCORE_CREATED. Found: %', coalesce(v_event_type_check, '<missing>');
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'grading'
          AND table_name = 'submission_score'
    ) INTO v_submission_score_exists;

    IF NOT v_submission_score_exists THEN
        RAISE EXCEPTION 'Expected table grading.submission_score to exist (out-of-scope for S2W-4.5 behavior).';
    END IF;

    RAISE NOTICE 'PASS: S2W-4.5G question_score schema readiness checks passed.';
END
$$;
