-- Verifies transactional inserts for Phase 5.3 actual_result and expected_actual_comparison cases, then rolls back.

BEGIN;

DO
$$
DECLARE
    suffix text := 'SMOKE_P53_' || txid_current()::text;

    v_department_id bigint;
    v_program_id bigint;
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
    v_generated_question_1_id bigint;
    v_generated_question_2_id bigint;
    v_generated_expected_answer_1_id bigint;
    v_generated_expected_answer_2_id bigint;

    v_sitting_id bigint;
    v_assignment_id bigint;
    v_session_id bigint;
    v_generated_exam_instance_id bigint;
    v_exam_submission_id bigint;
    v_submission_seal_id bigint;
    v_sealed_answer_id bigint;

    v_grading_job_id bigint;
    v_grading_run_id bigint;

    v_sql_engine_id bigint;
    v_misa_engine_id bigint;

    v_capture_job_id bigint;

    v_task_a_id bigint;
    v_task_b_id bigint;

    v_actual_result_a_id bigint;
    v_actual_result_b_id bigint;
    v_comparison_a_id bigint;
    v_comparison_b_id bigint;
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

    SELECT grading_engine_id
    INTO v_misa_engine_id
    FROM grading.grading_engine
    WHERE engine_code = 'MISA_DATABASE_COMPARATOR'
    ORDER BY grading_engine_id
    LIMIT 1;

    IF v_misa_engine_id IS NULL THEN
        RAISE EXCEPTION 'Required grading engine MISA_DATABASE_COMPARATOR is missing.';
    END IF;

    INSERT INTO academic.department (department_code, department_name, status)
    VALUES (suffix || '_DEPT', suffix || ' Department', 'ACTIVE')
    RETURNING department_id INTO v_department_id;

    INSERT INTO academic.program (department_id, program_code, program_name, program_level, status)
    VALUES (v_department_id, suffix || '_PROG', suffix || ' Program', 'UNDERGRADUATE', 'ACTIVE')
    RETURNING program_id INTO v_program_id;

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
        v_program_id,
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
        'hash_p53_proctor',
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
        'Phase 5.3 actual/comparison transactional smoke',
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
        'Write a deterministic SQL query.',
        'TOPIC1',
        'SKILL1',
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
        '{"source":"smoke-233"}'::jsonb
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
        'Case A SQL question',
        10.00,
        '{"source":"smoke-233"}'::jsonb
    )
    RETURNING generated_exam_question_id INTO v_generated_question_1_id;

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
        2,
        suffix || '_Q2',
        'MISA_TASK',
        'Case B MISA question',
        10.00,
        '{"source":"smoke-233"}'::jsonb
    )
    RETURNING generated_exam_question_id INTO v_generated_question_2_id;

    INSERT INTO delivery.generated_expected_answer (
        generated_exam_question_id,
        answer_order,
        solution_type,
        expected_payload,
        created_by,
        metadata_json
    )
    VALUES (
        v_generated_question_1_id,
        1,
        'SQL_TEXT',
        'SELECT 1;',
        v_proctor_user_id,
        '{"source":"smoke-233"}'::jsonb
    )
    RETURNING generated_expected_answer_id INTO v_generated_expected_answer_1_id;

    INSERT INTO delivery.generated_expected_answer (
        generated_exam_question_id,
        answer_order,
        solution_type,
        expected_payload_json,
        created_by,
        metadata_json
    )
    VALUES (
        v_generated_question_2_id,
        1,
        'ACCOUNTING_REPORT',
        '{"balance":100}'::jsonb,
        v_proctor_user_id,
        '{"source":"smoke-233"}'::jsonb
    )
    RETURNING generated_expected_answer_id INTO v_generated_expected_answer_2_id;

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
        '{"source":"smoke-233"}'::jsonb
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
        '{"source":"smoke-233"}'::jsonb
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
        v_generated_question_1_id,
        'SQL_TEXT',
        'SELECT 1;',
        repeat('d', 64),
        9,
        now(),
        '{"source":"smoke-233"}'::jsonb
    )
    RETURNING sealed_answer_id INTO v_sealed_answer_id;

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
        'QUEUED',
        suffix || '_JOB1',
        v_proctor_user_id,
        0,
        '{"source":"smoke-233"}'::jsonb
    )
    RETURNING grading_job_id INTO v_grading_job_id;

    INSERT INTO grading.grading_run (
        grading_job_id,
        run_no,
        run_status,
        started_at,
        worker_id,
        engine_batch_version,
        metadata_json
    )
    VALUES (
        v_grading_job_id,
        1,
        'RUNNING',
        now(),
        suffix || '_worker_1',
        'engine-batch-v3',
        '{"source":"smoke-233"}'::jsonb
    )
    RETURNING grading_run_id INTO v_grading_run_id;

    INSERT INTO capture.capture_job (
        exam_submission_id,
        submission_seal_id,
        exam_session_id,
        generated_exam_instance_id,
        idempotency_key,
        capture_type,
        capture_status,
        requested_by,
        metadata_json
    )
    VALUES (
        v_exam_submission_id,
        v_submission_seal_id,
        v_session_id,
        v_generated_exam_instance_id,
        suffix || '_CAP1',
        'MISA_DATABASE_SNAPSHOT',
        'COMPLETED',
        v_proctor_user_id,
        '{"source":"smoke-233"}'::jsonb
    )
    RETURNING capture_job_id INTO v_capture_job_id;

    INSERT INTO grading.question_grading_task (
        grading_run_id,
        grading_job_id,
        exam_submission_id,
        submission_seal_id,
        sealed_answer_id,
        generated_exam_question_id,
        generated_expected_answer_id,
        grading_engine_id,
        input_source,
        answer_language,
        requires_capture,
        task_status,
        max_score,
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
        v_generated_question_1_id,
        v_generated_expected_answer_1_id,
        v_sql_engine_id,
        'SEALED_TEXT_ANSWER',
        'SQL',
        false,
        'QUEUED',
        10.00,
        '{"case":"A"}'::jsonb,
        '{"case":"A"}'::jsonb,
        '{"case":"A"}'::jsonb
    )
    RETURNING question_grading_task_id INTO v_task_a_id;

    INSERT INTO grading.question_grading_task (
        grading_run_id,
        grading_job_id,
        exam_submission_id,
        submission_seal_id,
        sealed_answer_id,
        generated_exam_question_id,
        generated_expected_answer_id,
        grading_engine_id,
        input_source,
        answer_language,
        requires_capture,
        capture_job_id,
        task_status,
        max_score,
        profile_snapshot_json,
        expected_snapshot_json,
        metadata_json
    )
    VALUES (
        v_grading_run_id,
        v_grading_job_id,
        v_exam_submission_id,
        v_submission_seal_id,
        NULL,
        v_generated_question_2_id,
        v_generated_expected_answer_2_id,
        v_misa_engine_id,
        'MISA_DATABASE_CAPTURE',
        'NONE',
        true,
        v_capture_job_id,
        'QUEUED',
        10.00,
        '{"case":"B"}'::jsonb,
        '{"case":"B"}'::jsonb,
        '{"case":"B"}'::jsonb
    )
    RETURNING question_grading_task_id INTO v_task_b_id;

    -- Case A: SQL full match
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
        v_task_a_id,
        'SQL_RESULT_SET',
        '{"rows":[{"value":1}],"columns":["value"]}'::jsonb,
        repeat('e', 64),
        1,
        45,
        '{"case":"A"}'::jsonb
    )
    RETURNING actual_result_id INTO v_actual_result_a_id;

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
        v_task_a_id,
        v_generated_expected_answer_1_id,
        v_actual_result_a_id,
        'ORDER_INSENSITIVE_RESULT_SET',
        'MATCH',
        repeat('f', 64),
        repeat('e', 64),
        '{"matched":true}'::jsonb,
        NULL,
        '{"case":"A"}'::jsonb
    )
    RETURNING comparison_id INTO v_comparison_a_id;

    -- Case B: MISA mismatch/partial
    INSERT INTO grading.actual_result (
        question_grading_task_id,
        result_type,
        result_payload_json,
        result_artifact_ref,
        result_hash,
        row_count,
        runtime_ms,
        metadata_json
    )
    VALUES (
        v_task_b_id,
        'MISA_NORMALIZED_DATA',
        '{"summary":{"delta":2.5}}'::jsonb,
        suffix || '_misa_artifact_ref',
        repeat('1', 64),
        12,
        180,
        '{"case":"B"}'::jsonb
    )
    RETURNING actual_result_id INTO v_actual_result_b_id;

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
        v_task_b_id,
        v_generated_expected_answer_2_id,
        v_actual_result_b_id,
        'ACCOUNTING_BALANCE_CHECK',
        'PARTIAL_MATCH',
        repeat('2', 64),
        repeat('1', 64),
        '{"variance":2.5,"tolerance":1.0}'::jsonb,
        'Ledger totals differ by 2.5 after normalization.',
        '{"case":"B"}'::jsonb
    )
    RETURNING comparison_id INTO v_comparison_b_id;

    IF (SELECT COUNT(*) FROM grading.actual_result WHERE actual_result_id = v_actual_result_a_id) <> 1 THEN
        RAISE EXCEPTION 'Case A actual_result insert did not persist in transaction scope';
    END IF;

    IF (SELECT COUNT(*) FROM grading.expected_actual_comparison WHERE comparison_id = v_comparison_a_id) <> 1 THEN
        RAISE EXCEPTION 'Case A expected_actual_comparison insert did not persist in transaction scope';
    END IF;

    IF (SELECT COUNT(*) FROM grading.actual_result WHERE actual_result_id = v_actual_result_b_id) <> 1 THEN
        RAISE EXCEPTION 'Case B actual_result insert did not persist in transaction scope';
    END IF;

    IF (SELECT COUNT(*) FROM grading.expected_actual_comparison WHERE comparison_id = v_comparison_b_id) <> 1 THEN
        RAISE EXCEPTION 'Case B expected_actual_comparison insert did not persist in transaction scope';
    END IF;

    RAISE NOTICE 'PASS: Phase 5.3 transactional insert cases A/B succeeded.';
END
$$;

ROLLBACK;
