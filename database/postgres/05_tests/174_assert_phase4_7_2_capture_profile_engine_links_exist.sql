-- Verifies seeded capture profile to grading engine links exist where applicable.

DO
$$
DECLARE
    link_count integer;
BEGIN
    SELECT COUNT(*)
    INTO link_count
    FROM capture.capture_profile_engine_link l
    JOIN capture.capture_profile p
      ON p.capture_profile_id = l.capture_profile_id
    JOIN grading.grading_engine ge
      ON ge.grading_engine_id = l.grading_engine_id
    WHERE (
            p.profile_code IN ('SQLSERVER_SERVER_HOSTED_PROFILE', 'SQLSERVER_STUDENT_DEVICE_LOCAL_PROFILE')
            AND ge.engine_code = 'SQL_RESULT_COMPARATOR'
          )
       OR (
            p.profile_code IN ('MISA_SERVER_HOSTED_PROFILE', 'MISA_STUDENT_DEVICE_LOCAL_PROFILE')
            AND ge.engine_code = 'MISA_DATABASE_COMPARATOR'
          )
       OR (
            p.profile_code = 'AMIS_API_PROFILE'
            AND ge.engine_code = 'AMIS_API_DATA_COMPARATOR'
          );

    IF link_count <> 5 THEN
        RAISE EXCEPTION 'Expected 5 seeded capture profile engine links but found %', link_count;
    END IF;

    RAISE NOTICE 'PASS: Required Phase 4.7.2 profile-to-engine links exist.';
END
$$;
