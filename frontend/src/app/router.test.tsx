import { render, screen, waitFor } from '@testing-library/react';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { AppRouter } from './router';

vi.mock('../features/auth/authApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../features/auth/authApi')>();
  return {
    ...actual,
    changePassword: vi.fn(),
    getCurrentUser: vi.fn(),
    logout: vi.fn(),
  };
});

vi.mock('../shared/auth/tokenStorage', () => ({
  clearAuthTokens: vi.fn(),
  getAccessToken: vi.fn(),
  getRefreshToken: vi.fn(),
}));

vi.mock('../features/proctor/api/proctorApi', () => ({
  listMySittingRooms: vi.fn(),
  getProctorRoomRoster: vi.fn(),
  listProctorRoomAttendance: vi.fn(),
  checkInAssignment: vi.fn(),
  markAssignmentAbsent: vi.fn(),
  verifyAssignmentIdentity: vi.fn(),
  scanCheckInAttendance: vi.fn(),
  getProctorRoomReadiness: vi.fn(),
  getProctorRoomClosePreflight: vi.fn(),
  closeProctorRoom: vi.fn(),
  listProctorRoomIncidents: vi.fn(),
  createProctorIncident: vi.fn(),
  updateProctorIncident: vi.fn(),
  revokeStudentStaleSession: vi.fn(),
}));

vi.mock('../features/gradebook/gradebookApi', () => ({
  listGradebookSubmissions: vi.fn(),
  getGradebookSubmissionDetail: vi.fn(),
  getSubmissionScore: vi.fn(),
  getSubmissionQuestionScores: vi.fn(),
  listManualReviews: vi.fn(),
  GradebookRequestError: class GradebookRequestError extends Error {
    code: string;
    details: Record<string, unknown>;
    request_id: string | null;
    status: number;
    constructor(payload: { code: string; message: string; details?: Record<string, unknown>; request_id?: string | null; status?: number }) {
      super(payload.message);
      this.name = 'GradebookRequestError';
      this.code = payload.code;
      this.details = payload.details ?? {};
      this.request_id = payload.request_id ?? null;
      this.status = payload.status ?? 0;
    }
  },
}));

vi.mock('../features/dashboard/adminDashboardApi', () => ({
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

import { getCurrentUser } from '../features/auth/authApi';
import {
  getProctorRoomClosePreflight,
  getProctorRoomReadiness,
  listProctorRoomAttendance,
  listProctorRoomIncidents,
  getProctorRoomRoster,
  listMySittingRooms,
} from '../features/proctor/api/proctorApi';
import { getGradebookSubmissionDetail, listGradebookSubmissions } from '../features/gradebook/gradebookApi';
import { getAdminDashboardAlerts, getAdminDashboardSummary } from '../features/dashboard/adminDashboardApi';
import { getAccessToken, getRefreshToken } from '../shared/auth/tokenStorage';

const mockedGetCurrentUser = vi.mocked(getCurrentUser);
const mockedGetAccessToken = vi.mocked(getAccessToken);
const mockedGetRefreshToken = vi.mocked(getRefreshToken);
const mockedListMySittingRooms = vi.mocked(listMySittingRooms);
const mockedGetProctorRoomRoster = vi.mocked(getProctorRoomRoster);
const mockedListProctorRoomAttendance = vi.mocked(listProctorRoomAttendance);
const mockedListProctorRoomIncidents = vi.mocked(listProctorRoomIncidents);
const mockedGetProctorRoomReadiness = vi.mocked(getProctorRoomReadiness);
const mockedGetProctorRoomClosePreflight = vi.mocked(getProctorRoomClosePreflight);
const mockedListGradebookSubmissions = vi.mocked(listGradebookSubmissions);
const mockedGetGradebookSubmissionDetail = vi.mocked(getGradebookSubmissionDetail);
const mockedGetAdminDashboardSummary = vi.mocked(getAdminDashboardSummary);
const mockedGetAdminDashboardAlerts = vi.mocked(getAdminDashboardAlerts);

function successUser(roles: string[], permissions: string[] = []) {
  return {
    ok: true as const,
    success: true as const,
    data: {
      user_id: 2,
      username: 'student',
      display_name: 'Student',
      roles,
      permissions,
    },
    message: null,
    error: null,
  };
}

function frontendFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) {
      return frontendFiles(path);
    }
    return /\.(ts|tsx)$/.test(entry) && !/\.test\.(ts|tsx)$/.test(entry) ? [path] : [];
  });
}

