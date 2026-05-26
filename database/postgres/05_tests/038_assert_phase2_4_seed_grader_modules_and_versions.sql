-- Verifies seeded grader modules and v1 module versions exist.

DO
$$
DECLARE
    expected_module_code text;
    missing_modules text := '';
    missing_versions text := '';
BEGIN
    FOREACH expected_module_code IN ARRAY ARRAY[
        'SQL_QUERY_GRADER',
        'SQL_DDL_GRADER',
        'MISA_GRADER',
        'AMIS_GRADER',
        'MANUAL_RUBRIC_GRADER'
    ]
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM assessment.grader_module gm
            WHERE gm.module_code = expected_module_code
        ) THEN
            missing_modules := missing_modules || CASE WHEN missing_modules = '' THEN '' ELSE ', ' END || expected_module_code;
        END IF;

        IF NOT EXISTS (
            SELECT 1
            FROM assessment.grader_module_version gmv
            JOIN assessment.grader_module gm
                ON gm.module_id = gmv.module_id
            WHERE gm.module_code = expected_module_code
              AND gmv.version_no = 'v1'
        ) THEN
            missing_versions := missing_versions || CASE WHEN missing_versions = '' THEN '' ELSE ', ' END || expected_module_code || ':v1';
        END IF;
    END LOOP;

    IF missing_modules <> '' THEN
        RAISE EXCEPTION 'Missing seeded grader modules: %', missing_modules;
    END IF;

    IF missing_versions <> '' THEN
        RAISE EXCEPTION 'Missing seeded grader module versions: %', missing_versions;
    END IF;

    RAISE NOTICE 'PASS: Seeded grader modules and v1 module versions exist.';
END
$$;
