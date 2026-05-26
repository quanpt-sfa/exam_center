-- Verifies Phase 4.4 answer_conflict insert graph on top of full Phase 4.2 graph in a transaction.

BEGIN;

DO
$$
DECLARE
    suffix text := 'SMOKE_P44_' || txid_current()::text;

    v_department_id bigint;
    v_program_id bigint;
    v_term_id bigint;
    v_course_id bigint;
    v_course_offering_id bigint;
    v_class_section_id bigint;

    v_student_person_id bigint;
    v_proctor_person_id bigint;
    v_student_id bigint;
    v_instructor_id bigint;
    v_proctor_user_id bigint;

    v_assessment_type_id bigint;
    v_exam_id bigint;
    v_exam_version_id bigint;
    v_question_template_id bigint;

    v_room_id bigint;
    v_station_id bigint;
    v_device_id bigint;

    v_sitting_id bigint;
    v_sitting_room_id bigint;
    v_assignment_id bigint;
    v_station_assignment_id bigint;
    v_session_id bigint;

    v_generated_exam_instance_id bigint;
    v_generated_exam_question_id bigint;
    v_exam_submission_id bigint;
    v_answer_state_id bigint;
    v_answer_save_batch_id bigint;
    v_answer_save_item_id bigint;
    v_answer_conflict_id bigint;
