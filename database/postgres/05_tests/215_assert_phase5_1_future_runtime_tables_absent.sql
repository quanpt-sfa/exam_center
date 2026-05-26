-- Verifies future group-grading runtime tables are still absent after Phase 5.1.

DO
$$
DECLARE
    obj text;
    unexpected text := '';
BEGIN
    FOREACH obj IN ARRAY ARRAY[
        'grading.group_grading_job',
        'grading.group_cycle_grading_run',
        'grading.group_member_score'
    ] LOOP
        IF to_regclass(obj) IS NOT NULL THEN
            unexpected := unexpected || CASE WHEN unexpected = '' THEN '' ELSE ', ' END || obj;
        END IF;
    END LOOP;

    IF unexpected <> '' THEN
        RAISE EXCEPTION 'Unexpected future group-grading runtime tables exist in Phase 5.1: %', unexpected;
    END IF;

    RAISE NOTICE 'PASS: Future group-grading runtime tables remain absent after Phase 5.1.';
END
$$;
