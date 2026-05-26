import { fireEvent, render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { AdminDashboardPage } from './AdminDashboardPage';
import {
  AdminDashboardRequestError,
  getAdminDashboardAlerts,
  getAdminDashboardSummary,
} from './adminDashboardApi';

vi.mock('./adminDashboardApi', () => ({
  getAdminDashboardSummary: vi.fn(),
  getAdminDashboardAlerts: vi.fn(),
  AdminDashboardRequestError: class AdminDashboardRequestError extends Error {
    code: string;
    details: unknown;
    request_id: string | null;
    status: number;
    constructor(payload: { code: string; message: string; details?: unknown; request_id?: string | null; status?: number }) {
      super(payload.message);
      this.name = 'AdminDashboardRequestError';
      this.code = payload.code;
      this.details = payload.details ?? {};
      this.request_id = payload.request_id ?? null;
      this.status = payload.status ?? 0;
    }
  },
}));

const mockedGetAdminDashboardSummary = vi.mocked(getAdminDashboardSummary);
const mockedGetAdminDashboardAlerts = vi.mocked(getAdminDashboardAlerts);

function renderPage() {
  render(
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AdminDashboardPage />
    </BrowserRouter>
  );
}

const summaryFixture = {
  generated_at: '2026-05-23T09:00:00Z',
  sittings: { today: 7, open: 3, upcoming_24h: 4, not_ready: 2 },
  setup: {
    sittings_without_published_exam: 1,
    sittings_not_prepared: 2,
    rooms_missing_proctors: 3,
    rooms_missing_ready_stations: 1,
    students_unassigned: 5,
    failed_import_jobs: 1,
  },
  live: {
    open_rooms: 6,
    checked_in: 120,
    not_checked_in: 18,
    started: 98,
    checked_in_not_started: 22,
    not_started_in_open_sittings: 9,
    interrupted: 2,
    sealed: 84,
  },
  incidents: { open: 2, in_progress: 1, resolved_today: 4 },
  close_room: { blocked_rooms: 2, closed_rooms: 5 },
  grading: { pending: 12, running: 4, computed: 140, needs_review: 6, failed: 2 },
  system: { active_user_sessions: 88, locked_accounts: 3, workers_unhealthy: 0 },
};

const alertsFixture = {
  generated_at: '2026-05-23T09:00:00Z',
  limit: 50,
  items: [
    {
      alert_id: 'alert-1',
      type: 'SESSION_STALE',
      severity: 'warning',
      title: 'Phiên thi mất heartbeat',
      description: 'Máy thi không gửi heartbeat trong ngưỡng cho phép.',
      entity_type: 'exam_session',
      entity_id: 'session-12',
      exam_sitting_id: 12,
      exam_sitting_room_id: 44,
      action_route: '/proctor/rooms/44/operations',
      created_at: '2026-05-23T08:55:00Z',
      status: 'OPEN',
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  mockedGetAdminDashboardSummary.mockResolvedValue(summaryFixture);
  mockedGetAdminDashboardAlerts.mockResolvedValue(alertsFixture);
});

describe('AdminDashboardPage', () => {
  test('renders compact dashboard sections from backend data and keeps real action links', async () => {
    renderPage();

    expect(await screen.findByRole('heading', { name: 'Exam setup readiness' })).toBeInTheDocument();
    expect(screen.getByText('Operational alerts')).toBeInTheDocument();
    expect(screen.getByText('Phiên thi mất heartbeat')).toBeInTheDocument();
    expect(screen.getByText(/Generated at:/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Mở workflow' })).toHaveAttribute('href', '/proctor/rooms/44/operations');
    expect(screen.queryByText(/Lê Minh Tuấn/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Phòng thi 405/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Sửa lỗi/i })).not.toBeInTheDocument();
    expect(mockedGetAdminDashboardSummary).toHaveBeenCalledTimes(1);
    expect(mockedGetAdminDashboardAlerts).toHaveBeenCalledWith({ limit: 50 });
  });

  test('load failure shows error panel and retry button instead of fake zeros', async () => {
    mockedGetAdminDashboardSummary.mockRejectedValueOnce(
      new AdminDashboardRequestError({
        code: 'permission_denied',
        message: 'Forbidden',
        details: { required_roles: ['ADMIN'] },
        request_id: 'req-dashboard',
        status: 403,
      })
    );

    renderPage();

    expect(await screen.findByRole('heading', { name: 'Không tải được dashboard quản trị' })).toBeInTheDocument();
    expect(screen.getByText('Forbidden')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Tải lại dashboard' }));

    expect(await screen.findByText('Operational alerts')).toBeInTheDocument();
    expect(mockedGetAdminDashboardSummary).toHaveBeenCalledTimes(2);
  });

  test('empty alerts render a read-only compact empty state', async () => {
    mockedGetAdminDashboardAlerts.mockResolvedValueOnce({
      generated_at: '2026-05-23T09:00:00Z',
      limit: 50,
      items: [],
    });

    renderPage();

    expect(await screen.findByText('Không có cảnh báo vận hành hiện tại.')).toBeInTheDocument();
  });
});
