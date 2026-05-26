-- Verifies primary keys exist on both Phase 4.7.3 assessment modality tables.

DO
$$
DECLARE
    pk_count integer;
BEGIN
    SELECT COUNT(*)
    INTO pk_count
    FROM pg_constraint c
    WHERE c.contype = 'p'
      AND c.conrelid IN (
          'assessment.exam_version_delivery_profile'::regclass,
          'assessment.question_grading_profile'::regclass
      );

    IF pk_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 primary keys for Phase 4.7.3 tables but found %', pk_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 4.7.3 primary keys exist.';
END
$$;
