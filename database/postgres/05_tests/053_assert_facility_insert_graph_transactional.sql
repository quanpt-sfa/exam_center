-- Verifies facility insert graph inside a transaction and confirms rollback removes rows.

BEGIN;

DO
$$
DECLARE
    suffix text := 'SMOKE_P301_' || txid_current()::text;
    v_room_id bigint;
    v_station_id bigint;
    v_device_id bigint;
    v_device_registration_id bigint;
    v_device_checkin_id bigint;
BEGIN
    INSERT INTO facility.room (
        room_code,
        room_name,
        building,
        floor_no,
        capacity,
        room_type,
        status
    )
    VALUES (
        suffix || '_ROOM',
        suffix || ' Room',
        'Building A',
        '1',
        40,
        'LAB',
        'ACTIVE'
    )
    RETURNING room_id INTO v_room_id;

    INSERT INTO facility.lab_station (
        room_id,
        station_code,
        seat_no,
        row_no,
        column_no,
        status
    )
    VALUES (
        v_room_id,
        suffix || '_ST01',
        'S01',
        'R1',
        'C1',
        'ACTIVE'
    )
    RETURNING station_id INTO v_station_id;

    INSERT INTO facility.device (
        asset_tag,
        device_name,
        device_type,
        serial_no,
        current_station_id,
        status
    )
    VALUES (
        suffix || '_ASSET',
        suffix || ' Device',
        'LAB_PC',
        suffix || '_SERIAL',
        v_station_id,
        'ACTIVE'
    )
    RETURNING device_id INTO v_device_id;

    INSERT INTO facility.device_registration (
        device_id,
        registration_type,
        registration_value,
        valid_from,
        valid_to
    )
    VALUES (
        v_device_id,
        'HOSTNAME',
        lower(suffix) || '-host.local',
        now(),
        NULL
    )
    RETURNING device_registration_id INTO v_device_registration_id;

    INSERT INTO facility.device_checkin (
        device_id,
        station_id,
        checkin_at,
        ip_address,
        hostname,
        client_fingerprint,
        health_status,
        metadata_json
    )
    VALUES (
        v_device_id,
        v_station_id,
        now(),
        '127.0.0.1'::inet,
        lower(suffix) || '-host',
        lower(suffix) || '-fingerprint',
        'READY',
        '{"source":"smoke"}'::jsonb
    )
    RETURNING device_checkin_id INTO v_device_checkin_id;

    RAISE NOTICE 'PASS: Facility transactional insert graph succeeded before rollback.';
END
$$;

ROLLBACK;

DO
$$
BEGIN
    IF EXISTS (SELECT 1 FROM facility.room WHERE room_code LIKE 'SMOKE_P301_%') THEN
        RAISE EXCEPTION 'Rollback check failed: found rows in facility.room for SMOKE_P301_ prefix';
    END IF;

    IF EXISTS (SELECT 1 FROM facility.device WHERE asset_tag LIKE 'SMOKE_P301_%') THEN
        RAISE EXCEPTION 'Rollback check failed: found rows in facility.device for SMOKE_P301_ prefix';
    END IF;

    IF EXISTS (SELECT 1 FROM facility.device_registration WHERE registration_value LIKE 'smoke_p301_%') THEN
        RAISE EXCEPTION 'Rollback check failed: found rows in facility.device_registration for smoke_p301_ prefix';
    END IF;

    RAISE NOTICE 'PASS: Transaction rollback removed all SMOKE_P301_* rows.';
END
$$;
