import { httpRequest } from '../../shared/api/httpClient';
import type {
  AdminDashboardAlertsResponse,
  AdminDashboardApiError,
  AdminDashboardSummary,
  DashboardAlertType,
  DashboardSeverity,
} from './adminDashboardContracts';

export type AdminDashboardAlertFilters = {
  severity?: DashboardSeverity | null;
  type?: DashboardAlertType | null;
  limit?: number;
};

export class AdminDashboardRequestError extends Error {
  code: string;
  details: unknown;
  request_id: string | null;
  status: number;

  constructor(payload: AdminDashboardApiError) {
    super(payload.message);
    this.name = 'AdminDashboardRequestError';
    this.code = payload.code;
    this.details = payload.details;
    this.request_id = payload.request_id ?? null;
    this.status = payload.status ?? 0;
  }
}

type LegacyApiResult<T> = Awaited<ReturnType<typeof httpRequest<T>>>;

function inferStatus(code: string): number {
  switch (code) {
    case 'permission_denied':
      return 403;
    case 'unauthorized':
    case 'unauthenticated':
      return 401;
    case 'validation_error':
      return 422;
    case 'network_error':
      return 0;
    default:
      return 0;
  }
}

function mapApiError<T>(response: LegacyApiResult<T>): AdminDashboardApiError {
  if (response.ok) {
    return {
      code: 'invalid_response',
      message: 'Unexpected API success state',
      details: {},
      request_id: null,
      status: 502,
    };
  }

  return {
    code: response.error.code,
    message: response.error.message,
    details: response.error.details,
    request_id: response.error.request_id ?? null,
    status: inferStatus(response.error.code),
  };
}

async function requestData<T>(path: string): Promise<T> {
  const response = await httpRequest<T>(path, { method: 'GET' });
  if (!response.ok) {
    throw new AdminDashboardRequestError(mapApiError(response));
  }
  return response.data;
}

function buildAlertsQuery(filters?: AdminDashboardAlertFilters): string {
  const params = new URLSearchParams();
  if (filters?.severity) {
    params.set('severity', String(filters.severity));
  }
  if (filters?.type) {
    params.set('type', String(filters.type));
  }
  if (filters?.limit != null) {
    params.set('limit', String(filters.limit));
  }
  const query = params.toString();
  return query ? `?${query}` : '';
}

export function getAdminDashboardSummary(): Promise<AdminDashboardSummary> {
  return requestData<AdminDashboardSummary>('/admin/dashboard/summary');
}

export function getAdminDashboardAlerts(filters?: AdminDashboardAlertFilters): Promise<AdminDashboardAlertsResponse> {
  return requestData<AdminDashboardAlertsResponse>(`/admin/dashboard/alerts${buildAlertsQuery(filters)}`);
}
