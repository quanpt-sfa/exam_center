-- Verifies full Phase 3.2 generated exam snapshot insert graph in a transaction.

BEGIN;

DO
$$
DECLARE
    suffix text := 'SMOKE_P32_' || txid_current()::text;

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

    v_question_bank_id bigint;
    v_question_template_id bigint;
    v_parameter_definition_id bigint;
    v_reference_solution_id bigint;
    v_blueprint_id bigint;
    v_blueprint_section_id bigint;
    v_blueprint_rule_id bigint;

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
    v_generated_parameter_id bigint;
    v_generated_expected_answer_id bigint;

    duplicate_instance_conflict boolean := false;
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
        'hash_p32_proctor',
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
        'Phase 3.2 generated snapshot insert graph',
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

    INSERT INTO assessment.question_bank (
        course_id,
        bank_code,
        bank_name,
        description,
        owner_user_id,
        status
    )
    VALUES (
        v_course_id,
        suffix || '_BANK',
        suffix || ' Question Bank',
        'Phase 3.2 smoke bank',
        v_proctor_user_id,
        'ACTIVE'
    )
    RETURNING question_bank_id INTO v_question_bank_id;

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
        'Write a query that returns exactly one row.',
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

    INSERT INTO assessment.question_template_bank (
        question_bank_id,
        question_template_id,
        added_by,
        is_active
    )
    VALUES (
        v_question_bank_id,
        v_question_template_id,
        v_proctor_user_id,
        true
    );

    INSERT INTO assessment.question_parameter_definition (
        question_template_id,
        parameter_name,
        parameter_type,
        generation_rule_json,
        default_value_json,
        is_required
    )
    VALUES (
        v_question_template_id,
        'customer_id',
        'INTEGER',
        '{"strategy":"seeded"}'::jsonb,
        '1'::jsonb,
        true
    )
    RETURNING parameter_id INTO v_parameter_definition_id;

    INSERT INTO assessment.reference_solution (
        question_template_id,
        solution_type,
        solution_payload,
        solution_payload_json,
        artifact_ref,
        solution_hash,
        status,
        created_by
    )
    VALUES (
        v_question_template_id,
        'SQL_REFERENCE_QUERY',
        'SELECT 1;',
        '{"rows":[{"value":1}]}'::jsonb,
        NULL,
        repeat('a', 64),
        'ACTIVE',
        v_proctor_user_id
    )
    RETURNING reference_solution_id INTO v_reference_solution_id;

    INSERT INTO assessment.exam_blueprint (
        exam_version_id,
        blueprint_code,
        blueprint_name,
        total_questions,
        total_score,
        randomization_mode,
        status
    )
    VALUES (
        v_exam_version_id,
        suffix || '_BP',
        suffix || ' Blueprint',
        1,
        10.00,
        'PARAMETERIZED',
        'ACTIVE'
    )
    RETURNING blueprint_id INTO v_blueprint_id;

    INSERT INTO assessment.exam_blueprint_section (
        blueprint_id,
        section_code,
        section_name,
        section_order,
        description,
        shuffle_within_section
    )
    VALUES (
        v_blueprint_id,
        suffix || '_SEC',
        suffix || ' Section',
        1,
        'Section for Phase 3.2 smoke.',
        false
    )
    RETURNING blueprint_section_id INTO v_blueprint_section_id;

    INSERT INTO assessment.exam_blueprint_rule (
        blueprint_section_id,
        question_bank_id,
        question_type,
        topic_code,
        skill_code,
        difficulty_level,
        number_of_questions,
        score_per_question,
        selection_strategy,
        allow_replacement,
        rule_order
    )
    VALUES (
        v_blueprint_section_id,
        v_question_bank_id,
        'SQL_QUERY',
        'TOPIC1',
        'SKILL1',
        'MEDIUM',
        1,
        10.00,
        'SEEDED_RANDOM',
        false,
        1
    )
    RETURNING blueprint_rule_id INTO v_blueprint_rule_id;

    INSERT INTO assessment.exam_blueprint_rule_question (
        blueprint_rule_id,
        question_template_id,
        weight,
        is_active
    )
    VALUES (
        v_blueprint_rule_id,
        v_question_template_id,
        1.0,
        true
    );

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
        v_blueprint_id,
        'PARAMETERIZED',
        'GENERATED',
        suffix || '_SEED',
        repeat('b', 64),
        'smoke-generator',
        '1.0.0',
        1,
        repeat('c', 64),
        now(),
        v_proctor_user_id,
        '{"source":"smoke-117"}'::jsonb
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
        v_blueprint_rule_id,
        1,
        suffix || '_Q01',
        'SQL_QUERY',
        'Return the customer with id {{customer_id}}.',
        '{"customer_id":123}'::jsonb,
        10.00,
        '{"origin":"smoke-117"}'::jsonb
    )
    RETURNING generated_exam_question_id INTO v_generated_exam_question_id;

    INSERT INTO delivery.generated_question_parameter (
        generated_exam_question_id,
        parameter_definition_id,
        parameter_name,
        parameter_type,
        parameter_value_json,
        parameter_display_value
    )
    VALUES (
        v_generated_exam_question_id,
        v_parameter_definition_id,
        'customer_id',
        'INTEGER',
        '123'::jsonb,
        '123'
    )
    RETURNING generated_parameter_id INTO v_generated_parameter_id;

    INSERT INTO delivery.generated_expected_answer (
        generated_exam_question_id,
        reference_solution_id,
        answer_order,
        solution_type,
        expected_payload,
        expected_payload_json,
        expected_hash,
        created_by,
        metadata_json
    )
    VALUES (
        v_generated_exam_question_id,
        v_reference_solution_id,
        1,
        'SQL_RESULT',
        NULL,
        '{"rows":[{"value":1}]}'::jsonb,
        repeat('d', 64),
        v_proctor_user_id,
        '{"source":"smoke-117"}'::jsonb
    )
    RETURNING generated_expected_answer_id INTO v_generated_expected_answer_id;

    BEGIN
        INSERT INTO delivery.generated_exam_instance (
            exam_session_id,
            exam_version_id,
            blueprint_id,
            generation_mode,
            generation_status,
            generated_at,
            generated_by
        )
        VALUES (
            v_session_id,
            v_exam_version_id,
            v_blueprint_id,
            'PARAMETERIZED',
            'GENERATED',
            now(),
            v_proctor_user_id
        );
    EXCEPTION
        WHEN unique_violation THEN
            duplicate_instance_conflict := true;
    END;

    IF NOT duplicate_instance_conflict THEN
        RAISE EXCEPTION 'Expected unique_violation for second generated_exam_instance on same exam_session';
    END IF;

    IF (SELECT COUNT(*) FROM delivery.generated_exam_instance WHERE generated_exam_instance_id = v_generated_exam_instance_id) <> 1 THEN
        RAISE EXCEPTION 'Expected generated_exam_instance insert to persist inside transaction scope';
    END IF;

    IF (SELECT COUNT(*) FROM delivery.generated_exam_question WHERE generated_exam_question_id = v_generated_exam_question_id) <> 1 THEN
        RAISE EXCEPTION 'Expected generated_exam_question insert to persist inside transaction scope';
    END IF;

    IF (SELECT COUNT(*) FROM delivery.generated_question_parameter WHERE generated_parameter_id = v_generated_parameter_id) <> 1 THEN
        RAISE EXCEPTION 'Expected generated_question_parameter insert to persist inside transaction scope';
    END IF;

    IF (SELECT COUNT(*) FROM delivery.generated_expected_answer WHERE generated_expected_answer_id = v_generated_expected_answer_id) <> 1 THEN
        RAISE EXCEPTION 'Expected generated_expected_answer insert to persist inside transaction scope';
    END IF;

    RAISE NOTICE 'PASS: Phase 3.2 full insert graph and immutable-per-session guard validated.';
END
$$;

ROLLBACK;
