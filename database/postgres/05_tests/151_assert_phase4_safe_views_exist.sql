-- Verifies Phase 4.6 safe views exist with expected contracts.

DO
$$
DECLARE
    view_name text;
    missing_views text := '';
BEGIN
    FOREACH view_name IN ARRAY ARRAY[
        'submission.v_student_answer_resume_state',
        'submission.v_submission_status',
        'submission.v_sealed_submission_summary',
        'capture.v_capture_job_status'
    ]
    LOOP
        IF to_regclass(view_name) IS NULL THEN
            missing_views := missing_views || CASE WHEN missing_views = '' THEN '' ELSE ', ' END || view_name;
        END IF;
    END LOOP;

    IF missing_views <> '' THEN
        RAISE EXCEPTION 'Missing Phase 4.6 safe views: %', missing_views;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'capture'
          AND table_name = 'v_capture_job_status'
          AND column_name = 'error_code'
    ) THEN
        RAISE EXCEPTION 'capture.v_capture_job_status must expose error_code';
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'capture'
          AND table_name = 'v_capture_job_status'
          AND column_name = 'error_message'
    ) THEN
        RAISE EXCEPTION 'capture.v_capture_job_status must not expose error_message';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'submission'
          AND table_name = 'v_student_answer_resume_state'
          AND column_name = 'generated_exam_question_id'
    ) THEN
        RAISE EXCEPTION 'submission.v_student_answer_resume_state must expose generated_exam_question_id';
    END IF;

    RAISE NOTICE 'PASS: Phase 4 safe views exist with expected contracts.';
END
$$;
