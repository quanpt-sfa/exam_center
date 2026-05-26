-- Verifies Phase 3.2 generated exam safe views exist with expected projection.

DO
$$
DECLARE
    missing_views text := '';
    issues text := '';
BEGIN
    IF to_regclass('delivery.v_student_generated_exam') IS NULL THEN
        missing_views := missing_views || CASE WHEN missing_views = '' THEN '' ELSE ', ' END || 'delivery.v_student_generated_exam';
    END IF;

    IF to_regclass('delivery.v_proctor_generated_exam_summary') IS NULL THEN
        missing_views := missing_views || CASE WHEN missing_views = '' THEN '' ELSE ', ' END || 'delivery.v_proctor_generated_exam_summary';
    END IF;

    IF to_regclass('delivery.v_generated_exam_audit_summary') IS NULL THEN
        missing_views := missing_views || CASE WHEN missing_views = '' THEN '' ELSE ', ' END || 'delivery.v_generated_exam_audit_summary';
    END IF;

    IF missing_views <> '' THEN
        RAISE EXCEPTION 'Missing Phase 3.2 safe views: %', missing_views;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'delivery' AND table_name = 'v_student_generated_exam' AND column_name = 'rendered_question_text'
    ) OR NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'delivery' AND table_name = 'v_student_generated_exam' AND column_name = 'score'
    ) THEN
        issues := issues || CASE WHEN issues = '' THEN '' ELSE '; ' END
            || 'v_student_generated_exam missing rendered_question_text/score';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'delivery' AND table_name = 'v_proctor_generated_exam_summary' AND column_name = 'question_count'
    ) OR NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'delivery' AND table_name = 'v_proctor_generated_exam_summary' AND column_name = 'total_generated_score'
    ) THEN
        issues := issues || CASE WHEN issues = '' THEN '' ELSE '; ' END
            || 'v_proctor_generated_exam_summary missing question_count/total_generated_score';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'delivery' AND table_name = 'v_generated_exam_audit_summary' AND column_name = 'instance_hash'
    ) OR NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'delivery' AND table_name = 'v_generated_exam_audit_summary' AND column_name = 'generation_status'
    ) THEN
        issues := issues || CASE WHEN issues = '' THEN '' ELSE '; ' END
            || 'v_generated_exam_audit_summary missing instance_hash/generation_status';
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'delivery' AND table_name = 'v_student_generated_exam' AND column_name = 'parameter_value_json'
    ) OR EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'delivery' AND table_name = 'v_generated_exam_audit_summary' AND column_name = 'metadata_json'
    ) THEN
        issues := issues || CASE WHEN issues = '' THEN '' ELSE '; ' END
            || 'safe views expose sensitive parameter/metadata payload columns';
    END IF;

    IF issues <> '' THEN
        RAISE EXCEPTION 'Phase 3.2 safe view validation failed: %', issues;
    END IF;

    RAISE NOTICE 'PASS: Phase 3.2 safe views exist with expected projection.';
END
$$;
