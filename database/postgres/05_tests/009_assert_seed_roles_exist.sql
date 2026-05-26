-- Verifies required seed roles are present.

DO
$$
DECLARE
    missing_roles text;
BEGIN
    SELECT string_agg(expected_role, ', ' ORDER BY expected_role)
    INTO missing_roles
    FROM (
        SELECT unnest(
            ARRAY['STUDENT', 'INSTRUCTOR', 'ADMIN', 'ACADEMIC_OFFICER', 'PROCTOR', 'GRADER']
        ) AS expected_role
    ) src
    WHERE NOT EXISTS (
        SELECT 1
        FROM identity.role r
        WHERE r.role_code = src.expected_role
    );

    IF missing_roles IS NOT NULL THEN
        RAISE EXCEPTION 'Missing seeded roles: %', missing_roles;
    END IF;

    IF (SELECT COUNT(*) FROM identity.role WHERE role_code IN ('STUDENT', 'INSTRUCTOR', 'ADMIN', 'ACADEMIC_OFFICER', 'PROCTOR', 'GRADER')) < 6 THEN
        RAISE EXCEPTION 'Seed role count check failed.';
    END IF;

    RAISE NOTICE 'PASS: Seed roles exist.';
END
$$;
