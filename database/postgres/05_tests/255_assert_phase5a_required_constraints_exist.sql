-- Verifies required PK/FK/check constraints exist on Phase 5A runtime tables.

DO
$$
DECLARE
    rec record;
    pk_count integer;
    fk_count integer;
    ck_count integer;
BEGIN
    FOR rec IN
        SELECT *
        FROM (
            VALUES
                ('grading.grading_job'::regclass, 5, 6),
                ('grading.grading_run'::regclass, 1, 3),
                ('grading.question_grading_task'::regclass, 12, 9),
                ('grading.actual_result'::regclass, 1, 3),
                ('grading.expected_actual_comparison'::regclass, 3, 2),
                ('grading.question_score'::regclass, 6, 6),
                ('grading.submission_score'::regclass, 4, 7),
                ('grading.manual_review_queue'::regclass, 7, 5),
                ('grading.score_adjustment'::regclass, 3, 4),
                ('grading.grading_event'::regclass, 4, 2)
        ) AS t(tbl, fk_expected, ck_expected)
    LOOP
        SELECT COUNT(*) INTO pk_count
        FROM pg_constraint c
        WHERE c.conrelid = rec.tbl
          AND c.contype = 'p';

        SELECT COUNT(*) INTO fk_count
        FROM pg_constraint c
        WHERE c.conrelid = rec.tbl
          AND c.contype = 'f';

        SELECT COUNT(*) INTO ck_count
        FROM pg_constraint c
        WHERE c.conrelid = rec.tbl
          AND c.contype = 'c';

        IF pk_count <> 1 THEN
            RAISE EXCEPTION 'Table % must have exactly 1 primary key; found %', rec.tbl::text, pk_count;
        END IF;

        IF fk_count <> rec.fk_expected THEN
            RAISE EXCEPTION 'Table % expected % foreign keys; found %', rec.tbl::text, rec.fk_expected, fk_count;
        END IF;

        IF ck_count <> rec.ck_expected THEN
            RAISE EXCEPTION 'Table % expected % check constraints; found %', rec.tbl::text, rec.ck_expected, ck_count;
        END IF;
    END LOOP;

    RAISE NOTICE 'PASS: Phase 5A PK/FK/check constraints exist with expected counts.';
END
$$;
