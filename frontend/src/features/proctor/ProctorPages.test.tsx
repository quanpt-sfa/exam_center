import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import type { ReactNode } from 'react';
import { ProctorAttendancePage } from './ProctorAttendancePage';
import { ProctorCloseRoomPage } from './ProctorCloseRoomPage';
import { ProctorIncidentsPage } from './ProctorIncidentsPage';
import { ProctorLivePage } from './ProctorLivePage';
import { ProctorRoomWorkspacePage } from './ProctorRoomWorkspacePage';
import { ProctorSittingsPage } from './ProctorSittingsPage';
import {
  canProctorResolveIncident,
  getAllowedProctorIncidentTransitions,
  incidentStatusLabel,
  isIncidentTerminal,
  requiresResolutionNoteForTransition,
} from './proctorDisplay';

vi.mock('./api/proctorApi', () => ({
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

import {
  checkInAssignment,
  createProctorIncident,
  closeProctorRoom,
  getProctorRoomClosePreflight,
  getProctorRoomReadiness,
  getProctorRoomRoster,
  listProctorRoomAttendance,
  listProctorRoomIncidents,
  listMySittingRooms,
  markAssignmentAbsent,
  revokeStudentStaleSession,
  scanCheckInAttendance,
  updateProctorIncident,
  verifyAssignmentIdentity,
} from './api/proctorApi';

const mockedListMySittingRooms = vi.mocked(listMySittingRooms);
const mockedGetProctorRoomRoster = vi.mocked(getProctorRoomRoster);
const mockedListProctorRoomAttendance = vi.mocked(listProctorRoomAttendance);
const mockedCheckInAssignment = vi.mocked(checkInAssignment);
const mockedMarkAssignmentAbsent = vi.mocked(markAssignmentAbsent);
const mockedVerifyAssignmentIdentity = vi.mocked(verifyAssignmentIdentity);
const mockedScanCheckInAttendance = vi.mocked(scanCheckInAttendance);
const mockedGetProctorRoomReadiness = vi.mocked(getProctorRoomReadiness);
const mockedGetProctorRoomClosePreflight = vi.mocked(getProctorRoomClosePreflight);
const mockedCloseProctorRoom = vi.mocked(closeProctorRoom);
const mockedListProctorRoomIncidents = vi.mocked(listProctorRoomIncidents);
const mockedCreateProctorIncident = vi.mocked(createProctorIncident);
const mockedRevokeStudentStaleSession = vi.mocked(revokeStudentStaleSession);
const mockedUpdateProctorIncident = vi.mocked(updateProctorIncident);
const invalidRoomMessage = 'Mã phòng thi không hợp lệ. Vui lòng quay lại danh sách phòng được phân công.';

let localStorageSetItemSpy: ReturnType<typeof vi.spyOn> | null = null;
let sessionStorageSetItemSpy: ReturnType<typeof vi.spyOn> | null = null;

function room() {
  return {
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
  };
}

function rosterResponse() {
  return {
    exam_sitting_id: 10,
    exam_sitting_room_id: 100,
    room_code: 'D13',
    items: [
      {
        exam_sitting_id: 10,
        exam_sitting_room_id: 100,
        room_code: 'D13',
        exam_assignment_id: 555,
        station_id: 11,
        station_code: 'A1',
        student_id: 1001,
        student_code: 'SV001',
        full_name: 'Nguyễn A',
        photo_ref: null,
        assignment_status: 'ASSIGNED',
        station_assignment_status: 'ASSIGNED',
        planned_device_id: 5,
        planned_device_asset_tag: 'PC-01',
        last_checkin_at: '2026-05-21T07:55:00+07:00',
        latest_health_status: 'READY',
        exam_session_id: 777,
        session_code: 'SESS-1',
        session_status: 'IN_PROGRESS',
        started_at: '2026-05-21T08:01:00+07:00',
        ended_at: null,
        last_seen_at: '2026-05-21T08:10:00+07:00',
        exam_submission_id: 888,
        submission_status: 'IN_PROGRESS',
        submitted_at: null,
        sealed_at: null,
      },
    ],
  };
}

function readinessResponse() {
  return {
    exam_sitting_id: 10,
    exam_sitting_room_id: 100,
    room_code: 'D13',
    items: [{ station_code: 'A1', asset_tag: 'PC-01', last_checkin_at: '2026-05-21T07:55:00+07:00', health_status: 'READY', mismatch: false }],
  };
}

function closePreflightResponse(overrides: Partial<{
  exam_sitting_room_id: number;
  room_code: string | null;
  room_status: string;
  can_close: boolean;
  blockers: Array<{ code: string; severity: string; message: string; count: number; details: Array<Record<string, unknown>> | null }>;
  warnings: Array<{ code: string; severity: string; message: string; count: number; details: Array<Record<string, unknown>> | null }>;
  counts: {
    total_assignments: number;
    checked_in_count: number;
    absent_count: number;
    pending_attendance_count: number;
    open_incident_count: number;
    in_progress_incident_count: number;
    active_session_count: number;
    interrupted_session_count: number;
    pending_submission_count: number;
    stale_heartbeat_count: number;
  };
  generated_at: string;
}> = {}) {
  return {
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
    ...overrides,
  };
}

function closeRoomResponse(overrides: Partial<{
  status: string;
  exam_sitting_room_id: number;
  previous_status: string | null;
  new_status: string;
  closed_at: string | null;
  closed_by: number | null;
  close_summary: Record<string, unknown>;
  blockers: Array<{ code: string; severity: string; message: string; count: number; details: Array<Record<string, unknown>> | null }>;
}> = {}) {
  return {
    status: 'closed',
    exam_sitting_room_id: 100,
    previous_status: 'OPEN',
    new_status: 'CLOSED',
    closed_at: '2026-05-22T04:05:00Z',
    closed_by: 2,
    close_summary: { counts: { total_assignments: 18 } },
    blockers: [],
    ...overrides,
  };
}

function attendanceResponse() {
  return {
    exam_sitting_id: 10,
    exam_sitting_room_id: 100,
    room_code: 'D13',
    items: [
      {
        exam_sitting_id: 10,
        exam_sitting_room_id: 100,
        room_code: 'D13',
        exam_assignment_id: 555,
        station_assignment_id: 9001,
        station_id: 11,
        station_code: 'A1',
        student_id: 1001,
        student_code: 'SV001',
        full_name: 'Nguyễn A',
        photo_url: null,
        assignment_status: 'ASSIGNED',
        station_assignment_status: 'ASSIGNED',
        latest_verification_status: null,
        latest_verification_method: null,
        latest_verified_at: null,
        latest_verified_by: null,
        checked_in_at: null,
        checked_in_by: null,
        latest_attendance_note: null,
        exam_session_id: 777,
        session_status: 'IN_PROGRESS',
        submission_status: 'IN_PROGRESS',
        last_seen_at: '2026-05-21T08:10:00+07:00',
      },
    ],
  };
}

function incident(overrides: Partial<ReturnType<typeof incidentListResponse>[number]> = {}) {
  return {
    incident_id: 1,
    exam_sitting_id: 10,
    exam_sitting_room_id: 100,
    exam_assignment_id: 555,
    exam_session_id: null,
    station_id: 11,
    device_id: 5,
    incident_type: 'DEVICE_FAILURE',
    incident_status: 'OPEN',
    reported_by: 2,
    reported_at: '2026-05-21T10:00:00Z',
    resolved_by: null,
    resolved_at: null,
    updated_by: null,
    updated_at: null,
    resolution_note: null,
    description: 'Mất mạng',
    metadata_json: {},
    ...overrides,
  };
}

function incidentListResponse() {
  return [incident()];
}

function renderAt(path: string, element: ReactNode, routePath: string) {
  return render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }} initialEntries={[path]}>
      <Routes>
        <Route path={routePath} element={element} />
      </Routes>
    </MemoryRouter>
  );
}

