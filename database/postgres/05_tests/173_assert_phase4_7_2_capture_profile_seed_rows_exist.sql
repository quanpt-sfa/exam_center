-- Verifies required Phase 4.7.2 capture profile seed rows exist.

DO
$$
DECLARE
    profile_count integer;
BEGIN
    SELECT COUNT(*)
    INTO profile_count
    FROM capture.capture_profile cp
    WHERE cp.profile_code IN (
        'SQLSERVER_SERVER_HOSTED_PROFILE',
        'SQLSERVER_STUDENT_DEVICE_LOCAL_PROFILE',
        'MISA_SERVER_HOSTED_PROFILE',
        'MISA_STUDENT_DEVICE_LOCAL_PROFILE',
        'AMIS_API_PROFILE'
    );

    IF profile_count <> 5 THEN
        RAISE EXCEPTION 'Expected 5 seeded capture profiles but found %', profile_count;
    END IF;

    RAISE NOTICE 'PASS: Required Phase 4.7.2 capture profile seeds exist.';
END
$$;
