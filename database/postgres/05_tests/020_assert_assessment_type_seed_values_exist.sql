-- Verifies required assessment.assessment_type seed values exist.

DO
$$
DECLARE
    expected_type_code text;
    missing_codes text := '';
BEGIN
    FOREACH expected_type_code IN ARRAY ARRAY[
        'QUIZ',
        'PRACTICE',
        'MIDTERM',
        'FINAL',
        'RETAKE',
        'MAKEUP'
    ]
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM assessment.assessment_type atp
            WHERE atp.type_code = expected_type_code
        ) THEN
            missing_codes := missing_codes || CASE WHEN missing_codes = '' THEN '' ELSE ', ' END || expected_type_code;
        END IF;
    END LOOP;

    IF missing_codes <> '' THEN
        RAISE EXCEPTION 'Missing assessment_type seed values: %', missing_codes;
    END IF;

    RAISE NOTICE 'PASS: Required assessment_type seed values exist.';
END
$$;