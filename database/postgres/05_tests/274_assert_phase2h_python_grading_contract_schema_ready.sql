DO
$$
DECLARE
    v_question_template_check text;
    v_generated_question_check text;
    v_profile_comparison_check text;
    v_runtime_comparison_check text;
    v_python_test_case_exists boolean;
    v_missing_python_test_case_columns text;
    v_visibility_check text;
    v_comparison_mode_check text;
    v_question_template_index_exists boolean;
BEGIN
    SELECT pg_get_constraintdef(c.oid)
    INTO v_question_template_check
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'assessment'
      AND t.relname = 'question_template'
      AND c.conname = 'ck_assessment_question_template_question_type'
      AND c.contype = 'c'
    LIMIT 1;

    IF v_question_template_check IS NULL OR position('PYTHON_FUNCTION' in v_question_template_check) = 0 THEN
        RAISE EXCEPTION 'Expected assessment.question_template question_type contract to include PYTHON_FUNCTION. Found: %', coalesce(v_question_template_check, '<missing>');
    END IF;

    SELECT pg_get_constraintdef(c.oid)
    INTO v_generated_question_check
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'delivery'
      AND t.relname = 'generated_exam_question'
      AND c.conname = 'ck_delivery_generated_exam_question_type'
      AND c.contype = 'c'
    LIMIT 1;

    IF v_generated_question_check IS NULL OR position('PYTHON_FUNCTION' in v_generated_question_check) = 0 THEN
        RAISE EXCEPTION 'Expected delivery.generated_exam_question question_type contract to include PYTHON_FUNCTION. Found: %', coalesce(v_generated_question_check, '<missing>');
    END IF;

    SELECT pg_get_constraintdef(c.oid)
    INTO v_profile_comparison_check
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'assessment'
      AND t.relname = 'question_grading_profile'
      AND c.conname = 'ck_assessment_question_grading_profile_comparison_method'
      AND c.contype = 'c'
    LIMIT 1;

    IF v_profile_comparison_check IS NULL OR position('PYTHON_TEST_CASES' in v_profile_comparison_check) = 0 THEN
        RAISE EXCEPTION 'Expected assessment.question_grading_profile comparison_method contract to include PYTHON_TEST_CASES. Found: %', coalesce(v_profile_comparison_check, '<missing>');
    END IF;

    SELECT pg_get_constraintdef(c.oid)
    INTO v_runtime_comparison_check
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'grading'
      AND t.relname = 'expected_actual_comparison'
      AND c.conname = 'ck_gr_eac_comparison_method'
      AND c.contype = 'c'
    LIMIT 1;

    IF v_runtime_comparison_check IS NULL OR position('PYTHON_TEST_CASES' in v_runtime_comparison_check) = 0 THEN
        RAISE EXCEPTION 'Expected grading.expected_actual_comparison comparison_method contract to include PYTHON_TEST_CASES. Found: %', coalesce(v_runtime_comparison_check, '<missing>');
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'assessment'
          AND table_name = 'python_test_case'
    ) INTO v_python_test_case_exists;

    IF NOT v_python_test_case_exists THEN
        RAISE EXCEPTION 'Expected table assessment.python_test_case to exist.';
    END IF;

    WITH required_columns AS (
        SELECT unnest(
            ARRAY[
                'python_test_case_id',
                'question_template_id',
                'visibility',
                'input_payload_json',
                'expected_output_json',
                'comparison_mode',
                'weight',
                'timeout_override_seconds',
                'display_order',
                'is_active',
                'created_at',
                'updated_at'
            ]
        ) AS column_name
    )
    SELECT string_agg(rc.column_name, ', ' ORDER BY rc.column_name)
    INTO v_missing_python_test_case_columns
    FROM required_columns rc
    LEFT JOIN information_schema.columns c
      ON c.table_schema = 'assessment'
     AND c.table_name = 'python_test_case'
     AND c.column_name = rc.column_name
    WHERE c.column_name IS NULL;

    IF v_missing_python_test_case_columns IS NOT NULL THEN
        RAISE EXCEPTION 'Missing required columns on assessment.python_test_case: %', v_missing_python_test_case_columns;
    END IF;

    SELECT pg_get_constraintdef(c.oid)
    INTO v_visibility_check
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'assessment'
      AND t.relname = 'python_test_case'
      AND c.conname = 'ck_assessment_python_test_case_visibility'
      AND c.contype = 'c'
    LIMIT 1;

    IF v_visibility_check IS NULL
       OR position('PUBLIC' in v_visibility_check) = 0
       OR position('HIDDEN' in v_visibility_check) = 0 THEN
        RAISE EXCEPTION 'Expected assessment.python_test_case visibility contract to allow PUBLIC/HIDDEN. Found: %', coalesce(v_visibility_check, '<missing>');
    END IF;

    SELECT pg_get_constraintdef(c.oid)
    INTO v_comparison_mode_check
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'assessment'
      AND t.relname = 'python_test_case'
      AND c.conname = 'ck_assessment_python_test_case_comparison_mode'
      AND c.contype = 'c'
    LIMIT 1;

    IF v_comparison_mode_check IS NULL
       OR position('EXACT_JSON' in v_comparison_mode_check) = 0
       OR position('NUMERIC_TOLERANCE' in v_comparison_mode_check) = 0 THEN
        RAISE EXCEPTION 'Expected assessment.python_test_case comparison_mode contract to include EXACT_JSON/NUMERIC_TOLERANCE. Found: %', coalesce(v_comparison_mode_check, '<missing>');
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'assessment'
          AND tablename = 'python_test_case'
          AND indexname = 'idx_assessment_python_test_case_question_template_id'
    ) INTO v_question_template_index_exists;

    IF NOT v_question_template_index_exists THEN
        RAISE EXCEPTION 'Expected idx_assessment_python_test_case_question_template_id to exist.';
    END IF;

    RAISE NOTICE 'PASS: Phase 2H Python grading contract schema readiness checks passed.';
END
$$;