BEGIN
    SELECT assessment_type_id
    INTO v_assessment_type_id
    FROM assessment.assessment_type
    WHERE type_code = 'QUIZ';

    IF v_assessment_type_id IS NULL THEN
        RAISE EXCEPTION 'Required seed QUIZ in assessment.assessment_type is missing.';
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

    INSERT INTO identity.instructor_profile (person_id, instructor_code, department_id, instructor_status)
    VALUES (v_proctor_person_id, suffix || '_INS', v_department_id, 'ACTIVE')
    RETURNING instructor_id INTO v_instructor_id;

    INSERT INTO identity.app_user (person_id, username, email_login, password_hash, user_status)
    VALUES (
        v_proctor_person_id,
        lower(suffix) || '_proctor',
        lower(suffix) || '@local.test',
        'hash_p44_proctor',
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
        'Phase 4.4 conflict insert graph',
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
        'PARAMETERIZED',
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
        suffix || '_QT',
        'SQL_QUERY',
        suffix || ' Template',
        'Return exactly one row.',
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

    INSERT INTO facility.room (
        room_code,
        room_name,
        building,
        floor_no,
        capacity,
        room_type,
        status
    )
    VALUES (
        suffix || '_ROOM',
        suffix || ' Room',
        'Building K',
        '11',
        40,
        'LAB',
        'ACTIVE'
    )
    RETURNING room_id INTO v_room_id;

    INSERT INTO facility.lab_station (
        room_id,
        station_code,
        seat_no,
        row_no,
        column_no,
        status
    )
    VALUES (
        v_room_id,
        suffix || '_ST01',
        'S01',
        'R1',
        'C1',
        'ACTIVE'
    )
    RETURNING station_id INTO v_station_id;

    INSERT INTO facility.device (
        asset_tag,
        device_name,
        device_type,
        serial_no,
        current_station_id,
        status
    )
    VALUES (
        suffix || '_ASSET1',
        suffix || ' Device 1',
        'LAB_PC',
        suffix || '_SERIAL1',
        v_station_id,
        'ACTIVE'
    )
    RETURNING device_id INTO v_device_id;

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

    INSERT INTO delivery.exam_sitting_room (
        exam_sitting_id,
        room_id,
        capacity_allocated,
        room_status
    )
    VALUES (
        v_sitting_id,
        v_room_id,
        40,
        'READY'
    )
    RETURNING exam_sitting_room_id INTO v_sitting_room_id;

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

    INSERT INTO delivery.exam_station_assignment (
        exam_assignment_id,
        exam_sitting_room_id,
        station_id,
        planned_device_id,
        assigned_by,
        status
    )
    VALUES (
        v_assignment_id,
        v_sitting_room_id,
        v_station_id,
        v_device_id,
        v_proctor_user_id,
        'ASSIGNED'
    )
    RETURNING station_assignment_id INTO v_station_assignment_id;

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
        blueprint_id,
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
        NULL,
        'FIXED',
        'GENERATED',
        suffix || '_SEED',
        repeat('b', 64),
        'smoke-generator',
        '1.0.0',
        1,
        repeat('c', 64),
        now(),
        v_proctor_user_id,
        '{"source":"smoke-141"}'::jsonb
    )
    RETURNING generated_exam_instance_id INTO v_generated_exam_instance_id;

    INSERT INTO delivery.generated_exam_question (
        generated_exam_instance_id,
        question_template_id,
        blueprint_rule_id,
        question_order,
        question_code,
        question_type,
        rendered_question_text,
        rendered_question_payload_json,
        score,
        metadata_json
    )
    VALUES (
        v_generated_exam_instance_id,
        v_question_template_id,
        NULL,
        1,
        suffix || '_Q01',
        'SQL_QUERY',
        'Write a query returning one row.',
        '{"difficulty":"MEDIUM"}'::jsonb,
        10.00,
        '{"source":"smoke-141"}'::jsonb
    )
    RETURNING generated_exam_question_id INTO v_generated_exam_question_id;

    INSERT INTO submission.exam_submission (
        exam_session_id,
        generated_exam_instance_id,
        submission_status,
        opened_at,
        created_by,
        metadata_json
    )
    VALUES (
        v_session_id,
        v_generated_exam_instance_id,
        'IN_PROGRESS',
        now(),
        v_proctor_user_id,
        '{"source":"smoke-141"}'::jsonb
    )
    RETURNING exam_submission_id INTO v_exam_submission_id;

    INSERT INTO submission.answer_state (
        exam_submission_id,
        generated_exam_question_id,
        answer_type,
        answer_text,
        answer_hash,
        answer_length,
        client_version,
        server_version,
        client_saved_at,
        last_saved_at,
        last_saved_by_device_id,
        last_saved_by_station_id,
        answer_status,
        metadata_json
    )
    VALUES (
        v_exam_submission_id,
        v_generated_exam_question_id,
        'SQL_TEXT',
        'SELECT 1;',
        repeat('d', 64),
        9,
        1,
        1,
        now(),
        now(),
        v_device_id,
        v_station_id,
        'ACCEPTED',
        '{"source":"smoke-141"}'::jsonb
    )
    RETURNING answer_state_id INTO v_answer_state_id;

    INSERT INTO submission.answer_save_batch (
        exam_submission_id,
        idempotency_key,
        client_sequence_no,
        client_saved_at,
        server_received_at,
        device_id,
        station_id,
        batch_status,
        accepted_item_count,
        rejected_item_count,
        metadata_json
    )
    VALUES (
        v_exam_submission_id,
        suffix || '_BATCH1',
        1,
        now(),
        now(),
        v_device_id,
        v_station_id,
        'APPLIED',
        1,
        0,
        '{"source":"smoke-141"}'::jsonb
    )
    RETURNING answer_save_batch_id INTO v_answer_save_batch_id;

    INSERT INTO submission.answer_save_item (
        answer_save_batch_id,
        generated_exam_question_id,
        answer_state_id,
        client_version,
        server_version,
        answer_hash,
        answer_length,
        item_status,
        saved_at,
        error_code,
        error_message
    )
    VALUES (
        v_answer_save_batch_id,
        v_generated_exam_question_id,
        v_answer_state_id,
        1,
        1,
        repeat('d', 64),
        9,
        'APPLIED',
        now(),
        NULL,
        NULL
    )
    RETURNING answer_save_item_id INTO v_answer_save_item_id;

    INSERT INTO submission.answer_conflict (
        exam_submission_id,
        generated_exam_question_id,
        answer_state_id,
        client_version,
        server_version,
        conflict_type,
        client_payload_json,
        server_payload_json,
        detected_at,
        resolved_status,
        resolved_at,
        resolved_by,
        note
    )
    VALUES (
        v_exam_submission_id,
        v_generated_exam_question_id,
        v_answer_state_id,
        1,
        2,
        'VERSION_MISMATCH',
        '{"sql":"SELECT * FROM t"}'::jsonb,
        '{"sql":"SELECT id FROM t"}'::jsonb,
        now(),
        'UNRESOLVED',
        NULL,
        NULL,
        'Conflict detected during reconnect validation.'
    )
    RETURNING answer_conflict_id INTO v_answer_conflict_id;

    IF (SELECT COUNT(*) FROM submission.answer_state WHERE answer_state_id = v_answer_state_id) <> 1 THEN
        RAISE EXCEPTION 'Expected answer_state insert to persist inside transaction scope';
    END IF;

    IF (SELECT COUNT(*) FROM submission.answer_save_batch WHERE answer_save_batch_id = v_answer_save_batch_id) <> 1 THEN
        RAISE EXCEPTION 'Expected answer_save_batch insert to persist inside transaction scope';
    END IF;

    IF (SELECT COUNT(*) FROM submission.answer_save_item WHERE answer_save_item_id = v_answer_save_item_id) <> 1 THEN
        RAISE EXCEPTION 'Expected answer_save_item insert to persist inside transaction scope';
    END IF;

    IF (SELECT COUNT(*) FROM submission.answer_conflict WHERE answer_conflict_id = v_answer_conflict_id) <> 1 THEN
        RAISE EXCEPTION 'Expected answer_conflict insert to persist inside transaction scope';
    END IF;

    RAISE NOTICE 'PASS: Phase 4.4 answer_conflict insert graph with Phase 4.2 prerequisites validated.';
END
$$;

ROLLBACK;
