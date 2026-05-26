DO
$$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_worker') THEN
        RAISE EXCEPTION 'Role exam_sys_worker must exist';
    END IF;

    IF NOT has_schema_privilege('exam_sys_worker', 'importing', 'USAGE') THEN
        RAISE EXCEPTION 'exam_sys_worker must have USAGE on importing schema';
    END IF;

    IF NOT has_table_privilege('exam_sys_worker', 'importing.import_row_error', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_worker must have DELETE on importing.import_row_error';
    END IF;

    IF has_table_privilege('exam_sys_app', 'importing.import_row_error', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on importing.import_row_error';
    END IF;

    IF has_database_privilege('exam_sys_worker', current_database(), 'CREATE') THEN
        RAISE EXCEPTION 'exam_sys_worker must not have CREATE privilege on database';
    END IF;

    RAISE NOTICE 'PASS: split API/worker runtime role privileges validated.';
END
$$;

