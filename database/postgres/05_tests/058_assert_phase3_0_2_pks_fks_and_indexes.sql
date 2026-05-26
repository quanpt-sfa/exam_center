-- Verifies Phase 3.0.2 PK, FK, and lookup index coverage.

DO
$$
DECLARE
    table_name text;
    fk_name text;
    idx_name text;
    pk_count integer;
    missing_pk_tables text := '';
    missing_fks text := '';
    missing_indexes text := '';
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'identity.person_photo',
        'delivery.exam_sitting',
        'delivery.exam_sitting_room',
        'delivery.proctor_assignment'
    ]
    LOOP
        SELECT COUNT(*)
        INTO pk_count
        FROM pg_constraint c
        WHERE c.contype = 'p'
          AND c.conrelid = to_regclass(table_name);

        IF pk_count <> 1 THEN
            missing_pk_tables := missing_pk_tables || CASE WHEN missing_pk_tables = '' THEN '' ELSE ', ' END || table_name;
        END IF;
    END LOOP;

    FOREACH fk_name IN ARRAY ARRAY[
        'fk_identity_person_photo_person',
        'fk_identity_person_photo_created_by',
        'fk_delivery_exam_sitting_exam_version',
        'fk_delivery_exam_sitting_created_by',
        'fk_delivery_exam_sitting_room_exam_sitting',
        'fk_delivery_exam_sitting_room_room',
        'fk_delivery_proctor_assignment_exam_sitting_room',
        'fk_delivery_proctor_assignment_proctor_user',
        'fk_delivery_proctor_assignment_assigned_by'
    ]
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = fk_name
              AND contype = 'f'
        ) THEN
            missing_fks := missing_fks || CASE WHEN missing_fks = '' THEN '' ELSE ', ' END || fk_name;
        END IF;
    END LOOP;

    FOREACH idx_name IN ARRAY ARRAY[
        'idx_identity_person_photo_person_id',
        'idx_identity_person_photo_created_by',
        'idx_delivery_exam_sitting_exam_version_id',
        'idx_delivery_exam_sitting_created_by',
        'idx_delivery_exam_sitting_room_exam_sitting_id',
        'idx_delivery_exam_sitting_room_room_id',
        'idx_delivery_proctor_assignment_exam_sitting_room_id',
        'idx_delivery_proctor_assignment_proctor_user_id',
        'idx_delivery_proctor_assignment_assigned_by'
    ]
    LOOP
        IF to_regclass('identity.' || idx_name) IS NULL
           AND to_regclass('delivery.' || idx_name) IS NULL THEN
            missing_indexes := missing_indexes || CASE WHEN missing_indexes = '' THEN '' ELSE ', ' END || idx_name;
        END IF;
    END LOOP;

    IF missing_pk_tables <> '' THEN
        RAISE EXCEPTION 'Missing/invalid PK on tables: %', missing_pk_tables;
    END IF;

    IF missing_fks <> '' THEN
        RAISE EXCEPTION 'Missing FK constraints: %', missing_fks;
    END IF;

    IF missing_indexes <> '' THEN
        RAISE EXCEPTION 'Missing lookup indexes: %', missing_indexes;
    END IF;

    RAISE NOTICE 'PASS: Phase 3.0.2 PK/FK/index coverage exists.';
END
$$;