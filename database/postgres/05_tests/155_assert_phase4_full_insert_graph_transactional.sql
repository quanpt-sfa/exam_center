-- Verifies full Phase 4 insert graph in a transaction and confirms all key runtime rows persist before rollback.

BEGIN;

DO
$$
DECLARE
    suffix text := 'SMOKE_P46_' || txid_current()::text;

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
    v_station_1_id bigint;
    v_station_2_id bigint;
    v_device_1_id bigint;
    v_device_2_id bigint;

    v_sitting_id bigint;
    v_sitting_room_id bigint;
    v_proctor_assignment_id bigint;
    v_assignment_id bigint;
    v_station_assignment_id bigint;
    v_session_id bigint;

    v_generated_exam_instance_id bigint;
    v_generated_exam_question_id bigint;
    v_generated_parameter_id bigint;
    v_generated_expected_answer_id bigint;

    v_exam_submission_id bigint;
    v_answer_state_id bigint;
    v_answer_save_batch_id bigint;
    v_answer_save_item_id bigint;
    v_submission_seal_id bigint;
    v_sealed_answer_id bigint;
    v_answer_conflict_id bigint;

    v_capture_job_id bigint;
    v_capture_artifact_id bigint;
    v_capture_dataset_id bigint;
    v_capture_dataset_row_id bigint;
    v_capture_job_event_id bigint;
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
        'hash_p46_proctor',
        'ACTIVE'
    )
    RETURNING user_id INTO v_proctor_user_id;

    INSERT INTO academic.class_enrollment (class_section_id, student_id, enrollment_status, note)
    VALUES (v_class_section_id, v_student_id, 'ENROLLED', suffix || ' Enrollment');

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
        'Phase 4 full insert graph',
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
        'Phase 4 full graph bank',
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
        'Write deterministic SQL query.',
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
        'store_id',
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
        'Phase 4 full graph section',
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

    INSERT INTO facility.lab_station (room_id, station_code, seat_no, row_no, column_no, status)
    VALUES (v_room_id, suffix || '_ST01', 'S01', 'R1', 'C1', 'ACTIVE')
    RETURNING station_id INTO v_station_1_id;

    INSERT INTO facility.lab_station (room_id, station_code, seat_no, row_no, column_no, status)
    VALUES (v_room_id, suffix || '_ST02', 'S02', 'R1', 'C2', 'ACTIVE')
    RETURNING station_id INTO v_station_2_id;

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
        v_station_1_id,
        'ACTIVE'
    )
    RETURNING device_id INTO v_device_1_id;

    INSERT INTO facility.device (
        asset_tag,
        device_name,
        device_type,
        serial_no,
        current_station_id,
        status
    )
    VALUES (
        suffix || '_ASSET2',
        suffix || ' Device 2',
        'LAB_PC',
        suffix || '_SERIAL2',
        v_station_2_id,
        'ACTIVE'
    )
    RETURNING device_id INTO v_device_2_id;

    INSERT INTO facility.device_registration (
        device_id,
        registration_type,
        registration_value,
        valid_from,
        valid_to
    )
    VALUES (
        v_device_1_id,
        'HOSTNAME',
        lower(suffix) || '-host-1.local',
        now(),
        NULL
    );

    INSERT INTO facility.device_checkin (
        device_id,
        station_id,
        checkin_at,
        ip_address,
        hostname,
        client_fingerprint,
        health_status,
        metadata_json
    )
    VALUES (
        v_device_1_id,
        v_station_1_id,
        now(),
        '127.0.0.1'::inet,
        lower(suffix) || '-host-1',
        lower(suffix) || '-fp-1',
        'READY',
        '{"source":"smoke-155"}'::jsonb
    );

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

    INSERT INTO delivery.proctor_assignment (
        exam_sitting_room_id,
        proctor_user_id,
        proctor_role,
        assigned_by,
        status
    )
    VALUES (
        v_sitting_room_id,
        v_proctor_user_id,
        'ROOM_PROCTOR',
        v_proctor_user_id,
        'ASSIGNED'
    )
    RETURNING proctor_assignment_id INTO v_proctor_assignment_id;

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
        v_station_1_id,
        v_device_1_id,
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
        '{"source":"smoke-155"}'::jsonb
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
        'Return one row.',
        '{"store_id":1}'::jsonb,
        10.00,
        '{"source":"smoke-155"}'::jsonb
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
        'store_id',
        'INTEGER',
        '1'::jsonb,
        '1'
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
        '{"source":"smoke-155"}'::jsonb
    )
    RETURNING generated_expected_answer_id INTO v_generated_expected_answer_id;

    INSERT INTO submission.exam_submission (
        exam_session_id,
        generated_exam_instance_id,
        submission_status,
        opened_at,
        first_saved_at,
        last_saved_at,
        submitted_at,
        sealed_at,
        seal_reason,
        created_by,
        metadata_json
    )
    VALUES (
        v_session_id,
        v_generated_exam_instance_id,
        'IN_PROGRESS',
        now(),
        now(),
        now() + interval '2 minute',
        NULL,
        NULL,
        NULL,
        v_proctor_user_id,
        '{"source":"smoke-155"}'::jsonb
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
        repeat('e', 64),
        9,
        1,
        1,
        now(),
        now(),
        v_device_1_id,
        v_station_1_id,
        'ACCEPTED',
        '{"source":"smoke-155"}'::jsonb
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
        v_device_1_id,
        v_station_1_id,
        'APPLIED',
        1,
        0,
        '{"source":"smoke-155"}'::jsonb
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
        repeat('e', 64),
        9,
        'APPLIED',
        now(),
        NULL,
        NULL
    )
    RETURNING answer_save_item_id INTO v_answer_save_item_id;

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
        repeat('f', 64),
        '{"source":"smoke-155"}'::jsonb
    )
    RETURNING submission_seal_id INTO v_submission_seal_id;

    INSERT INTO submission.sealed_answer (
        submission_seal_id,
        exam_submission_id,
        generated_exam_question_id,
        answer_state_id,
        answer_type,
        answer_text,
        answer_payload_json,
        answer_hash,
        answer_length,
        sealed_at,
        metadata_json
    )
    VALUES (
        v_submission_seal_id,
        v_exam_submission_id,
        v_generated_exam_question_id,
        v_answer_state_id,
        'SQL_TEXT',
        'SELECT 1;',
        NULL,
        repeat('e', 64),
        9,
        now(),
        '{"source":"smoke-155"}'::jsonb
    )
    RETURNING sealed_answer_id INTO v_sealed_answer_id;

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
        'Conflict detected during full graph validation.'
    )
    RETURNING answer_conflict_id INTO v_answer_conflict_id;

    INSERT INTO capture.capture_job (
        exam_submission_id,
        submission_seal_id,
        exam_session_id,
        generated_exam_instance_id,
        idempotency_key,
        capture_type,
        capture_status,
        requested_at,
        started_at,
        finished_at,
        attempt_count,
        requested_by,
        worker_id,
        error_code,
        error_message,
        metadata_json
    )
    VALUES (
        v_exam_submission_id,
        v_submission_seal_id,
        v_session_id,
        v_generated_exam_instance_id,
        suffix || '_CAPJOB1',
        'SQL_QUERY_TEXT_ONLY',
        'COMPLETED',
        now(),
        now(),
        now() + interval '1 second',
        1,
        v_proctor_user_id,
        'worker-smoke',
        NULL,
        NULL,
        '{"source":"smoke-155"}'::jsonb
    )
    RETURNING capture_job_id INTO v_capture_job_id;

    INSERT INTO capture.capture_artifact (
        capture_job_id,
        artifact_type,
        artifact_ref,
        artifact_hash,
        artifact_size_bytes,
        content_type,
        metadata_json
    )
    VALUES (
        v_capture_job_id,
        'RAW_JSON',
        'local://capture/' || lower(suffix) || '/artifact_1.json',
        repeat('1', 64),
        128,
        'application/json',
        '{"source":"smoke-155"}'::jsonb
    )
    RETURNING capture_artifact_id INTO v_capture_artifact_id;

    INSERT INTO capture.capture_dataset (
        capture_job_id,
        dataset_name,
        dataset_schema_json,
        row_count,
        dataset_hash,
        metadata_json
    )
    VALUES (
        v_capture_job_id,
        'students',
        '{"columns":[{"name":"student_code","type":"text"}]}'::jsonb,
        1,
        repeat('2', 64),
        '{"source":"smoke-155"}'::jsonb
    )
    RETURNING capture_dataset_id INTO v_capture_dataset_id;

    INSERT INTO capture.capture_dataset_row (
        capture_dataset_id,
        row_no,
        row_payload_json,
        row_hash
    )
    VALUES (
        v_capture_dataset_id,
        1,
        '{"student_code":"S0001"}'::jsonb,
        repeat('3', 64)
    )
    RETURNING capture_dataset_row_id INTO v_capture_dataset_row_id;

    INSERT INTO capture.capture_job_event (
        capture_job_id,
        event_type,
        event_at,
        actor_user_id,
        event_payload_json
    )
    VALUES (
        v_capture_job_id,
        'CAPTURE_COMPLETED',
        now(),
        v_proctor_user_id,
        '{"source":"smoke-155"}'::jsonb
    )
    RETURNING capture_job_event_id INTO v_capture_job_event_id;

    IF (SELECT COUNT(*) FROM submission.exam_submission WHERE exam_submission_id = v_exam_submission_id) <> 1 THEN
        RAISE EXCEPTION 'Expected submission.exam_submission insert to persist inside transaction scope';
    END IF;

    IF (SELECT COUNT(*) FROM submission.submission_seal WHERE submission_seal_id = v_submission_seal_id) <> 1 THEN
        RAISE EXCEPTION 'Expected submission.submission_seal insert to persist inside transaction scope';
    END IF;

    IF (SELECT COUNT(*) FROM capture.capture_job WHERE capture_job_id = v_capture_job_id) <> 1 THEN
        RAISE EXCEPTION 'Expected capture.capture_job insert to persist inside transaction scope';
    END IF;

    IF (SELECT COUNT(*) FROM capture.capture_dataset_row WHERE capture_dataset_row_id = v_capture_dataset_row_id) <> 1 THEN
        RAISE EXCEPTION 'Expected capture.capture_dataset_row insert to persist inside transaction scope';
    END IF;

    RAISE NOTICE 'PASS: Full Phase 4 transactional insert graph succeeded before rollback.';
END
$$;

ROLLBACK;