beforeEach(() => {
  vi.resetAllMocks();
  mockedGetAccessToken.mockReturnValue('access-token');
  mockedGetRefreshToken.mockReturnValue(null);
  mockedGetCurrentUser.mockResolvedValue(successUser(['STUDENT']));
  mockedListMySittingRooms.mockResolvedValue([]);
  mockedGetProctorRoomRoster.mockResolvedValue({ exam_sitting_id: 10, exam_sitting_room_id: 100, room_code: 'D13', items: [] });
  mockedListProctorRoomAttendance.mockResolvedValue({ exam_sitting_id: 10, exam_sitting_room_id: 100, room_code: 'D13', items: [] });
  mockedListProctorRoomIncidents.mockResolvedValue([]);
  mockedGetProctorRoomReadiness.mockResolvedValue({ exam_sitting_id: 10, exam_sitting_room_id: 100, room_code: 'D13', items: [] });
  mockedGetProctorRoomClosePreflight.mockResolvedValue({
    exam_sitting_room_id: 100,
    room_code: 'D13',
    room_status: 'OPEN',
    can_close: true,
    blockers: [],
    warnings: [],
    counts: {
      total_assignments: 18,
      checked_in_count: 18,
      absent_count: 0,
      pending_attendance_count: 0,
      open_incident_count: 0,
      in_progress_incident_count: 0,
      active_session_count: 0,
      interrupted_session_count: 0,
      pending_submission_count: 0,
      stale_heartbeat_count: 0,
    },
    generated_at: '2026-05-22T04:00:00Z',
  });
  mockedListGradebookSubmissions.mockResolvedValue({
    items: [],
    total: 0,
    limit: 50,
    offset: 0,
  });
  mockedGetGradebookSubmissionDetail.mockResolvedValue({
    submission: {
      exam_submission_id: 123,
      student_id: 456,
      student_code: 'SV001',
      student_full_name: 'Nguyen Van A',
      exam_id: 1,
      exam_title: 'SQL Midterm',
      exam_sitting_id: 10,
      exam_sitting_room_id: 98,
      room_name: 'Lab A',
      submission_status: 'SUBMITTED',
      sealed_at: '2026-05-20T10:00:00+00:00',
      grading_status: 'COMPUTED',
      total_score: '10.00',
      max_score: '10.00',
      percentage: '100.00',
      needs_review: false,
      question_score_count: 1,
      manual_review_count: 0,
      last_graded_at: '2026-05-20T10:05:00+00:00',
    },
    score: null,
    question_scores: [],
    manual_reviews: [],
    jobs: [],
    events: [],
  });
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

describe('AppRouter guards and static navigation boundaries', () => {
  test('unauthorized student cannot access admin dashboard and is not shown admin navigation', async () => {
    window.history.pushState({}, '', '/admin/dashboard');

    render(<AppRouter />);

    expect(await screen.findByText(/Không có quyền truy cập/i)).toBeInTheDocument();
    await waitFor(() => expect(mockedGetCurrentUser).toHaveBeenCalled());
    expect(screen.queryByRole('link', { name: /Admin Dashboard/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Master Data/i })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Đổi mật khẩu' })).toHaveAttribute('href', '/change-password');
  });

  test('production navigation does not contain hard-coded demo submission result link', () => {
    const routerSource = readFileSync(join(process.cwd(), 'src/app/router.tsx'), 'utf8');
    expect(routerSource).not.toContain('/submissions/12001/result');
  });

  test('admin sees only one Dashboard menu entry and no Admin Dashboard label', async () => {
    mockedGetCurrentUser.mockResolvedValue(
      successUser(['ADMIN'], ['master_data:read', 'delivery:manage', 'master_data:write'])
    );
    window.history.pushState({}, '', '/dashboard');

    render(<AppRouter />);

    expect(await screen.findByRole('link', { name: 'Dashboard' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Admin Dashboard' })).not.toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'Dashboard' })).toHaveLength(1);
    expect(screen.queryByRole('link', { name: 'Môn học' })).not.toBeInTheDocument();
  });

  test('admin dashboard route renders the compact dashboard shell', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['ADMIN']));
    window.history.pushState({}, '', '/dashboard');

    render(<AppRouter />);

    expect(await screen.findByRole('heading', { name: /Dashboard/i })).toBeInTheDocument();
  });

  test('admin visiting /admin/dashboard is redirected to /dashboard', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['ADMIN']));
    window.history.pushState({}, '', '/admin/dashboard');

    render(<AppRouter />);

    await waitFor(() => expect(window.location.pathname).toBe('/dashboard'));
  });

  test('proctor cannot access admin dashboard route', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['PROCTOR']));
    window.history.pushState({}, '', '/admin/dashboard');

    render(<AppRouter />);

    expect(await screen.findByText(/Không có quyền truy cập/i)).toBeInTheDocument();
  });

  test('admin visiting /admin/subjects is redirected to /master-data', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['ADMIN'], ['master_data:read', 'master_data:write']));
    window.history.pushState({}, '', '/admin/subjects');

    render(<AppRouter />);

    await waitFor(() => expect(window.location.pathname).toBe('/admin/master-data/academic'));
  });

  test('admin landing route /admin/master-data renders the landing page', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['ADMIN'], ['master_data:read', 'master_data:write']));
    window.history.pushState({}, '', '/admin/master-data');

    render(<AppRouter />);

    expect(await screen.findByRole('heading', { name: 'Trung tâm dữ liệu nền' })).toBeInTheDocument();
  });

  test('admin academic route renders academic surface', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['ADMIN'], ['master_data:read', 'master_data:write']));
    window.history.pushState({}, '', '/admin/master-data/academic');

    render(<AppRouter />);

    expect(await screen.findByRole('heading', { name: 'Danh mục học thuật' })).toBeInTheDocument();
  });

  test('admin people route renders people surface', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['ADMIN'], ['master_data:read', 'master_data:write']));
    window.history.pushState({}, '', '/admin/master-data/people');

    render(<AppRouter />);

    expect(await screen.findByRole('heading', { name: 'Sinh viên và giảng viên' })).toBeInTheDocument();
  });

  test('admin facility route renders facility surface', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['ADMIN'], ['master_data:read', 'master_data:write']));
    window.history.pushState({}, '', '/admin/facility');

    render(<AppRouter />);

    expect(await screen.findByRole('heading', { name: 'Cơ sở vật chất phòng thi' })).toBeInTheDocument();
  });

  test('admin imports route renders import surface', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['ADMIN'], ['master_data:read', 'master_data:write']));
    window.history.pushState({}, '', '/admin/imports');

    render(<AppRouter />);

    expect(await screen.findByRole('heading', { name: 'Import dữ liệu nền' })).toBeInTheDocument();
  });

  test('compatibility route /master-data redirects to /admin/master-data', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['ADMIN'], ['master_data:read', 'master_data:write']));
    window.history.pushState({}, '', '/master-data');

    render(<AppRouter />);

    await waitFor(() => expect(window.location.pathname).toBe('/admin/master-data'));
  });

  test('admin exam setup route still renders', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['ADMIN'], ['master_data:read', 'delivery:manage']));
    window.history.pushState({}, '', '/admin/exam-setup');

    render(<AppRouter />);

    expect(await screen.findByRole('heading', { name: 'Thiết lập trước khi thi' })).toBeInTheDocument();
    const workflowLinks = screen.getAllByRole('link', { name: 'Mở workflow' });
    expect(workflowLinks).toHaveLength(2);
    expect(workflowLinks[0]).toHaveAttribute('href', '/admin/exam-setup/authoring');
    expect(workflowLinks[1]).toHaveAttribute('href', '/admin/exam-setup/delivery');
    expect(screen.queryByText(/Worker process heartbeat/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Đề gốc' })).not.toBeInTheDocument();
  });

  test('admin settings route still renders', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['ADMIN']));
    window.history.pushState({}, '', '/admin/settings');

    render(<AppRouter />);

    expect(await screen.findByRole('heading', { name: /Cấu hình hệ thống/i })).toBeInTheDocument();
  });

  test('admin exam authoring route renders authoring workflow only', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['ADMIN'], ['master_data:read', 'delivery:manage']));
    window.history.pushState({}, '', '/admin/exam-setup/authoring');

    render(<AppRouter />);

    expect(await screen.findByTestId('exam-authoring-page')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Exam Authoring' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Đề gốc' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Ca thi' })).not.toBeInTheDocument();
  });

  test('admin delivery setup route renders delivery workflow only', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['ADMIN'], ['master_data:read', 'delivery:manage']));
    window.history.pushState({}, '', '/admin/exam-setup/delivery');

    render(<AppRouter />);

    expect(await screen.findByTestId('delivery-setup-page')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Delivery Setup' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ca thi' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Đề gốc' })).not.toBeInTheDocument();
  });

  test('proctor sittings route renders the real API-backed page after auth', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['PROCTOR']));
    mockedListMySittingRooms.mockResolvedValue([
      {
        exam_sitting_id: 10,
        exam_sitting_room_id: 100,
        room_id: 1,
        room_code: 'D13',
        room_name: 'Phòng D13',
        sitting_code: 'S1',
        sitting_name: 'Ca sáng',
        sitting_status: 'OPEN',
        scheduled_start_at: '2026-05-21T08:00:00+07:00',
        scheduled_end_at: '2026-05-21T10:00:00+07:00',
        room_status: 'READY',
        capacity_allocated: 20,
        assigned_student_count: 18,
        assigned_station_count: 18,
      },
    ]);
    window.history.pushState({}, '', '/proctor/sittings');

    render(<AppRouter />);

    expect(await screen.findByTestId('proctor-sittings-page')).toBeInTheDocument();
    expect(await screen.findByText('D13 - S1')).toBeInTheDocument();
    expect(screen.queryByText(/Live Proctoring/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Close Room|Khóa phòng/i)).not.toBeInTheDocument();
  });

  test('proctor room workspace routes render real shells', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['PROCTOR']));
    mockedGetProctorRoomRoster.mockResolvedValue({
      exam_sitting_id: 10,
      exam_sitting_room_id: 100,
      room_code: 'D13',
      items: [],
    });
    mockedGetProctorRoomReadiness.mockResolvedValue({
      exam_sitting_id: 10,
      exam_sitting_room_id: 100,
      room_code: 'D13',
      items: [],
    });

    window.history.pushState({}, '', '/proctor/sitting-rooms/100');
    render(<AppRouter />);

    expect(await screen.findByTestId('proctor-room-workspace-page')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Danh sách thí sinh/i })).toHaveAttribute('href', '/proctor/sitting-rooms/100/attendance');
    expect(screen.getByRole('link', { name: /Close Room/i })).toHaveAttribute('href', '/proctor/sitting-rooms/100/close');
  });

  test('proctor close room route renders the active close-room page', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['PROCTOR']));
    window.history.pushState({}, '', '/proctor/sitting-rooms/100/close');

    render(<AppRouter />);

    expect(await screen.findByTestId('proctor-close-room-page')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Close Room/i })).toBeInTheDocument();
  });

  test('proctor attendance route renders active page', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['PROCTOR']));
    window.history.pushState({}, '', '/proctor/sitting-rooms/100/attendance');

    render(<AppRouter />);

    expect(await screen.findByTestId('proctor-attendance-page')).toBeInTheDocument();
  });

  test('proctor live route renders active page', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['PROCTOR']));
    window.history.pushState({}, '', '/proctor/sitting-rooms/100/live');

    render(<AppRouter />);

    expect(await screen.findByTestId('proctor-live-page')).toBeInTheDocument();
  });

  test('proctor incidents route renders active page', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['PROCTOR']));
    window.history.pushState({}, '', '/proctor/sitting-rooms/100/incidents');

    render(<AppRouter />);

    expect(await screen.findByTestId('proctor-incidents-page')).toBeInTheDocument();
  });

  test('student cannot access proctor close room route and auth guard still applies', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['STUDENT']));
    window.history.pushState({}, '', '/proctor/sitting-rooms/100/close');

    render(<AppRouter />);

    expect(await screen.findByText(/Không có quyền truy cập/i)).toBeInTheDocument();
  });

  test('admin can access gradebook route and sees sidebar entry', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['ADMIN']));
    window.history.pushState({}, '', '/grading/gradebook');

    render(<AppRouter />);

    expect(await screen.findByTestId('gradebook-page')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Bảng điểm' })).toHaveAttribute('href', '/grading/gradebook');
  });

  test('instructor can access gradebook route', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['INSTRUCTOR']));
    window.history.pushState({}, '', '/grading/gradebook');

    render(<AppRouter />);

    expect(await screen.findByTestId('gradebook-page')).toBeInTheDocument();
  });

  test('student is denied gradebook route', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['STUDENT']));
    window.history.pushState({}, '', '/grading/gradebook');

    render(<AppRouter />);

    expect(await screen.findByText(/Không có quyền truy cập/i)).toBeInTheDocument();
  });

  test('proctor is denied gradebook route', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['PROCTOR']));
    window.history.pushState({}, '', '/grading/gradebook');

    render(<AppRouter />);

    expect(await screen.findByText(/Không có quyền truy cập/i)).toBeInTheDocument();
  });

  test('sidebar gradebook entry is hidden for student and visible for instructor', async () => {
    mockedGetCurrentUser.mockResolvedValue(successUser(['STUDENT']));
    window.history.pushState({}, '', '/dashboard');

    const { unmount } = render(<AppRouter />);

    await waitFor(() => expect(mockedGetCurrentUser).toHaveBeenCalled());
    expect(screen.queryByRole('link', { name: 'Bảng điểm' })).not.toBeInTheDocument();

    unmount();
    mockedGetCurrentUser.mockResolvedValue(successUser(['INSTRUCTOR']));
    window.history.pushState({}, '', '/dashboard');

    render(<AppRouter />);

    expect(await screen.findByRole('link', { name: 'Bảng điểm' })).toHaveAttribute('href', '/grading/gradebook');
  });

  test('frontend code does not import worker code or reference database connection settings', () => {
    const sourceRoot = join(process.cwd(), 'src');
    const combined = frontendFiles(sourceRoot)
      .map((file) => readFileSync(file, 'utf8'))
      .join('\n');

    expect(combined).not.toMatch(/apps[\\/]worker|worker_runtime|from ['"].*worker/i);
    expect(combined).not.toMatch(/postgres:\/\/|PGPASSWORD|DATABASE_URL|connection_profile_ref/i);
    expect(combined).not.toMatch(/celery|dramatiq|rq worker|worker cli/i);
  });

  test('/change-password with an access token loads current user and renders the page', async () => {
    mockedGetAccessToken.mockReturnValue('access-token');
    mockedGetRefreshToken.mockReturnValue(null);
    mockedGetCurrentUser.mockResolvedValue(successUser(['STUDENT']));
    window.history.pushState({}, '', '/change-password');

    render(<AppRouter />);

    expect(await screen.findByRole('heading', { name: 'Đổi mật khẩu' })).toBeInTheDocument();
    expect(mockedGetCurrentUser).toHaveBeenCalled();
  });

  test('/change-password without access token and without refresh token redirects to /login', async () => {
    mockedGetAccessToken.mockReturnValue(null);
    mockedGetRefreshToken.mockReturnValue(null);
    window.history.pushState({}, '', '/change-password');

    render(<AppRouter />);

    await waitFor(() => expect(window.location.pathname).toBe('/login'));
  });

  test('/login remains public and does not call getCurrentUser()', async () => {
    mockedGetAccessToken.mockReturnValue(null);
    mockedGetRefreshToken.mockReturnValue(null);
    window.history.pushState({}, '', '/login');

    render(<AppRouter />);

    await waitFor(() => {
      expect(document.querySelector('#identifier')).not.toBeNull();
    });
    await waitFor(() => {
      expect(mockedGetCurrentUser).not.toHaveBeenCalled();
    });
  });

  test('blank layout is not equivalent to public auth', async () => {
    mockedGetAccessToken.mockReturnValue('access-token');
    mockedGetRefreshToken.mockReturnValue(null);
    mockedGetCurrentUser.mockResolvedValue(successUser(['STUDENT']));
    window.history.pushState({}, '', '/change-password');

    render(<AppRouter />);

    expect(await screen.findByRole('heading', { name: 'Đổi mật khẩu' })).toBeInTheDocument();
    expect(mockedGetCurrentUser).toHaveBeenCalled();
  });
});
