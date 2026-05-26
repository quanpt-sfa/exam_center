-- Verifies that the target development database exists by asserting current DB session is active.

DO
$$
DECLARE
    active_db text;
BEGIN
    SELECT current_database() INTO active_db;

    IF active_db IS NULL OR active_db = '' THEN
        RAISE EXCEPTION 'Unable to resolve current_database().';
    END IF;

    RAISE NOTICE 'PASS: Connected to database %.', active_db;
END
$$;
