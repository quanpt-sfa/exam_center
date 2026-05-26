DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM app_meta.schema_migrations
        WHERE version = '0112_add_phase3_0_station_room_integrity_and_indexes.sql'
    ) THEN
        RAISE EXCEPTION 'Missing migration version 0112_add_phase3_0_station_room_integrity_and_indexes.sql';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM app_meta.schema_migrations
        WHERE version = '0113_record_phase3_0_alignment_versions.sql'
    ) THEN
        RAISE EXCEPTION 'Missing migration version 0113_record_phase3_0_alignment_versions.sql';
    END IF;

    RAISE NOTICE 'PASS: Phase 3.0 alignment migration versions recorded.';
END
$$;

