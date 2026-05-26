import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { httpRequest } from '../../shared/api/httpClient';
import { DashboardPage } from './DashboardPage';

vi.mock('./adminDashboardApi', () => ({
  getAdminDashboardSummary: vi.fn(),
  getAdminDashboardAlerts: vi.fn(),
  AdminDashboardRequestError: class AdminDashboardRequestError extends Error {},
}));

import { getAdminDashboardAlerts, getAdminDashboardSummary } from './adminDashboardApi';

vi.mock('../../shared/api/httpClient', () => ({
  httpRequest: vi.fn(),
}));

const mockedHttpRequest = vi.mocked(httpRequest);
const mockedGetAdminDashboardSummary = vi.mocked(getAdminDashboardSummary);
const mockedGetAdminDashboardAlerts = vi.mocked(getAdminDashboardAlerts);

function renderDashboard() {
  render(
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <DashboardPage />
    </BrowserRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockedGetAdminDashboardSummary.mockResolvedValue({
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
  });
  mockedGetAdminDashboardAlerts.mockResolvedValue({
    generated_at: '2026-05-23T09:00:00Z',
    items: [],
    limit: 50,
  });
});

describe('DashboardPage', () => {
  test('loads current student and renders registered exam classes', async () => {
    mockedHttpRequest
      .mockResolvedValueOnce({
        ok: true,
        success: true,
        data: {
          user_id: 2,
          username: 'student',
          display_name: 'Nguyen Van A',
          roles: ['STUDENT'],
          permissions: [],
        },
        message: null,
        error: null,
      })
      .mockResolvedValueOnce({
        ok: true,
        success: true,
        data: {
          items: [
            {
              exam_session_id: 10,
              sitting_name: 'Ca thi SQL 01',
              course_code: 'DB101',
              course_name: 'Databases',
              scheduled_start_at: '2026-05-14T08:00:00+07:00',
              scheduled_end_at: '2026-05-14T09:30:00+07:00',
              room_code: 'LAB 1',
              seat_no: 'A01',
              session_status: 'READY_TO_START',
              assignment_status: 'ASSIGNED',
            },
          ],
        },
        message: null,
        error: null,
      });

    renderDashboard();

    expect(await screen.findByText('Nguyen Van A')).toBeInTheDocument();
    expect(screen.getByText(/DB101 - Databases/)).toBeInTheDocument();
    expect(screen.getAllByText('Ca thi SQL 01').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Đang mở').length).toBeGreaterThan(0);
    expect(screen.getByText('Sẵn sàng vào thi')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Vào bài thi/i })).toHaveAttribute('href', '/exams/10');
    expect(mockedHttpRequest).toHaveBeenNthCalledWith(1, '/auth/me');
    expect(mockedHttpRequest).toHaveBeenNthCalledWith(2, '/exam-sessions');
  });

  test('renders admin dashboard for admin users without loading student exams', async () => {
    window.history.pushState({}, '', '/dashboard');
    mockedHttpRequest.mockResolvedValueOnce({
      ok: true,
      success: true,
      data: {
        user_id: 1,
        username: 'admin',
        display_name: 'Admin User',
        roles: ['ADMIN'],
        permissions: ['subjects.manage'],
      },
      message: null,
      error: null,
    });

    renderDashboard();

    expect(await screen.findByText(/Admin Dashboard/i)).toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: 'Exam setup readiness' })).toBeInTheDocument();
    expect(mockedHttpRequest).toHaveBeenCalledTimes(1);
    expect(mockedGetAdminDashboardSummary).toHaveBeenCalledTimes(1);
    expect(mockedGetAdminDashboardAlerts).toHaveBeenCalledWith({ limit: 50 });
  });

  test('hides master data quick action for instructor without permission', async () => {
    window.history.pushState({}, '', '/dashboard');
    mockedHttpRequest.mockResolvedValueOnce({
      ok: true,
      success: true,
      data: {
        user_id: 11,
        username: 'gv01',
        display_name: 'Giảng viên A',
        roles: ['INSTRUCTOR'],
        permissions: ['grading.grade'],
      },
      message: null,
      error: null,
    });

    renderDashboard();

    expect(await screen.findByText(/Dashboard giảng viên/i)).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Mở master data/i })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Mở bảng điểm/i })).toHaveAttribute('href', '/grading/gradebook');
  });

  test('shows master data quick action when user has master data permission', async () => {
    window.history.pushState({}, '', '/dashboard');
    mockedHttpRequest.mockResolvedValueOnce({
      ok: true,
      success: true,
      data: {
        user_id: 12,
        username: 'gv02',
        display_name: 'Giảng viên B',
        roles: ['INSTRUCTOR'],
        permissions: ['master_data:read'],
      },
      message: null,
      error: null,
    });

    renderDashboard();

    expect(await screen.findByRole('link', { name: /Mở master data/i })).toHaveAttribute('href', '/master-data');
  });
});
