-- Assert partial unique indexes exist with expected predicates,
-- and validate with insert conflict checks.

DO
$$
DECLARE
    idx_name text;
    idx_pred text;
    missing_indexes text := '';
    bad_indexes text := '';

    suffix text := to_char(clock_timestamp(), 'YYYYMMDDHH24MISSMS');
    v_person_id bigint;
    v_department_id bigint;
    v_program_id bigint;
    v_student_id bigint;
BEGIN
    -- Catalog checks: index exists, unique, and predicate has expected semantics.
    FOR idx_name, idx_pred IN
        SELECT *
        FROM (
            VALUES
                ('idx_contact_point_one_current_primary_per_type', '(is_primary = true) AND (valid_to IS NULL)'),
                ('idx_address_one_current_primary_per_type', '(is_primary = true) AND (valid_to IS NULL)'),
                ('idx_student_demographic_profile_one_current_per_student', '(valid_to IS NULL)'),
                ('idx_student_socioeconomic_profile_one_current_per_student', '(valid_to IS NULL)'),
                ('idx_student_learning_context_one_current_per_student', '(valid_to IS NULL)'),
                ('idx_student_accessibility_profile_one_current_per_student', '(valid_to IS NULL)')
        ) AS t(idx_name, idx_pred)
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_class c
            JOIN pg_index i ON i.indexrelid = c.oid
            WHERE c.relname = idx_name
              AND i.indisunique = true
              AND pg_get_expr(i.indpred, i.indrelid) ILIKE '%' || idx_pred || '%'
        ) THEN
            IF NOT EXISTS (SELECT 1 FROM pg_class c WHERE c.relname = idx_name) THEN
                missing_indexes := missing_indexes || CASE WHEN missing_indexes = '' THEN '' ELSE ', ' END || idx_name;
            ELSE
                bad_indexes := bad_indexes || CASE WHEN bad_indexes = '' THEN '' ELSE ', ' END || idx_name;
            END IF;
        END IF;
    END LOOP;

    IF missing_indexes <> '' THEN
        RAISE EXCEPTION 'Missing partial unique indexes: %', missing_indexes;
    END IF;

    IF bad_indexes <> '' THEN
        RAISE EXCEPTION 'Partial unique indexes have unexpected uniqueness/predicate: %', bad_indexes;
    END IF;

    -- Conflict check for contact_point partial unique.
    INSERT INTO identity.person (full_name, person_status)
    VALUES ('Phase11 Person ' || suffix, 'ACTIVE')
    RETURNING person_id INTO v_person_id;

    INSERT INTO identity.contact_point (person_id, contact_type, contact_value, is_primary, is_verified, valid_from)
    VALUES (v_person_id, 'EMAIL', 'phase11.primary.1.' || suffix || '@local.test', true, true, now());

    BEGIN
        INSERT INTO identity.contact_point (person_id, contact_type, contact_value, is_primary, is_verified, valid_from)
        VALUES (v_person_id, 'EMAIL', 'phase11.primary.2.' || suffix || '@local.test', true, true, now());
        RAISE EXCEPTION 'Expected unique violation for contact_point partial unique index did not occur.';
    EXCEPTION
        WHEN unique_violation THEN
            NULL;
    END;

    -- Conflict check for address partial unique.
    INSERT INTO identity.address (person_id, address_type, address_line, is_primary, valid_from)
    VALUES (v_person_id, 'CURRENT', 'Phase11 Address 1 ' || suffix, true, now());

    BEGIN
        INSERT INTO identity.address (person_id, address_type, address_line, is_primary, valid_from)
        VALUES (v_person_id, 'CURRENT', 'Phase11 Address 2 ' || suffix, true, now());
        RAISE EXCEPTION 'Expected unique violation for address partial unique index did not occur.';
    EXCEPTION
        WHEN unique_violation THEN
            NULL;
    END;

    -- Conflict check for one-current-per-student demographic.
    INSERT INTO academic.department (department_code, department_name, status)
    VALUES ('PH11_DEPT_' || suffix, 'Phase11 Department ' || suffix, 'ACTIVE')
    RETURNING department_id INTO v_department_id;

    INSERT INTO academic.program (department_id, program_code, program_name, program_level, status)
    VALUES (v_department_id, 'PH11_PRG_' || suffix, 'Phase11 Program ' || suffix, 'UNDERGRADUATE', 'ACTIVE')
    RETURNING program_id INTO v_program_id;

    INSERT INTO identity.student_profile (person_id, student_code, program_id, cohort, entry_year, student_status)
    VALUES (v_person_id, 'PH11_STU_' || suffix, v_program_id, 'K' || to_char(CURRENT_DATE, 'YYYY'), EXTRACT(YEAR FROM CURRENT_DATE)::int, 'ACTIVE')
    RETURNING student_id INTO v_student_id;

    INSERT INTO academic.student_demographic_profile (student_id, gender_code, valid_from, updated_at)
    VALUES (v_student_id, 'M', CURRENT_DATE, now());

    BEGIN
        INSERT INTO academic.student_demographic_profile (student_id, gender_code, valid_from, updated_at)
        VALUES (v_student_id, 'F', CURRENT_DATE, now());
        RAISE EXCEPTION 'Expected unique violation for student_demographic current row did not occur.';
    EXCEPTION
        WHEN unique_violation THEN
            NULL;
    END;

    -- Cleanup
    DELETE FROM academic.student_demographic_profile WHERE student_id = v_student_id;
    DELETE FROM identity.address WHERE person_id = v_person_id;
    DELETE FROM identity.contact_point WHERE person_id = v_person_id;
    DELETE FROM identity.student_profile WHERE student_id = v_student_id;
    DELETE FROM identity.person WHERE person_id = v_person_id;
    DELETE FROM academic.program WHERE program_id = v_program_id;
    DELETE FROM academic.department WHERE department_id = v_department_id;

    RAISE NOTICE 'PASS: Partial unique indexes validated by catalog and conflict checks.';
END
$$;
