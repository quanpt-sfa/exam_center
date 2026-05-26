import { beforeEach, describe, expect, test, vi } from 'vitest';
import { httpRequest } from '../../shared/api/httpClient';
import {
  AdminDashboardRequestError,
  getAdminDashboardAlerts,
  getAdminDashboardSummary,
} from './adminDashboardApi';

vi.mock('../../shared/api/httpClient', () => ({
  httpRequest: vi.fn(),
}));

const mockedHttpRequest = vi.mocked(httpRequest);

const ok = <T,>(data: T) => ({
  ok: true as const,
  success: true as const,
  data,
  message: null,
  error: null,
});

const err = (code: string, message: string, details: Record<string, unknown> = {}) => ({
  ok: false as const,
  success: false as const,
  data: null,
  message: null,
  error: {
    code,
    message,
    details,
    request_id: 'req-admin-dashboard',
  },
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe('admin dashboard api client', () => {
  test('summary endpoint uses the admin dashboard summary path', async () => {
    mockedHttpRequest.mockResolvedValueOnce(
      ok({
        generated_at: '2026-05-23T09:00:00Z',
        sittings: { today: 0, open: 0, upcoming_24h: 0, not_ready: 0 },
        setup: {
          sittings_without_published_exam: 0,
          sittings_not_prepared: 0,
          rooms_missing_proctors: 0,
          rooms_missing_ready_stations: 0,
          students_unassigned: 0,
          failed_import_jobs: 0,
        },
        live: {
          open_rooms: 0,
          checked_in: 0,
          not_checked_in: 0,
          started: 0,
          checked_in_not_started: 0,
          not_started_in_open_sittings: 0,
          interrupted: 0,
          sealed: 0,
        },
        incidents: { open: 0, in_progress: 0, resolved_today: 0 },
        close_room: { blocked_rooms: 0, closed_rooms: 0 },
        grading: { pending: 0, running: 0, computed: 0, needs_review: 0, failed: 0 },
        system: { active_user_sessions: 0, locked_accounts: 0, workers_unhealthy: 0 },
      })
    );

    await getAdminDashboardSummary();

    expect(mockedHttpRequest).toHaveBeenCalledWith('/admin/dashboard/summary', { method: 'GET' });
  });

  test('alerts endpoint uses expected path and query encoding', async () => {
    mockedHttpRequest.mockResolvedValueOnce(
      ok({
        generated_at: '2026-05-23T09:00:00Z',
        items: [],
        limit: 25,
      })
    );

    await getAdminDashboardAlerts({ severity: 'warning', type: 'SESSION_STALE', limit: 25 });

    expect(mockedHttpRequest).toHaveBeenCalledWith(
      '/admin/dashboard/alerts?severity=warning&type=SESSION_STALE&limit=25',
      { method: 'GET' }
    );
  });

  test('backend error is preserved for summary endpoint', async () => {
    mockedHttpRequest.mockResolvedValueOnce(err('permission_denied', 'Forbidden', { required_roles: ['ADMIN'] }));

    await expect(getAdminDashboardSummary()).rejects.toMatchObject({
      name: 'AdminDashboardRequestError',
      code: 'permission_denied',
      message: 'Forbidden',
      details: { required_roles: ['ADMIN'] },
    });
  });

  test('does not fake success on alerts error', async () => {
    mockedHttpRequest.mockResolvedValueOnce(err('network_error', 'Network request failed'));

    await expect(getAdminDashboardAlerts()).rejects.toBeInstanceOf(AdminDashboardRequestError);
  });
});
