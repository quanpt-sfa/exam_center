-- Verifies Phase 5A transactional insert graph case 5:
-- score adjustments are auditable and do not mutate sealed_answer provenance.

BEGIN;

DO
$$
DECLARE
    suffix text := 'SMOKE_P56_C5_' || txid_current()::text;

    v_department_id bigint;
    v_term_id bigint;
    v_course_id bigint;
    v_course_offering_id bigint;
    v_class_section_id bigint;

    v_student_person_id bigint;
    v_proctor_person_id bigint;
    v_student_id bigint;
    v_proctor_user_id bigint;

    v_assessment_type_id bigint;
    v_exam_id bigint;
    v_exam_version_id bigint;

    v_question_template_id bigint;
    v_generated_question_id bigint;
    v_generated_expected_answer_id bigint;

    v_sitting_id bigint;
    v_assignment_id bigint;
    v_session_id bigint;
    v_generated_exam_instance_id bigint;
    v_exam_submission_id bigint;
    v_submission_seal_id bigint;
    v_sealed_answer_id bigint;

    v_grading_job_id bigint;
    v_grading_run_id bigint;
    v_question_grading_task_id bigint;
    v_actual_result_id bigint;
    v_comparison_id bigint;
    v_question_score_id bigint;
    v_submission_score_id bigint;

    v_adjustment_question_id bigint;
    v_adjustment_submission_id bigint;
    v_event_id bigint;

    v_sql_engine_id bigint;
    v_original_answer_text text;
    v_original_answer_hash text;