describe('Phase 2B proctor pages', () => {
  afterEach(() => {
    vi.useRealTimers();
    localStorageSetItemSpy?.mockRestore();
    sessionStorageSetItemSpy?.mockRestore();
    localStorageSetItemSpy = null;
    sessionStorageSetItemSpy = null;
  });

  beforeEach(() => {
    vi.resetAllMocks();
    mockedListMySittingRooms.mockResolvedValue([room()]);
    mockedGetProctorRoomRoster.mockResolvedValue(rosterResponse());
    mockedListProctorRoomAttendance.mockResolvedValue(attendanceResponse());
    mockedCheckInAssignment.mockResolvedValue({ ...attendanceResponse().items[0], assignment_status: 'CHECKED_IN', station_assignment_status: 'CHECKED_IN' });
    mockedMarkAssignmentAbsent.mockResolvedValue({ ...attendanceResponse().items[0], assignment_status: 'ABSENT', station_assignment_status: 'NO_SHOW' });
    mockedVerifyAssignmentIdentity.mockResolvedValue({
      checkin_verification_id: 1,
      exam_sitting_room_id: 100,
      exam_assignment_id: 555,
      station_assignment_id: 9001,
      exam_session_id: 777,
      verification_status: 'VERIFIED',
      verification_method: 'PHOTO_ID',
      verified_at: '2026-05-21T08:12:00+07:00',
      verified_by: 2,
      note: 'Khớp',
      metadata_json: null,
    });
    mockedScanCheckInAttendance.mockResolvedValue({
      ...attendanceResponse().items[0],
      assignment_status: 'CHECKED_IN',
      station_assignment_status: 'CHECKED_IN',
      scan_match_type: 'STUDENT_CODE',
    });
    mockedGetProctorRoomReadiness.mockResolvedValue(readinessResponse());
    mockedGetProctorRoomClosePreflight.mockResolvedValue(closePreflightResponse());
    mockedCloseProctorRoom.mockResolvedValue(closeRoomResponse());
    mockedListProctorRoomIncidents.mockResolvedValue(incidentListResponse());
    mockedRevokeStudentStaleSession.mockResolvedValue({ status: 'revoked' });
    mockedUpdateProctorIncident.mockResolvedValue(
      incident({
        incident_status: 'IN_PROGRESS',
        updated_by: 2,
        updated_at: '2026-05-21T10:06:00Z',
      })
    );
    mockedCreateProctorIncident.mockResolvedValue({
      ...incident(),
      exam_assignment_id: null,
      station_id: null,
      device_id: null,
    });
  });

  test('sittings page shows loading first and does not render fake room data before API success', async () => {
    let resolveRooms: ((value: ReturnType<typeof room>[]) => void) | null = null;
    mockedListMySittingRooms.mockReturnValue(
      new Promise((resolve) => {
        resolveRooms = resolve;
      })
    );

    renderAt('/proctor/sittings', <ProctorSittingsPage />, '/proctor/sittings');

    expect(screen.getByText('Đang tải danh sách phòng được phân công...')).toBeInTheDocument();
    expect(screen.queryByText('D13 - S1')).not.toBeInTheDocument();

    resolveRooms?.([room()]);

    expect(await screen.findByText('D13 - S1')).toBeInTheDocument();
  });

  test('sittings page handles empty state and retry', async () => {
    mockedListMySittingRooms.mockResolvedValueOnce([]).mockResolvedValueOnce([room()]);

    renderAt('/proctor/sittings', <ProctorSittingsPage />, '/proctor/sittings');

    const emptyStateMessage = await screen.findByText('Hiện chưa có phòng thi nào được phân công cho tài khoản này.');
    fireEvent.click(within(emptyStateMessage.closest('div') as HTMLElement).getByRole('button', { name: 'Tải lại' }));
    expect(await screen.findByText('D13 - S1')).toBeInTheDocument();
  });

  test('workspace page loads roster and readiness', async () => {
    renderAt('/proctor/sitting-rooms/100', <ProctorRoomWorkspacePage />, '/proctor/sitting-rooms/:examSittingRoomId');

    expect(await screen.findByTestId('proctor-room-workspace-page')).toBeInTheDocument();
    expect(screen.getByText(/Đi theo thứ tự Attendance/i)).toBeInTheDocument();
    expect(screen.getByText('SV001')).toBeInTheDocument();
    expect(screen.getByText('Tình trạng readiness')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Danh sách thí sinh/i })).toHaveAttribute('href', '/proctor/sitting-rooms/100/attendance');
    expect(screen.getByRole('link', { name: /Theo dõi phòng thi/i })).toHaveAttribute('href', '/proctor/sitting-rooms/100/live');
    expect(screen.getByRole('link', { name: /Close Room/i })).toHaveAttribute('href', '/proctor/sitting-rooms/100/close');
    expect(screen.queryByText(/Attendance \/ roster|Live monitor/i)).not.toBeInTheDocument();
  });

  test('close room page rejects invalid route params without calling close APIs', async () => {
    renderAt('/proctor/sitting-rooms/abc/close', <ProctorCloseRoomPage />, '/proctor/sitting-rooms/:examSittingRoomId/close');

    expect(await screen.findByText(invalidRoomMessage)).toBeInTheDocument();
    expect(mockedGetProctorRoomClosePreflight).not.toHaveBeenCalled();
    expect(mockedCloseProctorRoom).not.toHaveBeenCalled();
  });

  test('close room page loads preflight success and renders counts', async () => {
    mockedGetProctorRoomClosePreflight.mockResolvedValueOnce(
      closePreflightResponse({
        warnings: [{ code: 'FUTURE_WARNING', severity: 'warning', message: 'Review room note', count: 1, details: [{ source: 'ops' }] }],
      })
    );

    renderAt('/proctor/sitting-rooms/100/close', <ProctorCloseRoomPage />, '/proctor/sitting-rooms/:examSittingRoomId/close');

    expect(await screen.findByTestId('proctor-close-room-page')).toBeInTheDocument();
    expect(screen.getByText('OPEN')).toBeInTheDocument();
    expect(screen.getByText('Yes')).toBeInTheDocument();
    expect(screen.getByText('Counts from backend')).toBeInTheDocument();
    expect(screen.getByText('Total assignments').closest('.compact-statbar__item')).toHaveTextContent('18');
    expect(screen.getByText('Warnings')).toBeInTheDocument();
    expect(screen.getByText('Review room note')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Close Room' })).toBeInTheDocument();
  });

  test('close room page shows preflight error honestly and allows retry without fake can_close', async () => {
    mockedGetProctorRoomClosePreflight
      .mockRejectedValueOnce(new Error('permission_denied'))
      .mockResolvedValueOnce(closePreflightResponse());

    renderAt('/proctor/sitting-rooms/100/close', <ProctorCloseRoomPage />, '/proctor/sitting-rooms/:examSittingRoomId/close');

    expect(await screen.findByText('permission_denied')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Close Room' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }));
    expect(await screen.findByRole('button', { name: 'Close Room' })).toBeInTheDocument();
  });

  test('close room page renders blockers and disables close when can_close is false', async () => {
    mockedGetProctorRoomClosePreflight.mockResolvedValueOnce(
      closePreflightResponse({
        can_close: false,
        blockers: [
          { code: 'ACTIVE_SESSIONS', severity: 'hard', message: 'Active sessions still exist', count: 2, details: [{ student_code: 'SV001' }] },
          { code: 'INCIDENTS_UNRESOLVED', severity: 'hard', message: 'Open incidents remain', count: 1, details: [{ incident_id: 99 }] },
        ],
        counts: {
          ...closePreflightResponse().counts,
          active_session_count: 2,
          open_incident_count: 1,
        },
      })
    );

    renderAt('/proctor/sitting-rooms/100/close', <ProctorCloseRoomPage />, '/proctor/sitting-rooms/:examSittingRoomId/close');

    expect(await screen.findByText('Active sessions still exist')).toBeInTheDocument();
    expect(screen.getByText('Open incidents remain')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Close Room unavailable' })).toBeDisabled();
  });

  test('close room page shows already closed state as read-only', async () => {
    mockedGetProctorRoomClosePreflight.mockResolvedValueOnce(
      closePreflightResponse({ room_status: 'CLOSED', can_close: false, blockers: [{ code: 'ROOM_ALREADY_CLOSED', severity: 'hard', message: 'Room is already closed', count: 1, details: null }] })
    );

    renderAt('/proctor/sitting-rooms/100/close', <ProctorCloseRoomPage />, '/proctor/sitting-rooms/:examSittingRoomId/close');

    expect(await screen.findByText(/Phòng này đã ở trạng thái CLOSED/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Close Room unavailable' })).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Close Room' })).not.toBeInTheDocument();
  });

  test('close room page shows invalid status blocker honestly', async () => {
    mockedGetProctorRoomClosePreflight.mockResolvedValueOnce(
      closePreflightResponse({
        room_status: 'CANCELLED',
        can_close: false,
        blockers: [{ code: 'ROOM_NOT_CLOSEABLE', severity: 'hard', message: 'Room cannot be closed from its current status', count: 1, details: [{ room_status: 'CANCELLED' }] }],
      })
    );

    renderAt('/proctor/sitting-rooms/100/close', <ProctorCloseRoomPage />, '/proctor/sitting-rooms/:examSittingRoomId/close');

    expect(await screen.findByText('CANCELLED')).toBeInTheDocument();
    expect(screen.getByText('Room cannot be closed from its current status')).toBeInTheDocument();
  });

  test('close room page handles close success and refetches preflight', async () => {
    mockedGetProctorRoomClosePreflight
      .mockResolvedValueOnce(closePreflightResponse())
      .mockResolvedValueOnce(closePreflightResponse({ room_status: 'CLOSED', can_close: false, blockers: [{ code: 'ROOM_ALREADY_CLOSED', severity: 'hard', message: 'Room is already closed', count: 1, details: null }] }));
    mockedCloseProctorRoom.mockResolvedValueOnce(closeRoomResponse());

    renderAt('/proctor/sitting-rooms/100/close', <ProctorCloseRoomPage />, '/proctor/sitting-rooms/:examSittingRoomId/close');

    expect(await screen.findByRole('button', { name: 'Close Room' })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Close note'), { target: { value: 'all done' } });
    fireEvent.click(screen.getByRole('button', { name: 'Close Room' }));

    const dialog = await screen.findByRole('alertdialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Xác nhận đóng phòng' }));

    expect(await screen.findByText('Kết quả đóng phòng')).toBeInTheDocument();
    expect(screen.getByText(/Phòng này đã ở trạng thái CLOSED/i)).toBeInTheDocument();
    await waitFor(() => expect(mockedCloseProctorRoom).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(mockedGetProctorRoomClosePreflight).toHaveBeenCalledTimes(2));
  });

  test('close room page shows backend blocked error and does not fake success', async () => {
    mockedGetProctorRoomClosePreflight
      .mockResolvedValueOnce(closePreflightResponse())
      .mockResolvedValueOnce(
        closePreflightResponse({
          can_close: false,
          blockers: [{ code: 'ACTIVE_SESSIONS', severity: 'hard', message: 'Active sessions still exist', count: 1, details: [{ student_code: 'SV001' }] }],
        })
      );
    mockedCloseProctorRoom.mockRejectedValueOnce(
      Object.assign(new Error('Room cannot be closed while hard blockers remain'), {
        code: 'room_close_blocked',
        details: { blockers: [{ code: 'ACTIVE_SESSIONS' }] },
      })
    );

    renderAt('/proctor/sitting-rooms/100/close', <ProctorCloseRoomPage />, '/proctor/sitting-rooms/:examSittingRoomId/close');

    expect(await screen.findByRole('button', { name: 'Close Room' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Close Room' }));

    const dialog = await screen.findByRole('alertdialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Xác nhận đóng phòng' }));

    expect(await screen.findByText(/room_close_blocked: Room cannot be closed while hard blockers remain/)).toBeInTheDocument();
    expect(screen.queryByText('Kết quả đóng phòng')).not.toBeInTheDocument();
    await waitFor(() => expect(mockedGetProctorRoomClosePreflight).toHaveBeenCalledTimes(2));
  });

  test('duplicate close submit is guarded while request is pending', async () => {
    mockedCloseProctorRoom.mockReturnValueOnce(new Promise(() => {}));

    renderAt('/proctor/sitting-rooms/100/close', <ProctorCloseRoomPage />, '/proctor/sitting-rooms/:examSittingRoomId/close');

    expect(await screen.findByRole('button', { name: 'Close Room' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Close Room' }));

    const dialog = await screen.findByRole('alertdialog');
    const confirmButton = within(dialog).getByRole('button', { name: 'Xác nhận đóng phòng' });
    fireEvent.click(confirmButton);
    fireEvent.click(confirmButton);

    await waitFor(() => expect(mockedCloseProctorRoom).toHaveBeenCalledTimes(1));
  });

  test('close room page never renders force-close or reopen actions', async () => {
    renderAt('/proctor/sitting-rooms/100/close', <ProctorCloseRoomPage />, '/proctor/sitting-rooms/:examSittingRoomId/close');

    expect(await screen.findByTestId('proctor-close-room-page')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /force-close/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /reopen/i })).not.toBeInTheDocument();
  });

  test('close room page renders unknown blocker code and unknown room status safely', async () => {
    mockedGetProctorRoomClosePreflight.mockResolvedValueOnce(
      closePreflightResponse({
        room_status: 'MYSTERY_STATUS',
        can_close: false,
        blockers: [{ code: 'FUTURE_BLOCKER', severity: 'hard', message: 'Unknown future blocker', count: 1, details: [{ key: 'value' }] }],
      })
    );

    renderAt('/proctor/sitting-rooms/100/close', <ProctorCloseRoomPage />, '/proctor/sitting-rooms/:examSittingRoomId/close');

    expect(await screen.findByText('MYSTERY_STATUS')).toBeInTheDocument();
    expect(screen.getByText('Unknown future blocker')).toBeInTheDocument();
    expect(screen.getByText(/FUTURE BLOCKER/)).toBeInTheDocument();
  });

  test('workspace page rejects invalid route params without calling backend', async () => {
    renderAt('/proctor/sitting-rooms/0', <ProctorRoomWorkspacePage />, '/proctor/sitting-rooms/:examSittingRoomId');

    expect(await screen.findByText(invalidRoomMessage)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Quay lại danh sách phòng' })).toHaveAttribute('href', '/proctor/sittings');
    expect(mockedGetProctorRoomRoster).not.toHaveBeenCalled();
    expect(mockedGetProctorRoomReadiness).not.toHaveBeenCalled();
  });

  test('attendance page loads backend attendance list with scanner panel and supported actions only', async () => {
    renderAt('/proctor/sitting-rooms/100/attendance', <ProctorAttendancePage />, '/proctor/sitting-rooms/:examSittingRoomId/attendance');

    const page = await screen.findByTestId('proctor-attendance-page');
    expect(within(page).getByRole('table')).toHaveClass('table-compact');
    expect(screen.getByText('SV001')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Điểm danh phòng thi' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Check-in' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Đánh dấu vắng' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Xác minh danh tính' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Scan check-in' })).toBeInTheDocument();
    expect(screen.getByLabelText('Phương thức scan')).toHaveValue('BARCODE');
    expect(screen.queryByRole('option', { name: /QR_CCCD/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/Attendance \/ roster|Revoke stuck login/i)).not.toBeInTheDocument();
    expect(within(page).queryAllByRole('img')).toHaveLength(0);

    const checkInButton = screen.getByRole('button', { name: 'Check-in' });
    const actionCell = checkInButton.closest('td');
    expect(actionCell).not.toBeNull();
    const secondaryActionGroup = within(actionCell as HTMLElement).getByRole('button', { name: 'Đánh dấu vắng' }).closest('[data-action-group="true"]');
    expect(secondaryActionGroup).toHaveAttribute('data-action-mode', 'icon');
    expect(within(secondaryActionGroup as HTMLElement).queryByText('Thu hồi đăng nhập bị kẹt')).not.toBeInTheDocument();
  });

  test('attendance page rejects invalid route params without calling attendance or revoke APIs', async () => {
    renderAt('/proctor/sitting-rooms/abc/attendance', <ProctorAttendancePage />, '/proctor/sitting-rooms/:examSittingRoomId/attendance');

    expect(await screen.findByText(invalidRoomMessage)).toBeInTheDocument();
    expect(mockedListProctorRoomAttendance).not.toHaveBeenCalled();
    expect(mockedRevokeStudentStaleSession).not.toHaveBeenCalled();
  });

  test('attendance page shows empty state and retry for attendance API', async () => {
    mockedListProctorRoomAttendance.mockResolvedValueOnce({ exam_sitting_id: 10, exam_sitting_room_id: 100, room_code: 'D13', items: [] });

    renderAt('/proctor/sitting-rooms/100/attendance', <ProctorAttendancePage />, '/proctor/sitting-rooms/:examSittingRoomId/attendance');

    expect(await screen.findByText('Chưa có thí sinh nào trong danh sách điểm danh của phòng thi này.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Làm mới thủ công' }));
    await waitFor(() => expect(mockedListProctorRoomAttendance).toHaveBeenCalledTimes(2));
  });

  test('attendance page shows permission error honestly and allows retry', async () => {
    mockedListProctorRoomAttendance.mockRejectedValueOnce(new Error('permission_denied')).mockResolvedValueOnce(attendanceResponse());

    renderAt('/proctor/sitting-rooms/100/attendance', <ProctorAttendancePage />, '/proctor/sitting-rooms/:examSittingRoomId/attendance');

    expect(await screen.findByText('permission_denied')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }));
    expect(await screen.findByText('SV001')).toBeInTheDocument();
  });

  test('attendance page renders photo_url only when present and never uses raw photo_ref as img src', async () => {
    mockedListProctorRoomAttendance.mockResolvedValueOnce({
      ...attendanceResponse(),
      items: [
        {
          ...attendanceResponse().items[0],
          photo_url: 'https://assets.local/student-1.jpg',
        },
      ],
    });

    renderAt('/proctor/sitting-rooms/100/attendance', <ProctorAttendancePage />, '/proctor/sitting-rooms/:examSittingRoomId/attendance');

    const image = await screen.findByRole('img', { name: 'Ảnh SV001' });
    expect(image).toHaveAttribute('src', 'https://assets.local/student-1.jpg');
    expect(image).not.toHaveAttribute('src', 'internal-photo-key');
  });

  test('attendance page handles unknown statuses safely', async () => {
    mockedListProctorRoomAttendance.mockResolvedValueOnce({
      ...attendanceResponse(),
      items: [
        {
          ...attendanceResponse().items[0],
          assignment_status: 'MYSTERY_STATUS',
          latest_verification_status: 'MYSTERY_VERIFY',
        },
      ],
    });

    renderAt('/proctor/sitting-rooms/100/attendance', <ProctorAttendancePage />, '/proctor/sitting-rooms/:examSittingRoomId/attendance');

    expect(await screen.findByText(/MYSTERY_STATUS/)).toBeInTheDocument();
    expect(screen.getByText(/MYSTERY_VERIFY/)).toBeInTheDocument();
  });

  test('manual check-in success refreshes attendance list', async () => {
    renderAt('/proctor/sitting-rooms/100/attendance', <ProctorAttendancePage />, '/proctor/sitting-rooms/:examSittingRoomId/attendance');

    expect(await screen.findByText('SV001')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Check-in' }));
    const dialog = await screen.findByRole('alertdialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Xác nhận check-in' }));

    expect(await screen.findByText('Đã check-in SV001.')).toBeInTheDocument();
    await waitFor(() => expect(mockedCheckInAssignment).toHaveBeenCalledWith(100, 555, { checkin_method: 'MANUAL' }));
    await waitFor(() => expect(mockedListProctorRoomAttendance).toHaveBeenCalledTimes(2));
  });

  test('manual check-in failure shows backend error and no false success', async () => {
    mockedCheckInAssignment.mockRejectedValueOnce(new Error('invalid_attendance_transition'));

    renderAt('/proctor/sitting-rooms/100/attendance', <ProctorAttendancePage />, '/proctor/sitting-rooms/:examSittingRoomId/attendance');

    expect(await screen.findByText('SV001')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Check-in' }));
    const dialog = await screen.findByRole('alertdialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Xác nhận check-in' }));

    expect(await within(dialog).findByText('invalid_attendance_transition')).toBeInTheDocument();
    expect(screen.queryByText('Đã check-in SV001.')).not.toBeInTheDocument();
    expect(mockedListProctorRoomAttendance).toHaveBeenCalledTimes(1);
  });

  test('duplicate manual check-in is guarded while request is pending', async () => {
    mockedCheckInAssignment.mockReturnValueOnce(new Promise(() => {}));

    renderAt('/proctor/sitting-rooms/100/attendance', <ProctorAttendancePage />, '/proctor/sitting-rooms/:examSittingRoomId/attendance');

    expect(await screen.findByText('SV001')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Check-in' }));
    const dialog = await screen.findByRole('alertdialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Xác nhận check-in' }));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Đang gửi...' }));

    expect(mockedCheckInAssignment).toHaveBeenCalledTimes(1);
  });

  test('unsupported actions are hidden for checked-in candidates', async () => {
    mockedListProctorRoomAttendance.mockResolvedValueOnce({
      ...attendanceResponse(),
      items: [
        {
          ...attendanceResponse().items[0],
          assignment_status: 'CHECKED_IN',
          station_assignment_status: 'CHECKED_IN',
        },
      ],
    });

    renderAt('/proctor/sitting-rooms/100/attendance', <ProctorAttendancePage />, '/proctor/sitting-rooms/:examSittingRoomId/attendance');

    expect(await screen.findByText('SV001')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Check-in' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Đánh dấu vắng' })).not.toBeInTheDocument();
  });

  test('mark absent success refreshes attendance list', async () => {
    renderAt('/proctor/sitting-rooms/100/attendance', <ProctorAttendancePage />, '/proctor/sitting-rooms/:examSittingRoomId/attendance');

    expect(await screen.findByText('SV001')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Đánh dấu vắng' }));
    const dialog = await screen.findByRole('alertdialog');
    fireEvent.change(within(dialog).getByLabelText('Ghi chú bắt buộc'), { target: { value: 'Vắng thi' } });
    fireEvent.change(within(dialog).getByLabelText('Mã lý do'), { target: { value: 'NO_SHOW' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Xác nhận vắng' }));

    expect(await screen.findByText('Đã đánh dấu vắng SV001.')).toBeInTheDocument();
    await waitFor(() => expect(mockedMarkAssignmentAbsent).toHaveBeenCalledWith(100, 555, { note: 'Vắng thi', reason_code: 'NO_SHOW' }));
  });

  test('verify identity success refreshes attendance list', async () => {
    renderAt('/proctor/sitting-rooms/100/attendance', <ProctorAttendancePage />, '/proctor/sitting-rooms/:examSittingRoomId/attendance');

    expect(await screen.findByText('SV001')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Xác minh danh tính' }));
    const dialog = await screen.findByRole('alertdialog');
    fireEvent.change(within(dialog).getByLabelText('Trạng thái xác minh'), { target: { value: 'REJECTED' } });
    fireEvent.change(within(dialog).getByLabelText('Phương thức xác minh'), { target: { value: 'MANUAL' } });
    fireEvent.change(within(dialog).getByLabelText('Ghi chú'), { target: { value: 'Không khớp' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Lưu xác minh' }));

    expect(await screen.findByText('Đã lưu xác minh danh tính cho SV001.')).toBeInTheDocument();
    await waitFor(() => expect(mockedVerifyAssignmentIdentity).toHaveBeenCalledWith(100, 555, {
      verification_status: 'REJECTED',
      verification_method: 'MANUAL',
      note: 'Không khớp',
    }));
  });

  test('scanner success refreshes list, clears input, and never renders raw scan value', async () => {
    localStorageSetItemSpy = vi.spyOn(window.localStorage.__proto__, 'setItem');
    sessionStorageSetItemSpy = vi.spyOn(window.sessionStorage.__proto__, 'setItem');

    renderAt('/proctor/sitting-rooms/100/attendance', <ProctorAttendancePage />, '/proctor/sitting-rooms/:examSittingRoomId/attendance');

    const scanInput = await screen.findByLabelText('Dữ liệu scan');
    fireEvent.change(scanInput, { target: { value: 'RAW-SCAN-ABC-999' } });
    fireEvent.click(screen.getByRole('button', { name: 'Scan check-in' }));

    expect(await screen.findByText('Scan thành công: SV001 - Nguyễn A.')).toBeInTheDocument();
    await waitFor(() => expect(mockedScanCheckInAttendance).toHaveBeenCalledWith(100, {
      checkin_method: 'BARCODE',
      scan_value: 'RAW-SCAN-ABC-999',
      scan_device_id: null,
    }));
    expect(screen.getByLabelText('Dữ liệu scan')).toHaveValue('');
    expect(screen.queryByText('RAW-SCAN-ABC-999')).not.toBeInTheDocument();
    expect(screen.getByText('Scan thành công: SV001 - Nguyễn A.')).toBeInTheDocument();
    expect(localStorageSetItemSpy).not.toHaveBeenCalled();
    expect(sessionStorageSetItemSpy).not.toHaveBeenCalled();
    await waitFor(() => expect(mockedListProctorRoomAttendance).toHaveBeenCalledTimes(2));
  });

  test('scanner failure shows backend error, clears input, and does not fake success', async () => {
    mockedScanCheckInAttendance.mockRejectedValueOnce(new Error('scan_checkin_no_match'));

    renderAt('/proctor/sitting-rooms/100/attendance', <ProctorAttendancePage />, '/proctor/sitting-rooms/:examSittingRoomId/attendance');

    const scanInput = await screen.findByLabelText('Dữ liệu scan');
    fireEvent.change(scanInput, { target: { value: 'RAW-QR-CCCD-PAYLOAD' } });
    fireEvent.click(screen.getByRole('button', { name: 'Scan check-in' }));

    expect(await screen.findByText('scan_checkin_no_match')).toBeInTheDocument();
    expect(screen.getByLabelText('Dữ liệu scan')).toHaveValue('');
    expect(screen.queryByText('RAW-QR-CCCD-PAYLOAD')).not.toBeInTheDocument();
    expect(screen.queryByText(/Scan thành công/i)).not.toBeInTheDocument();
  });

  test('attendance page hides revoke action when student id is missing', async () => {
    mockedListProctorRoomAttendance.mockResolvedValueOnce({
      ...attendanceResponse(),
      items: [{ ...attendanceResponse().items[0], student_id: Number.NaN }],
    });

    renderAt('/proctor/sitting-rooms/100/attendance', <ProctorAttendancePage />, '/proctor/sitting-rooms/:examSittingRoomId/attendance');

    expect(await screen.findByText('SV001')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Thu hồi đăng nhập bị kẹt' })).not.toBeInTheDocument();
  });

  test('revoke dialog cancel does not call API', async () => {
    renderAt('/proctor/sitting-rooms/100/attendance', <ProctorAttendancePage />, '/proctor/sitting-rooms/:examSittingRoomId/attendance');

    expect(await screen.findByText('SV001')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Thu hồi đăng nhập bị kẹt' }));

    const dialog = await screen.findByRole('alertdialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Hủy' }));

    expect(mockedRevokeStudentStaleSession).not.toHaveBeenCalled();
  });

  test('revoke dialog confirms once and guards duplicate clicks while loading', async () => {
    mockedRevokeStudentStaleSession.mockReturnValueOnce(new Promise(() => {}));

    renderAt('/proctor/sitting-rooms/100/attendance', <ProctorAttendancePage />, '/proctor/sitting-rooms/:examSittingRoomId/attendance');

    expect(await screen.findByText('SV001')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Thu hồi đăng nhập bị kẹt' }));

    const dialog = await screen.findByRole('alertdialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Thu hồi phiên' }));
    expect(within(dialog).getByRole('button', { name: 'Đang thu hồi...' })).toBeDisabled();
    expect(mockedRevokeStudentStaleSession).toHaveBeenCalledTimes(1);
  });

  test('revoke dialog shows success state, disables confirm, and refreshes attendance once after revoked result', async () => {
    renderAt('/proctor/sitting-rooms/100/attendance', <ProctorAttendancePage />, '/proctor/sitting-rooms/:examSittingRoomId/attendance');

    expect(await screen.findByText('SV001')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Thu hồi đăng nhập bị kẹt' }));

    const dialog = await screen.findByRole('alertdialog');
    expect(within(dialog).getByText('SV001')).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Thu hồi phiên' }));

    expect(await within(dialog).findByText('Đã thu hồi phiên đăng nhập bị kẹt.')).toBeInTheDocument();
    await waitFor(() => expect(mockedRevokeStudentStaleSession).toHaveBeenCalledWith(100, 1001));
    await waitFor(() => expect(mockedListProctorRoomAttendance).toHaveBeenCalledTimes(2));
  });

  test('revoke dialog shows backend failure and allows retry without false success', async () => {
    mockedRevokeStudentStaleSession.mockRejectedValueOnce(new Error('Thu hồi thất bại')).mockResolvedValueOnce({ status: 'revoked' });

    renderAt('/proctor/sitting-rooms/100/attendance', <ProctorAttendancePage />, '/proctor/sitting-rooms/:examSittingRoomId/attendance');

    expect(await screen.findByText('SV001')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Thu hồi đăng nhập bị kẹt' }));

    const dialog = await screen.findByRole('alertdialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Thu hồi phiên' }));

    expect(await within(dialog).findByText('Thu hồi thất bại')).toBeInTheDocument();
    expect(within(dialog).queryByText('Đã thu hồi phiên đăng nhập bị kẹt.')).not.toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole('button', { name: 'Thu hồi phiên' }));
    expect(await within(dialog).findByText('Đã thu hồi phiên đăng nhập bị kẹt.')).toBeInTheDocument();
    expect(mockedRevokeStudentStaleSession).toHaveBeenCalledTimes(2);
  });

  test('live page uses roster fields and does not claim websocket or sse realtime', async () => {
    const setIntervalSpy = vi.spyOn(window, 'setInterval');
    renderAt('/proctor/sitting-rooms/100/live', <ProctorLivePage />, '/proctor/sitting-rooms/:examSittingRoomId/live');

    expect(await screen.findByTestId('proctor-live-page')).toBeInTheDocument();
    expect(screen.getByRole('table')).toHaveClass('table-compact');
    expect(screen.getByText('SV001')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Theo dõi phòng thi' })).toBeInTheDocument();
    expect(screen.getByText(/Theo dõi theo lượt cập nhật, chưa dùng WebSocket\/SSE/i)).toBeInTheDocument();
    expect(screen.getByText(/Tự động làm mới mỗi 15 giây/i)).toBeInTheDocument();
    expect(setIntervalSpy).toHaveBeenCalledWith(expect.any(Function), 15000);

    fireEvent.click(screen.getByRole('button', { name: 'Làm mới thủ công' }));
    await waitFor(() => expect(mockedGetProctorRoomRoster).toHaveBeenCalledTimes(2));
    expect(screen.queryByText(/Live monitor|Revoke stuck login/i)).not.toBeInTheDocument();
    setIntervalSpy.mockRestore();
  });

  test('live page rejects invalid route params without calling backend or starting polling', async () => {
    const setIntervalSpy = vi.spyOn(window, 'setInterval');

    renderAt('/proctor/sitting-rooms/-1/live', <ProctorLivePage />, '/proctor/sitting-rooms/:examSittingRoomId/live');

    expect(await screen.findByText(invalidRoomMessage)).toBeInTheDocument();
    expect(mockedGetProctorRoomRoster).not.toHaveBeenCalled();
    expect(setIntervalSpy).not.toHaveBeenCalledWith(expect.any(Function), 15000);
    setIntervalSpy.mockRestore();
  });

  test('live page cleans up polling interval on unmount', async () => {
    const clearIntervalSpy = vi.spyOn(window, 'clearInterval');
    const rendered = renderAt('/proctor/sitting-rooms/100/live', <ProctorLivePage />, '/proctor/sitting-rooms/:examSittingRoomId/live');

    expect(await screen.findByTestId('proctor-live-page')).toBeInTheDocument();
    rendered.unmount();

    expect(clearIntervalSpy).toHaveBeenCalled();
    clearIntervalSpy.mockRestore();
  });

  test('live page stops polling when all candidates are already in terminal submission states', async () => {
    const clearIntervalSpy = vi.spyOn(window, 'clearInterval');
    mockedGetProctorRoomRoster.mockResolvedValue({
      ...rosterResponse(),
      items: [
        {
          ...rosterResponse().items[0],
          submission_status: 'SEALED',
          submitted_at: '2026-05-21T09:50:00+07:00',
          session_status: 'COMPLETED',
        },
      ],
    });

    renderAt('/proctor/sitting-rooms/100/live', <ProctorLivePage />, '/proctor/sitting-rooms/:examSittingRoomId/live');

    expect(await screen.findByText(/Đã dừng tự động làm mới vì tất cả thí sinh đã ở trạng thái kết thúc/i)).toBeInTheDocument();
    await waitFor(() => expect(clearIntervalSpy).toHaveBeenCalled());
    clearIntervalSpy.mockRestore();
  });

  test('live page keeps polling semantics active on empty roster', async () => {
    mockedGetProctorRoomRoster.mockResolvedValueOnce({
      exam_sitting_id: 10,
      exam_sitting_room_id: 100,
      room_code: 'D13',
      items: [],
    });

    renderAt('/proctor/sitting-rooms/100/live', <ProctorLivePage />, '/proctor/sitting-rooms/:examSittingRoomId/live');

    expect(await screen.findByText('Không có dữ liệu session/submission cho phòng thi này.')).toBeInTheDocument();
    expect(screen.getByText(/Tự động làm mới mỗi 15 giây/i)).toBeInTheDocument();
    expect(screen.queryByText(/Đã dừng tự động làm mới/i)).not.toBeInTheDocument();
  });

  test('incidents page rejects invalid route params without rendering the form or calling backend', async () => {
    renderAt('/proctor/sitting-rooms/0/incidents', <ProctorIncidentsPage />, '/proctor/sitting-rooms/:examSittingRoomId/incidents');

    expect(await screen.findByText(invalidRoomMessage)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Ghi nhận sự cố' })).not.toBeInTheDocument();
    expect(mockedCreateProctorIncident).not.toHaveBeenCalled();
    expect(mockedListProctorRoomIncidents).not.toHaveBeenCalled();
  });

  test('incidents page shows initial loading state before first successful list load', async () => {
    let resolveIncidents: ((value: ReturnType<typeof incidentListResponse>) => void) | null = null;
    mockedListProctorRoomIncidents.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveIncidents = resolve;
      })
    );

    renderAt('/proctor/sitting-rooms/100/incidents', <ProctorIncidentsPage />, '/proctor/sitting-rooms/:examSittingRoomId/incidents');

    expect(screen.getByText('Đang tải danh sách sự cố...')).toBeInTheDocument();
    expect(screen.queryByText('Mất mạng')).not.toBeInTheDocument();

    resolveIncidents?.(incidentListResponse());

    expect(await screen.findByText('Lịch sử sự cố phòng thi')).toBeInTheDocument();
    expect(await screen.findByText('Mất mạng')).toBeInTheDocument();
  });

  test('incidents page renders only allowed OPEN actions and no unsafe controls', async () => {
    renderAt('/proctor/sitting-rooms/100/incidents', <ProctorIncidentsPage />, '/proctor/sitting-rooms/:examSittingRoomId/incidents');

    expect(await screen.findByText('Lịch sử sự cố phòng thi')).toBeInTheDocument();
    expect(screen.getByText('Lỗi thiết bị')).toBeInTheDocument();
    expect(screen.getByText('Mất mạng')).toBeInTheDocument();
    expect(screen.getByText('Mã phân công')).toBeInTheDocument();
    expect(screen.getByText('Mã trạm')).toBeInTheDocument();
    expect(screen.getByText('Mã thiết bị')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Đánh dấu đang xử lý' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Đánh dấu đã xử lý' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /void|vô hiệu/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('combobox', { name: 'Trạng thái' })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/metadata/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/dòng thời gian/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Close Room|Khóa phòng/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/điểm danh|check-in/i)).not.toBeInTheDocument();
  });

  test('incidents page shows only resolved action for IN_PROGRESS incidents', async () => {
    mockedListProctorRoomIncidents.mockResolvedValueOnce([
      incident({ incident_status: 'IN_PROGRESS', updated_by: 9, updated_at: '2026-05-21T10:06:00Z' }),
    ]);

    renderAt('/proctor/sitting-rooms/100/incidents', <ProctorIncidentsPage />, '/proctor/sitting-rooms/:examSittingRoomId/incidents');

    expect(await screen.findByText('Lịch sử sự cố phòng thi')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Đánh dấu đang xử lý' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Đánh dấu đã xử lý' })).toBeInTheDocument();
  });

  test('resolved incidents are read-only and display audit fields', async () => {
    mockedListProctorRoomIncidents.mockResolvedValueOnce([
      incident({
        incident_status: 'RESOLVED',
        resolved_by: 21,
        resolved_at: '2026-05-21T10:05:00Z',
        updated_by: 21,
        updated_at: '2026-05-21T10:05:00Z',
        resolution_note: 'Đã thay modem',
      }),
    ]);

    renderAt('/proctor/sitting-rooms/100/incidents', <ProctorIncidentsPage />, '/proctor/sitting-rooms/:examSittingRoomId/incidents');

    expect(await screen.findByText('Ghi chú xử lý:')).toBeInTheDocument();
    expect(screen.getByText('Đã thay modem')).toBeInTheDocument();
    expect(screen.getByText('Thời điểm xử lý')).toBeInTheDocument();
    expect(screen.getByText('Thời điểm cập nhật')).toBeInTheDocument();
    expect(screen.getByText('ID người cập nhật')).toBeInTheDocument();
    expect(screen.getByText('ID người xử lý')).toBeInTheDocument();
    expect(screen.getByText('Sự cố đang ở trạng thái cuối, chỉ có thể xem.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Đánh dấu đang xử lý' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Đánh dấu đã xử lý' })).not.toBeInTheDocument();
  });

  test('voided incidents are read-only with no update actions', async () => {
    mockedListProctorRoomIncidents.mockResolvedValueOnce([
      incident({ incident_status: 'VOIDED', updated_by: 3, updated_at: '2026-05-21T10:07:00Z' }),
    ]);

    renderAt('/proctor/sitting-rooms/100/incidents', <ProctorIncidentsPage />, '/proctor/sitting-rooms/:examSittingRoomId/incidents');

    expect(await screen.findByText('Đã vô hiệu')).toBeInTheDocument();
    expect(screen.getByText('Sự cố đang ở trạng thái cuối, chỉ có thể xem.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Đánh dấu đang xử lý' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Đánh dấu đã xử lý' })).not.toBeInTheDocument();
  });

  test('incidents page shows empty state when backend returns no incidents', async () => {
    mockedListProctorRoomIncidents.mockResolvedValueOnce([]);

    renderAt('/proctor/sitting-rooms/100/incidents', <ProctorIncidentsPage />, '/proctor/sitting-rooms/:examSittingRoomId/incidents');

    expect(await screen.findByText('Chưa có sự cố nào được ghi nhận')).toBeInTheDocument();
  });

  test('incidents page shows list error and retries', async () => {
    mockedListProctorRoomIncidents.mockRejectedValueOnce(new Error('Không tải được danh sách sự cố'));

    renderAt('/proctor/sitting-rooms/100/incidents', <ProctorIncidentsPage />, '/proctor/sitting-rooms/:examSittingRoomId/incidents');

    expect(await screen.findByRole('heading', { name: 'Không tải được danh sách sự cố' })).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: 'Thử tải lại' })[0]);

    await waitFor(() => expect(mockedListProctorRoomIncidents).toHaveBeenCalledTimes(2));
    expect(await screen.findByText('Mất mạng')).toBeInTheDocument();
  });

  test.each([
    ['0'],
    ['-3'],
    ['1.5'],
    ['abc'],
  ])('incidents page rejects invalid optional assignment id %s without calling backend', async (invalidValue) => {
    renderAt('/proctor/sitting-rooms/100/incidents', <ProctorIncidentsPage />, '/proctor/sitting-rooms/:examSittingRoomId/incidents');

    fireEvent.change(screen.getByLabelText(/Mã phân công/), { target: { value: invalidValue } });
    fireEvent.click(screen.getByRole('button', { name: 'Ghi nhận sự cố' }));

    expect(await screen.findByText('Mã phân công phải là số nguyên dương lớn hơn 0.')).toBeInTheDocument();
    expect(mockedCreateProctorIncident).not.toHaveBeenCalled();
    expect(screen.queryByText('Sự cố vừa tạo')).not.toBeInTheDocument();
  });

  test('incidents page omits empty optional ids from payload', async () => {
    renderAt('/proctor/sitting-rooms/100/incidents', <ProctorIncidentsPage />, '/proctor/sitting-rooms/:examSittingRoomId/incidents');

    fireEvent.change(screen.getByLabelText('Mô tả'), { target: { value: 'Mất mạng' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ghi nhận sự cố' }));

    await waitFor(() => expect(mockedCreateProctorIncident).toHaveBeenCalledTimes(1));
    const payload = mockedCreateProctorIncident.mock.calls[0][1] as Record<string, unknown>;
    expect(payload).not.toHaveProperty('exam_assignment_id');
    expect(payload).not.toHaveProperty('station_id');
    expect(payload).not.toHaveProperty('device_id');
  });

  test('incidents page submits trimmed valid positive optional ids', async () => {
    renderAt('/proctor/sitting-rooms/100/incidents', <ProctorIncidentsPage />, '/proctor/sitting-rooms/:examSittingRoomId/incidents');

    fireEvent.change(screen.getByLabelText(/Mã phân công/), { target: { value: ' 7 ' } });
    fireEvent.change(screen.getByLabelText('Mô tả'), { target: { value: 'Mất mạng' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ghi nhận sự cố' }));

    await waitFor(() => expect(mockedCreateProctorIncident).toHaveBeenCalledTimes(1));
    expect(mockedCreateProctorIncident).toHaveBeenCalledWith(
      100,
      expect.objectContaining({
        incident_type: 'DEVICE_FAILURE',
        description: 'Mất mạng',
        exam_assignment_id: 7,
      })
    );
  });

  test('incidents page creates incidents and guards duplicate submits', async () => {
    let resolveCreate: ((value: unknown) => void) | null = null;
    mockedCreateProctorIncident.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveCreate = resolve;
      })
    );

    renderAt('/proctor/sitting-rooms/100/incidents', <ProctorIncidentsPage />, '/proctor/sitting-rooms/:examSittingRoomId/incidents');

  expect(await screen.findByText('Mất mạng')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Mô tả'), { target: { value: 'Mất mạng' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ghi nhận sự cố' }));
    fireEvent.click(screen.getByRole('button', { name: 'Đang gửi...' }));

    expect(mockedCreateProctorIncident).toHaveBeenCalledTimes(1);

    resolveCreate?.({
      ...incident(),
      exam_assignment_id: null,
      station_id: null,
      device_id: null,
    });

    expect(await screen.findByText('Sự cố vừa tạo')).toBeInTheDocument();
    expect(screen.getAllByText('Lỗi thiết bị').length).toBeGreaterThan(0);
    await waitFor(() => expect(mockedListProctorRoomIncidents).toHaveBeenCalledTimes(2));
    expect(screen.getByText('Lịch sử sự cố phòng thi')).toBeInTheDocument();
    expect(screen.queryByText(/timeline|dòng thời gian/i)).not.toBeInTheDocument();
  });

  test('incidents page shows backend failure without faking success', async () => {
    mockedCreateProctorIncident.mockRejectedValueOnce(new Error('Create failed'));

    renderAt('/proctor/sitting-rooms/100/incidents', <ProctorIncidentsPage />, '/proctor/sitting-rooms/:examSittingRoomId/incidents');

    fireEvent.change(screen.getByLabelText('Mô tả'), { target: { value: 'Mất mạng' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ghi nhận sự cố' }));

    expect(await screen.findByText('Create failed')).toBeInTheDocument();
    expect(screen.queryByText('Đã ghi nhận sự cố từ backend.')).not.toBeInTheDocument();
  });

  test('incidents page keeps create success visible and shows list refresh error honestly when refresh fails', async () => {
    mockedListProctorRoomIncidents.mockResolvedValueOnce([]).mockRejectedValueOnce(new Error('Refresh failed'));
    mockedCreateProctorIncident.mockResolvedValueOnce(
      incident({
        incident_id: 2,
        exam_assignment_id: null,
        station_id: null,
        device_id: null,
        description: 'Mất điện',
        reported_at: '2026-05-21T10:05:00Z',
      })
    );

    renderAt('/proctor/sitting-rooms/100/incidents', <ProctorIncidentsPage />, '/proctor/sitting-rooms/:examSittingRoomId/incidents');

    expect(await screen.findByText('Chưa có sự cố nào được ghi nhận')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Mô tả'), { target: { value: 'Mất điện' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ghi nhận sự cố' }));

    expect(await screen.findByText('Sự cố vừa tạo')).toBeInTheDocument();
    expect(await screen.findByText('Refresh failed')).toBeInTheDocument();
    expect(screen.getByText('Mất điện')).toBeInTheDocument();
  });

  test('unknown incident statuses remain read-only with safe fallback labels', async () => {
    mockedListProctorRoomIncidents.mockResolvedValueOnce([
      incident({
        incident_id: 3,
        exam_assignment_id: null,
        station_id: null,
        device_id: null,
        incident_type: 'MYSTERY_INCIDENT',
        incident_status: 'PENDING_TRIAGE',
        reported_by: null,
        description: 'Chưa rõ',
      }),
    ]);

    renderAt('/proctor/sitting-rooms/100/incidents', <ProctorIncidentsPage />, '/proctor/sitting-rooms/:examSittingRoomId/incidents');

    expect(await screen.findByText('Không xác định: MYSTERY_INCIDENT')).toBeInTheDocument();
    expect(screen.getByText('Không xác định: PENDING_TRIAGE')).toBeInTheDocument();
    expect(screen.getByText('Trạng thái này chưa hỗ trợ cập nhật từ giao diện giám thị.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Đánh dấu đang xử lý' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Đánh dấu đã xử lý' })).not.toBeInTheDocument();
  });

  test('in-progress confirmation dialog cancels without calling PATCH', async () => {
    renderAt('/proctor/sitting-rooms/100/incidents', <ProctorIncidentsPage />, '/proctor/sitting-rooms/:examSittingRoomId/incidents');

    expect(await screen.findByRole('button', { name: 'Đánh dấu đang xử lý' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Đánh dấu đang xử lý' }));

    const dialog = await screen.findByRole('alertdialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Hủy' }));

    expect(mockedUpdateProctorIncident).not.toHaveBeenCalled();
  });

  test('in-progress confirmation calls PATCH and refreshes the list', async () => {
    mockedListProctorRoomIncidents
      .mockResolvedValueOnce([incident()])
      .mockResolvedValueOnce([incident({ incident_status: 'IN_PROGRESS', updated_by: 2, updated_at: '2026-05-21T10:06:00Z' })]);

    renderAt('/proctor/sitting-rooms/100/incidents', <ProctorIncidentsPage />, '/proctor/sitting-rooms/:examSittingRoomId/incidents');

    fireEvent.click(await screen.findByRole('button', { name: 'Đánh dấu đang xử lý' }));

    const dialog = await screen.findByRole('alertdialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Xác nhận đang xử lý' }));

    await waitFor(() => expect(mockedUpdateProctorIncident).toHaveBeenCalledWith(1, { incident_status: 'IN_PROGRESS' }));
    await waitFor(() => expect(mockedListProctorRoomIncidents).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Đánh dấu đang xử lý' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Đánh dấu đã xử lý' })).toBeInTheDocument();
  });

  test('in-progress update guards duplicate submit while loading', async () => {
    mockedUpdateProctorIncident.mockReturnValueOnce(new Promise(() => {}));

    renderAt('/proctor/sitting-rooms/100/incidents', <ProctorIncidentsPage />, '/proctor/sitting-rooms/:examSittingRoomId/incidents');

    fireEvent.click(await screen.findByRole('button', { name: 'Đánh dấu đang xử lý' }));

    const dialog = await screen.findByRole('alertdialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Xác nhận đang xử lý' }));
    expect(within(dialog).getByRole('button', { name: 'Đang cập nhật...' })).toBeDisabled();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Đang cập nhật...' }));

    expect(mockedUpdateProctorIncident).toHaveBeenCalledTimes(1);
  });

  test('in-progress update shows backend error honestly', async () => {
    mockedUpdateProctorIncident.mockRejectedValueOnce(new Error('Patch failed'));

    renderAt('/proctor/sitting-rooms/100/incidents', <ProctorIncidentsPage />, '/proctor/sitting-rooms/:examSittingRoomId/incidents');

    fireEvent.click(await screen.findByRole('button', { name: 'Đánh dấu đang xử lý' }));

    const dialog = await screen.findByRole('alertdialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Xác nhận đang xử lý' }));

    expect(await within(dialog).findByText('Patch failed')).toBeInTheDocument();
    expect(mockedListProctorRoomIncidents).toHaveBeenCalledTimes(1);
  });

  test('resolve dialog requires non-empty resolution note', async () => {
    renderAt('/proctor/sitting-rooms/100/incidents', <ProctorIncidentsPage />, '/proctor/sitting-rooms/:examSittingRoomId/incidents');

    fireEvent.click(await screen.findByRole('button', { name: 'Đánh dấu đã xử lý' }));

    const dialog = await screen.findByRole('alertdialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Xác nhận đã xử lý' }));

    expect(await within(dialog).findByText('Vui lòng nhập ghi chú xử lý.')).toBeInTheDocument();
    expect(mockedUpdateProctorIncident).not.toHaveBeenCalled();
  });

  test('resolve dialog submits trimmed resolution_note and refreshes terminal state', async () => {
    mockedListProctorRoomIncidents
      .mockResolvedValueOnce([incident()])
      .mockResolvedValueOnce([
        incident({
          incident_status: 'RESOLVED',
          resolved_by: 2,
          resolved_at: '2026-05-21T10:08:00Z',
          updated_by: 2,
          updated_at: '2026-05-21T10:08:00Z',
          resolution_note: 'Đã khởi động lại modem',
        }),
      ]);

    renderAt('/proctor/sitting-rooms/100/incidents', <ProctorIncidentsPage />, '/proctor/sitting-rooms/:examSittingRoomId/incidents');

    fireEvent.click(await screen.findByRole('button', { name: 'Đánh dấu đã xử lý' }));

    const dialog = await screen.findByRole('alertdialog');
    fireEvent.change(within(dialog).getByLabelText('Ghi chú xử lý'), { target: { value: '  Đã khởi động lại modem  ' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Xác nhận đã xử lý' }));

    await waitFor(() =>
      expect(mockedUpdateProctorIncident).toHaveBeenCalledWith(1, {
        incident_status: 'RESOLVED',
        resolution_note: 'Đã khởi động lại modem',
      })
    );
    await waitFor(() => expect(mockedListProctorRoomIncidents).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    expect(screen.getByText('Đã khởi động lại modem')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Đánh dấu đang xử lý' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Đánh dấu đã xử lý' })).not.toBeInTheDocument();
  });

  test('resolve dialog guards duplicate submit while loading', async () => {
    mockedUpdateProctorIncident.mockReturnValueOnce(new Promise(() => {}));

    renderAt('/proctor/sitting-rooms/100/incidents', <ProctorIncidentsPage />, '/proctor/sitting-rooms/:examSittingRoomId/incidents');

    fireEvent.click(await screen.findByRole('button', { name: 'Đánh dấu đã xử lý' }));

    const dialog = await screen.findByRole('alertdialog');
    fireEvent.change(within(dialog).getByLabelText('Ghi chú xử lý'), { target: { value: 'Đã thay dây nguồn' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Xác nhận đã xử lý' }));
    expect(within(dialog).getByRole('button', { name: 'Đang cập nhật...' })).toBeDisabled();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Đang cập nhật...' }));

    expect(mockedUpdateProctorIncident).toHaveBeenCalledTimes(1);
  });

  test('resolve dialog shows backend error honestly', async () => {
    mockedUpdateProctorIncident.mockRejectedValueOnce(new Error('Resolve failed'));

    renderAt('/proctor/sitting-rooms/100/incidents', <ProctorIncidentsPage />, '/proctor/sitting-rooms/:examSittingRoomId/incidents');

    fireEvent.click(await screen.findByRole('button', { name: 'Đánh dấu đã xử lý' }));

    const dialog = await screen.findByRole('alertdialog');
    fireEvent.change(within(dialog).getByLabelText('Ghi chú xử lý'), { target: { value: 'Đã thay dây nguồn' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Xác nhận đã xử lý' }));

    expect(await within(dialog).findByText('Resolve failed')).toBeInTheDocument();
    expect(mockedListProctorRoomIncidents).toHaveBeenCalledTimes(1);
  });
});

describe('proctor incident display helpers', () => {
  test('incident transitions match backend MVP policy for proctors', () => {
    expect(getAllowedProctorIncidentTransitions('OPEN')).toEqual(['IN_PROGRESS', 'RESOLVED']);
    expect(getAllowedProctorIncidentTransitions('IN_PROGRESS')).toEqual(['RESOLVED']);
    expect(getAllowedProctorIncidentTransitions('RESOLVED')).toEqual([]);
    expect(getAllowedProctorIncidentTransitions('VOIDED')).toEqual([]);
    expect(getAllowedProctorIncidentTransitions('CLOSED')).toEqual([]);
    expect(getAllowedProctorIncidentTransitions(undefined)).toEqual([]);
  });

  test('resolve and terminal helpers stay aligned with backend policy', () => {
    expect(canProctorResolveIncident('OPEN')).toBe(true);
    expect(canProctorResolveIncident('IN_PROGRESS')).toBe(true);
    expect(canProctorResolveIncident('RESOLVED')).toBe(false);
    expect(canProctorResolveIncident('VOIDED')).toBe(false);

    expect(isIncidentTerminal('RESOLVED')).toBe(true);
    expect(isIncidentTerminal('VOIDED')).toBe(true);
    expect(isIncidentTerminal('OPEN')).toBe(false);
    expect(isIncidentTerminal('UNKNOWN')).toBe(false);
  });

  test('resolution_note requirement only applies to allowed transitions into RESOLVED', () => {
    expect(requiresResolutionNoteForTransition('OPEN', 'RESOLVED')).toBe(true);
    expect(requiresResolutionNoteForTransition('IN_PROGRESS', 'RESOLVED')).toBe(true);
    expect(requiresResolutionNoteForTransition('RESOLVED', 'RESOLVED')).toBe(false);
    expect(requiresResolutionNoteForTransition('VOIDED', 'RESOLVED')).toBe(false);
    expect(requiresResolutionNoteForTransition('OPEN', 'IN_PROGRESS')).toBe(false);
    expect(requiresResolutionNoteForTransition('UNKNOWN', 'RESOLVED')).toBe(false);
  });

  test('incident status label keeps safe fallback for unknown statuses and labels VOIDED explicitly', () => {
    expect(incidentStatusLabel('VOIDED')).toBe('Đã vô hiệu');
    expect(incidentStatusLabel('CLOSED')).toBe('Không xác định: CLOSED');
    expect(incidentStatusLabel(undefined)).toBe('Không xác định');
  });
});
