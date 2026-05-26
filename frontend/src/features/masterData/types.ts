import type { HTMLAttributes } from 'react';
import type { ApiEnvelope } from '../../shared/api/apiEnvelope';
import type { MasterDataRow, Pagination } from './api/contracts';

export type FieldType = 'text' | 'number' | 'date' | 'select';

export type SupportedLocale = 'vi' | 'en';

export type DisplayLabelConfig =
  | string
  | {
      label?: string;
      labelVi?: string;
      labelEn?: string;
      titleVi?: string;
      titleEn?: string;
      descriptionVi?: string;
      descriptionEn?: string;
      labels?: {
        vi?: string;
        en?: string;
      };
    };

export type FieldSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | 'full';

export type FieldKind =
  | 'code'
  | 'id'
  | 'numeric'
  | 'year'
  | 'order'
  | 'status'
  | 'select'
  | 'shortName'
  | 'longName'
  | 'email'
  | 'phone'
  | 'url'
  | 'address'
  | 'description'
  | 'note'
  | 'json'
  | 'dateTime'
  | 'boolean';

export type EntityGroup = 'Core' | 'Academic' | 'People' | 'Facility';

export type CapabilityStatus = 'available' | 'deferred' | 'unsupported';

export type EntityCapability = {
  status: CapabilityStatus;
  note?: string;
};

export type EntityFieldConfig = {
  name: string;
  label: DisplayLabelConfig;
  type?: FieldType;
  fieldKind?: FieldKind;
  fieldSize?: FieldSize;
  gridSpan?: 2 | 3 | 4 | 6 | 8 | 12;
  maxDisplayChars?: number;
  inputMode?: HTMLAttributes<HTMLInputElement>['inputMode'];
  multiline?: boolean;
  minRows?: number;
  maxRows?: number;
  valueType?: 'string' | 'number';
  required?: boolean;
  integer?: boolean;
  min?: number;
  max?: number;
  placeholder?: string;
  defaultValue?: string;
  helperText?: string;
  validationMessage?: string;
  options?: Array<{ label: string; value: string }>;
  lookup?: 'departments' | 'programs' | 'courses';
  allowManualLookupFallback?: boolean;
};

export type LookupFieldState = {
  disabled: boolean;
  loading: boolean;
  error: string | null;
  allowManualFallback: boolean;
  showManualFallback: boolean;
};

export type EntityColumnConfig = {
  key: string;
  label: DisplayLabelConfig;
};

export type EntityFilterConfig = {
  key: 'room';
  label: DisplayLabelConfig;
  type: 'select';
};

export type MasterDataEntityKey =
  | 'departments'
  | 'programs'
  | 'courses'
  | 'courseOfferings'
  | 'classSections'
  | 'enrollments'
  | 'students'
  | 'instructors'
  | 'assessment-types'
  | 'exam-slots'
  | 'rooms'
  | 'stations'
  | 'devices'
  | 'device-readiness';

export type EntityFormState = Record<string, string>;

export type EntityListParams = {
  page: number;
  page_size: number;
  query?: string;
  status?: string;
};

export type EntityListResponse = {
  items: MasterDataRow[];
  pagination?: Pagination;
};

export type EntityApiContext = {
  selectedRoomId: number | null;
  params: EntityListParams;
};

export type EntityApiConfig = {
  list?: (context: EntityApiContext) => Promise<ApiEnvelope<EntityListResponse>> | null;
  create?: (form: EntityFormState, context: EntityApiContext) => Promise<ApiEnvelope<MasterDataRow>> | null;
  update?: (entityId: number, form: EntityFormState, context: EntityApiContext) => Promise<ApiEnvelope<MasterDataRow>> | null;
  deactivate?: (entityId: number, context: EntityApiContext) => Promise<ApiEnvelope<MasterDataRow>> | null;
};

export type EntityListFeatures = {
  supportsQuery: boolean;
  supportsStatusFilter: boolean;
  supportsPagination: boolean;
  defaultPageSize: number;
  pageSizeOptions?: number[];
  statusOptions?: Array<{ label: string; value: string }>;
};

export type EntityCapabilities = {
  list: EntityCapability;
  create: EntityCapability;
  update: EntityCapability;
  deactivate: EntityCapability;
  readOnly: boolean;
};

export type EntityConfig = {
  key: MasterDataEntityKey;
  label: DisplayLabelConfig;
  group: EntityGroup;
  primaryKey: string;
  description: DisplayLabelConfig;
  fields: EntityFieldConfig[];
  columns: EntityColumnConfig[];
  filters: EntityFilterConfig[];
  createNote?: string;
  capabilities: EntityCapabilities;
  listFeatures: EntityListFeatures;
  api: EntityApiConfig;
};

export type EntityState = {
  rows: MasterDataRow[];
  pagination?: Pagination;
  loading: boolean;
  error: string | null;
  submitting: boolean;
  message: string | null;
};

export type EntityFormErrors = Record<string, string>;