BEGIN
    SELECT assessment_type_id
    INTO v_assessment_type_id
    FROM assessment.assessment_type
    WHERE type_code = 'QUIZ'
    ORDER BY assessment_type_id
    LIMIT 1;

    IF v_assessment_type_id IS NULL THEN
        RAISE EXCEPTION 'Required seed QUIZ in assessment.assessment_type is missing.';
    END IF;

    SELECT grading_engine_id
    INTO v_sql_engine_id
    FROM grading.grading_engine
    WHERE engine_code = 'SQL_RESULT_COMPARATOR'
    ORDER BY grading_engine_id
    LIMIT 1;

    IF v_sql_engine_id IS NULL THEN
        RAISE EXCEPTION 'Required grading engine SQL_RESULT_COMPARATOR is missing.';
    END IF;

    INSERT INTO academic.department (department_code, department_name, status)
    VALUES (suffix || '_DEPT', suffix || ' Department', 'ACTIVE')
    RETURNING department_id INTO v_department_id;

    INSERT INTO academic.term (term_code, term_name, start_date, end_date, status)
    VALUES (suffix || '_TERM', suffix || ' Term', CURRENT_DATE, CURRENT_DATE + INTERVAL '120 days', 'ACTIVE')
    RETURNING term_id INTO v_term_id;

    INSERT INTO academic.course (department_id, course_code, course_name, course_type, credit, status)
    VALUES (v_department_id, suffix || '_COURSE', suffix || ' Course', 'SQL_SERVER', 3.0, 'ACTIVE')
    RETURNING course_id INTO v_course_id;

    INSERT INTO academic.course_offering (course_id, term_id, offering_code, coordinator_id, status)
    VALUES (v_course_id, v_term_id, suffix || '_OFF', NULL, 'ACTIVE')
    RETURNING course_offering_id INTO v_course_offering_id;

    INSERT INTO academic.class_section (course_offering_id, class_code, class_name, capacity, delivery_mode, status)
    VALUES (v_course_offering_id, suffix || '_CLASS', suffix || ' Class', 40, 'ONSITE', 'ACTIVE')
    RETURNING class_section_id INTO v_class_section_id;

    INSERT INTO identity.person (full_name, person_status)
    VALUES (suffix || ' Student', 'ACTIVE')
    RETURNING person_id INTO v_student_person_id;

    INSERT INTO identity.person (full_name, person_status)
    VALUES (suffix || ' Proctor', 'ACTIVE')
    RETURNING person_id INTO v_proctor_person_id;

    INSERT INTO identity.student_profile (person_id, student_code, program_id, cohort, entry_year, student_status)
    VALUES (
        v_student_person_id,
        suffix || '_STU',
        NULL,
        'K' || to_char(CURRENT_DATE, 'YYYY'),
        EXTRACT(YEAR FROM CURRENT_DATE)::integer,
        'ACTIVE'
    )
    RETURNING student_id INTO v_student_id;

    INSERT INTO identity.app_user (person_id, username, email_login, password_hash, user_status)
    VALUES (
        v_proctor_person_id,
        lower(suffix) || '_proctor',
        lower(suffix) || '@local.test',
        'hash_p56_c5_proctor',
        'ACTIVE'
    )
    RETURNING user_id INTO v_proctor_user_id;

    INSERT INTO assessment.exam (
        class_section_id,
        assessment_type_id,
        exam_code,
        exam_name,
        description,
        exam_status,
        created_by
    )
    VALUES (
        v_class_section_id,
        v_assessment_type_id,
        suffix || '_EXAM',
        suffix || ' Exam',
        'Phase 5.6 case 5 score adjustment provenance transactional smoke',
        'DRAFT',
        v_proctor_user_id
    )
    RETURNING exam_id INTO v_exam_id;

    INSERT INTO assessment.exam_version (
        exam_id,
        version_no,
        version_label,
        duration_seconds,
        total_score,
        shuffle_questions,
        shuffle_options,
        randomization_mode,
        status
    )
    VALUES (
        v_exam_id,
        1,
        'v1',
        3600,
        100.00,
        false,
        false,
        'FIXED',
        'DRAFT'
    )
    RETURNING exam_version_id INTO v_exam_version_id;

    INSERT INTO assessment.question_template (
        template_code,
        question_type,
        title,
        template_text,
        topic_code,
        skill_code,
        difficulty_level,
        default_score,
        generator_type,
        generator_version,
        status,
        created_by
    )
    VALUES (
        suffix || '_QT01',
        'SQL_QUERY',
        suffix || ' Template',
        'Provide SQL query for deterministic output.',
        'TOPIC5',
        'SKILL5',
        'MEDIUM',
        10.00,
        'PARAMETERIZED',
        '1.0.0',
        'ACTIVE',
        v_proctor_user_id
    )
    RETURNING question_template_id INTO v_question_template_id;

    INSERT INTO delivery.exam_sitting (
        exam_version_id,
        sitting_code,
        sitting_name,
        scheduled_start_at,
        scheduled_end_at,
        timezone,
        sitting_status,
        created_by
    )
    VALUES (
        v_exam_version_id,
        suffix || '_SIT',
        suffix || ' Sitting',
        now() + interval '1 day',
        now() + interval '1 day 2 hours',
        'Asia/Ho_Chi_Minh',
        'READY',
        v_proctor_user_id
    )
    RETURNING exam_sitting_id INTO v_sitting_id;

    INSERT INTO delivery.exam_assignment (
        exam_sitting_id,
        student_id,
        assignment_status,
        assigned_by,
        note
    )
    VALUES (
        v_sitting_id,
        v_student_id,
        'ASSIGNED',
        v_proctor_user_id,
        suffix || ' Assignment'
    )
    RETURNING exam_assignment_id INTO v_assignment_id;

    INSERT INTO delivery.exam_session (
        exam_assignment_id,
        session_code,
        session_no,
        session_status,
        started_at,
        deadline_at,
        time_limit_seconds,
        extra_time_seconds,
        last_seen_at,
        last_activity_at,
        created_by
    )
    VALUES (
        v_assignment_id,
        suffix || '_SESSION',
        1,
        'IN_PROGRESS',
        now(),
        now() + interval '1 hour',
        3600,
        0,
        now(),
        now(),
        v_proctor_user_id
    )
    RETURNING exam_session_id INTO v_session_id;

    INSERT INTO delivery.generated_exam_instance (
        exam_session_id,
        exam_version_id,
        generation_mode,
        generation_status,
        generation_seed,
        generation_seed_hash,
        generator_name,
        generator_version,
        snapshot_version,
        instance_hash,
        generated_at,
        generated_by,
        metadata_json
    )
    VALUES (
        v_session_id,
        v_exam_version_id,
        'FIXED',
        'GENERATED',
        suffix || '_SEED',
        repeat('a', 64),
        'smoke-generator',
        '1.0.0',
        1,
        repeat('b', 64),
        now(),
        v_proctor_user_id,
        '{"source":"smoke-265"}'::jsonb
    )
    RETURNING generated_exam_instance_id INTO v_generated_exam_instance_id;

    INSERT INTO delivery.generated_exam_question (
        generated_exam_instance_id,
        question_template_id,
        question_order,
        question_code,
        question_type,
        rendered_question_text,
        score,
        metadata_json
    )
    VALUES (
        v_generated_exam_instance_id,
        v_question_template_id,
        1,
        suffix || '_Q1',
        'SQL_QUERY',
        'Case 5 score adjustment question',
        10.00,
        '{"source":"smoke-265"}'::jsonb
    )
    RETURNING generated_exam_question_id INTO v_generated_question_id;

    INSERT INTO delivery.generated_expected_answer (
        generated_exam_question_id,
        answer_order,
        solution_type,
        expected_payload,
        created_by,
        metadata_json
    )
    VALUES (
        v_generated_question_id,
        1,
        'SQL_TEXT',
        'SELECT 1;',
        v_proctor_user_id,
        '{"source":"smoke-265"}'::jsonb
    )
    RETURNING generated_expected_answer_id INTO v_generated_expected_answer_id;

    INSERT INTO submission.exam_submission (
        exam_session_id,
        generated_exam_instance_id,
        submission_status,
        opened_at,
        first_saved_at,
        last_saved_at,
        created_by,
        metadata_json
    )
    VALUES (
        v_session_id,
        v_generated_exam_instance_id,
        'IN_PROGRESS',
        now(),
        now(),
        now(),
        v_proctor_user_id,
        '{"source":"smoke-265"}'::jsonb
    )
    RETURNING exam_submission_id INTO v_exam_submission_id;

    INSERT INTO submission.submission_seal (
        exam_submission_id,
        seal_idempotency_key,
        seal_status,
        seal_reason,
        sealed_at,
        sealed_by,
        server_time_at_seal,
        answer_count,
        submission_hash,
        metadata_json
    )
    VALUES (
        v_exam_submission_id,
        suffix || '_SEAL1',
        'SEALED',
        'STUDENT_SUBMIT',
        now(),
        v_proctor_user_id,
        now(),
        1,
        repeat('c', 64),
        '{"source":"smoke-265"}'::jsonb
    )
    RETURNING submission_seal_id INTO v_submission_seal_id;

    INSERT INTO submission.sealed_answer (
        submission_seal_id,
        exam_submission_id,
        generated_exam_question_id,
        answer_type,
        answer_text,
        answer_hash,
        answer_length,
        sealed_at,
        metadata_json
    )
    VALUES (
        v_submission_seal_id,
        v_exam_submission_id,
        v_generated_question_id,
        'SQL_TEXT',
        'SELECT 1;',
        repeat('d', 64),
        9,
        now(),
        '{"source":"smoke-265"}'::jsonb
    )
    RETURNING sealed_answer_id INTO v_sealed_answer_id;

    SELECT answer_text, answer_hash::text
    INTO v_original_answer_text, v_original_answer_hash
    FROM submission.sealed_answer
    WHERE sealed_answer_id = v_sealed_answer_id;

    INSERT INTO grading.grading_job (
        exam_submission_id,
        submission_seal_id,
        exam_session_id,
        generated_exam_instance_id,
        grading_mode,
        grading_status,
        idempotency_key,
        requested_by,
        attempt_count,
        metadata_json
    )
    VALUES (
        v_exam_submission_id,
        v_submission_seal_id,
        v_session_id,
        v_generated_exam_instance_id,
        'AUTO',
        'COMPLETED',
        suffix || '_JOB1',
        v_proctor_user_id,
        0,
        '{"source":"smoke-265"}'::jsonb
    )
    RETURNING grading_job_id INTO v_grading_job_id;

    INSERT INTO grading.grading_run (
        grading_job_id,
        run_no,
        run_status,
        started_at,
        finished_at,
        worker_id,
        engine_batch_version,
        metadata_json
    )
    VALUES (
        v_grading_job_id,
        1,
        'COMPLETED',
        now(),
        now(),
        suffix || '_worker_1',
        'engine-batch-v6',
        '{"source":"smoke-265"}'::jsonb
    )
    RETURNING grading_run_id INTO v_grading_run_id;

    INSERT INTO grading.question_grading_task (
        grading_run_id,
        grading_job_id,
        exam_submission_id,
        submission_seal_id,
        sealed_answer_id,
        generated_exam_question_id,
        generated_expected_answer_id,
        question_grading_profile_id,
        grading_engine_id,
        input_source,
        answer_language,
        requires_capture,
        task_status,
        max_score,
        started_at,
        finished_at,
        profile_snapshot_json,
        expected_snapshot_json,
        metadata_json
    )
    VALUES (
        v_grading_run_id,
        v_grading_job_id,
        v_exam_submission_id,
        v_submission_seal_id,
        v_sealed_answer_id,
        v_generated_question_id,
        v_generated_expected_answer_id,
        NULL,
        v_sql_engine_id,
        'SEALED_TEXT_ANSWER',
        'SQL',
        false,
        'COMPLETED',
        10.00,
        now(),
        now(),
        '{"case":"case5"}'::jsonb,
        '{"case":"case5"}'::jsonb,
        '{"case":"case5"}'::jsonb
    )
    RETURNING question_grading_task_id INTO v_question_grading_task_id;

    INSERT INTO grading.actual_result (
        question_grading_task_id,
        result_type,
        result_payload_json,
        result_hash,
        row_count,
        runtime_ms,
        metadata_json
    )
    VALUES (
        v_question_grading_task_id,
        'SQL_RESULT_SET',
        '{"rows":[{"v":1}]}'::jsonb,
        repeat('1', 64),
        1,
        80,
        '{"case":"case5"}'::jsonb
    )
    RETURNING actual_result_id INTO v_actual_result_id;

    INSERT INTO grading.expected_actual_comparison (
        question_grading_task_id,
        generated_expected_answer_id,
        actual_result_id,
        comparison_method,
        comparison_status,
        expected_hash,
        actual_hash,
        comparison_payload_json,
        mismatch_summary,
        metadata_json
    )
    VALUES (
        v_question_grading_task_id,
        v_generated_expected_answer_id,
        v_actual_result_id,
        'EXACT_RESULT_SET',
        'MATCH',
        repeat('2', 64),
        repeat('3', 64),
        '{"matched":true}'::jsonb,
        NULL,
        '{"case":"case5"}'::jsonb
    )
    RETURNING comparison_id INTO v_comparison_id;

    INSERT INTO grading.question_score (
        question_grading_task_id,
        exam_submission_id,
        submission_seal_id,
        sealed_answer_id,
        generated_exam_question_id,
        raw_score,
        max_score,
        score_percent,
        score_status,
        scored_by_engine_id,
        requires_manual_review,
        feedback_json,
        metadata_json
    )
    VALUES (
        v_question_grading_task_id,
        v_exam_submission_id,
        v_submission_seal_id,
        v_sealed_answer_id,
        v_generated_question_id,
        8.00,
        10.00,
        80.0000,
        'SCORED',
        v_sql_engine_id,
        false,
        '{"summary":"initial score"}'::jsonb,
        '{"case":"case5"}'::jsonb
    )
    RETURNING question_score_id INTO v_question_score_id;

    INSERT INTO grading.submission_score (
        grading_job_id,
        exam_submission_id,
        submission_seal_id,
        score_version_no,
        is_current,
        total_raw_score,
        total_max_score,
        final_score,
        score_status,
        metadata_json
    )
    VALUES (
        v_grading_job_id,
        v_exam_submission_id,
        v_submission_seal_id,
        1,
        true,
        8.00,
        10.00,
        8.00,
        'COMPUTED',
        '{"case":"case5"}'::jsonb
    )
    RETURNING submission_score_id INTO v_submission_score_id;

    INSERT INTO grading.score_adjustment (
        question_score_id,
        submission_score_id,
        adjustment_type,
        old_score,
        new_score,
        reason,
        adjusted_by,
        metadata_json
    )
    VALUES (
        v_question_score_id,
        NULL,
        'TECHNICAL_CORRECTION',
        8.00,
        9.00,
        'Technical comparator threshold fix.',
        v_proctor_user_id,
        '{"case":"case5","target":"question"}'::jsonb
    )
    RETURNING score_adjustment_id INTO v_adjustment_question_id;

    INSERT INTO grading.score_adjustment (
        question_score_id,
        submission_score_id,
        adjustment_type,
        old_score,
        new_score,
        reason,
        adjusted_by,
        metadata_json
    )
    VALUES (
        NULL,
        v_submission_score_id,
        'MANUAL_OVERRIDE',
        8.00,
        9.00,
        'Manual override after quality review.',
        v_proctor_user_id,
        '{"case":"case5","target":"submission"}'::jsonb
    )
    RETURNING score_adjustment_id INTO v_adjustment_submission_id;

    INSERT INTO grading.grading_event (
        grading_job_id,
        grading_run_id,
        question_grading_task_id,
        event_type,
        actor_user_id,
        worker_id,
        event_payload_json
    )
    VALUES (
        v_grading_job_id,
        v_grading_run_id,
        v_question_grading_task_id,
        'SCORE_ADJUSTED',
        v_proctor_user_id,
        suffix || '_worker_1',
        '{"case":"case5","step":"score_adjusted"}'::jsonb
    )
    RETURNING grading_event_id INTO v_event_id;

    IF (
        SELECT COUNT(*)
        FROM grading.score_adjustment
        WHERE score_adjustment_id IN (v_adjustment_question_id, v_adjustment_submission_id)
    ) <> 2 THEN
        RAISE EXCEPTION 'Case 5 expected two score adjustment rows';
    END IF;

    IF (
        SELECT COUNT(*)
        FROM grading.grading_event
        WHERE grading_event_id = v_event_id
          AND event_type = 'SCORE_ADJUSTED'
    ) <> 1 THEN
        RAISE EXCEPTION 'Case 5 score adjustment event missing';
    END IF;

    IF (
        SELECT COUNT(*)
        FROM submission.sealed_answer sa
        WHERE sa.sealed_answer_id = v_sealed_answer_id
          AND sa.answer_text = v_original_answer_text
          AND sa.answer_hash::text = v_original_answer_hash
    ) <> 1 THEN
        RAISE EXCEPTION 'Case 5 sealed_answer provenance changed unexpectedly after adjustments';
    END IF;

    RAISE NOTICE 'PASS: Phase 5A case 5 score adjustment/provenance graph succeeded.';
END
$$;

ROLLBACK;
