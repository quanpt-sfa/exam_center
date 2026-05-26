import type { EntityFieldConfig, FieldKind, FieldSize } from '../types';

type GridSpan = 2 | 3 | 4 | 6 | 8 | 12;

export type ResolvedMasterDataFieldLayout = {
  fieldKind: FieldKind;
  fieldSize: FieldSize;
  gridSpan: GridSpan;
  inputMode?: EntityFieldConfig['inputMode'];
  multiline: boolean;
  className: string;
  dataAttributes: {
    'data-field-kind': FieldKind;
    'data-field-size': FieldSize;
    'data-grid-span': GridSpan;
  };
};

const FIELD_SIZE_TO_GRID_SPAN: Record<FieldSize, GridSpan> = {
  xs: 2,
  sm: 3,
  md: 4,
  lg: 6,
  xl: 8,
  full: 12,
};

const FIELD_KIND_TO_SIZE: Record<FieldKind, FieldSize> = {
  code: 'sm',
  id: 'sm',
  numeric: 'xs',
  year: 'xs',
  order: 'xs',
  status: 'sm',
  select: 'sm',
  shortName: 'md',
  longName: 'lg',
  email: 'xl',
  phone: 'md',
  url: 'xl',
  address: 'full',
  description: 'full',
  note: 'full',
  json: 'full',
  dateTime: 'md',
  boolean: 'sm',
};

const CODE_FIELDS = new Set([
  'department_code',
  'course_code',
  'class_code',
  'student_code',
  'instructor_code',
  'room_code',
  'station_code',
  'asset_tag',
  'offering_code',
  'serial_no',
]);

const ID_FIELDS = new Set([
  'parent_department_id',
  'term_id',
  'program_id',
  'department_id',
  'course_id',
  'current_station_id',
]);

const XS_NUMERIC_FIELDS = new Set(['capacity', 'floor_no', 'credit', 'seat_no', 'row_no', 'column_no', 'entry_year']);

const STATUS_FIELDS = new Set([
  'status',
  'student_status',
  'instructor_status',
  'room_type',
  'device_type',
  'gender_code',
  'delivery_mode',
  'course_type',
]);

const SHORT_NAME_FIELDS = new Set(['building', 'cohort']);

const LONG_NAME_FIELDS = new Set(['department_name', 'course_name', 'class_name', 'full_name', 'room_name', 'device_name']);

function inferFieldKind(field: EntityFieldConfig): FieldKind {
  const name = field.name;

  if (CODE_FIELDS.has(name)) return 'code';
  if (ID_FIELDS.has(name) || name.endsWith('_id')) return 'id';
  if (name === 'entry_year') return 'year';
  if (name === 'date_of_birth' || field.type === 'date') return 'dateTime';
  if (name === 'seat_no' || name === 'row_no' || name === 'column_no') return 'order';
  if (STATUS_FIELDS.has(name)) return field.type === 'select' ? 'status' : 'select';
  if (SHORT_NAME_FIELDS.has(name)) return 'shortName';
  if (LONG_NAME_FIELDS.has(name) || name.endsWith('_name')) return 'longName';
  if (name.includes('email')) return 'email';
  if (name.includes('phone') || name.includes('hotline')) return 'phone';
  if (name.includes('url')) return 'url';
  if (name.includes('address') || name.includes('location')) return 'address';
  if (name.includes('description')) return 'description';
  if (name.includes('note')) return 'note';
  if (name.includes('json') || name.includes('config')) return 'json';

  if (field.type === 'number' || field.valueType === 'number' || XS_NUMERIC_FIELDS.has(name)) return 'numeric';
  if (field.type === 'select') return 'select';

  return 'longName';
}

function inferInputMode(field: EntityFieldConfig, kind: FieldKind): EntityFieldConfig['inputMode'] {
  if (field.inputMode) {
    return field.inputMode;
  }

  if (field.type === 'number' || field.valueType === 'number' || kind === 'numeric' || kind === 'year' || kind === 'order' || kind === 'id') {
    return 'numeric';
  }
  if (kind === 'email') {
    return 'email';
  }
  if (kind === 'phone') {
    return 'tel';
  }
  if (kind === 'url') {
    return 'url';
  }

  return undefined;
}

export function resolveMasterDataFieldLayout(field: EntityFieldConfig, fieldName = field.name): ResolvedMasterDataFieldLayout {
  const fieldKind = field.fieldKind ?? inferFieldKind({ ...field, name: fieldName });
  const fieldSize = field.fieldSize ?? FIELD_KIND_TO_SIZE[fieldKind] ?? 'lg';
  const gridSpan = field.gridSpan ?? FIELD_SIZE_TO_GRID_SPAN[fieldSize];
  const multiline = Boolean(field.multiline || fieldKind === 'address' || fieldKind === 'description' || fieldKind === 'note' || fieldKind === 'json');

  return {
    fieldKind,
    fieldSize,
    gridSpan,
    inputMode: inferInputMode(field, fieldKind),
    multiline,
    className: `master-data-field field-span-${fieldSize}`,
    dataAttributes: {
      'data-field-kind': fieldKind,
      'data-field-size': fieldSize,
      'data-grid-span': gridSpan,
    },
  };
}
