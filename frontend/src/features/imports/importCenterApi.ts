import { httpRequest } from '../../shared/api/httpClient';

export type ImportType =
  | 'STUDENTS'
  | 'INSTRUCTORS'
  | 'SUBJECTS'
  | 'COURSES'
  | 'CLASS_SECTIONS'
  | 'ENROLLMENTS'
  | 'ROOMS'
  | 'STATIONS'
  | 'DEVICES';

export type ImportRow = Record<string, unknown>;

export type ImportPagination = {
  page: number;
  page_size: number;
  total?: number;
  total_pages?: number;
  has_next?: boolean;
  has_previous?: boolean;
};

export type ImportTemplateColumn = {
  name: string;
  required: boolean;
  default: string | null;
  description: string;
};

export type ImportTemplate = {
  import_type: ImportType;
  label: string;
  columns: ImportTemplateColumn[];
  sample_row: Record<string, string>;
};

export type ImportTemplatesResponse = {
  items: ImportTemplate[];
};

export type ImportJob = {
  import_job_id: number;
  import_type: ImportType;
  status: string;
  validation_status: string;
  commit_status: string;
  counts: Record<string, number>;
};

export type ImportJobDetail = ImportJob & Partial<ImportJobStatus>;

export type ImportJobStatus = {
  import_job_id: number;
  import_type: ImportType;
  status: string;
  worker_status?: string | null;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  committed_rows: number;
  failed_rows: number;
  skipped_rows: number;
  attempt_count?: number;
  max_attempts?: number;
  claimed_by?: string | null;
  claimed_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  last_error_code?: string | null;
  last_error_message?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type CreateImportJobPayload = {
  import_type: ImportType;
  source_filename: string;
  rows: ImportRow[];
  metadata_json: Record<string, unknown>;
};

export type ImportRowDetail = {
  import_row_id: number;
  row_number: number;
  validation_status?: string | null;
  commit_status?: string | null;
  raw_row: Record<string, unknown>;
  normalized_row?: Record<string, unknown> | null;
  errors?: ImportErrorDetail[];
  error_count?: number;
  has_errors?: boolean;
  [key: string]: unknown;
};

export type ImportRowsResponse = {
  items: ImportRowDetail[];
  pagination?: ImportPagination;
};

export type ImportErrorDetail = {
  row_number?: number;
  field_name?: string | null;
  error_code?: string | null;
  error_message: string;
  severity?: string | null;
  created_at?: string | null;
  details?: Record<string, unknown> | null;
  [key: string]: unknown;
};

export type ImportErrorsResponse = {
  items: ImportErrorDetail[];
  pagination?: ImportPagination;
};

export type ImportValidationResult = ImportJob;

export type ImportCommitPayload = {
  idempotency_key?: string;
};

export type ImportCommitResult = {
  import_job_id: number;
  status: string;
  committed_rows: number;
  failed_rows: number;
  total_rows: number;
};

export type ImportListQuery = {
  page?: number;
  page_size?: number;
};

function buildImportQueryString(query?: ImportListQuery): string {
  const page = query?.page ?? 1;
  const pageSize = query?.page_size ?? 20;
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  return params.toString();
}

export function loadImportTemplates() {
  return httpRequest<ImportTemplatesResponse>('/master-data/import-templates');
}

export function createImportJob(payload: CreateImportJobPayload) {
  return httpRequest<ImportJob>('/master-data/imports', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getImportJobStatus(importJobId: number) {
  return httpRequest<ImportJobStatus>(`/master-data/imports/${importJobId}/status`);
}

export function getImportJob(importJobId: number) {
  return httpRequest<ImportJobDetail>(`/master-data/imports/${importJobId}`);
}

export function listImportRows(importJobId: number, query?: ImportListQuery) {
  return httpRequest<ImportRowsResponse>(`/master-data/imports/${importJobId}/rows?${buildImportQueryString(query)}`);
}

export function listImportErrors(importJobId: number, query?: ImportListQuery) {
  return httpRequest<ImportErrorsResponse>(`/master-data/imports/${importJobId}/errors?${buildImportQueryString(query)}`);
}

export function validateImportJob(importJobId: number) {
  return httpRequest<ImportValidationResult>(`/master-data/imports/${importJobId}/validate`, {
    method: 'POST',
  });
}

export function commitImportJob(importJobId: number, payload: ImportCommitPayload = {}) {
  return httpRequest<ImportCommitResult>(`/master-data/imports/${importJobId}/commit`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}