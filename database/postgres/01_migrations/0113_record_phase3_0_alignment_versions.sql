-- Record Phase 3.0 alignment migration versions.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    (
        '0112_add_phase3_0_station_room_integrity_and_indexes.sql',
        'Phase 3.0 alignment: station-room integrity trigger and operational lookup indexes',
        NULL,
        current_user
    ),
    (
        '0113_record_phase3_0_alignment_versions.sql',
        'Record Phase 3.0 alignment migration versions',
        NULL,
        current_user
    )
ON CONFLICT (version) DO NOTHING;

