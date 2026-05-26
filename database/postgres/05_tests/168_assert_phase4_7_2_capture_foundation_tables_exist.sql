-- Verifies all required Phase 4.7.2 capture foundation tables exist.

DO
$$
BEGIN
    IF to_regclass('capture.capture_profile') IS NULL THEN
        RAISE EXCEPTION 'Table capture.capture_profile does not exist';
    END IF;

    IF to_regclass('capture.capture_extractor_query') IS NULL THEN
        RAISE EXCEPTION 'Table capture.capture_extractor_query does not exist';
    END IF;

    IF to_regclass('capture.capture_profile_engine_link') IS NULL THEN
        RAISE EXCEPTION 'Table capture.capture_profile_engine_link does not exist';
    END IF;

    RAISE NOTICE 'PASS: Phase 4.7.2 capture foundation tables exist.';
END
$$;
