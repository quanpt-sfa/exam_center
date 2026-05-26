-- Verifies identity.person_photo exists.

DO
$$
BEGIN
    IF to_regclass('identity.person_photo') IS NULL THEN
        RAISE EXCEPTION 'Missing table: identity.person_photo';
    END IF;

    RAISE NOTICE 'PASS: identity.person_photo exists.';
END
$$;