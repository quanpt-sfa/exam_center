import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { ProctorDashboardPanel } from './ProctorDashboardPanel';
import { httpRequest } from '../../shared/api/httpClient';

vi.mock('../../shared/api/httpClient', () => ({ httpRequest: vi.fn() }));

const ok = <T,>(data: T) => ({ ok: true as const, success: true as const, data, error: null, message: null });
const err = (code: string, message: string) => ({ ok: false as const, success: false as const, data: null, error: { code, message, details: {} }, message: null });

function renderPanel(props?: { allowSessionRevoke?: boolean }) {
  render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <ProctorDashboardPanel {...props} />
    </MemoryRouter>
  );
}

describe('ProctorDashboardPanel', () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.clearAllMocks();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === '/proctor/my-sitting-rooms') {
        return ok({ items: [{ exam_sitting_id: 10, exam_sitting_room_id: 100, room_code: 'D13', sitting_code: 'S1' }] });
      }
      if (path === '/proctor/sitting-rooms/100/roster') {
        return ok({
          items: [
            {
              student_id: 10,
              station_code: 'A1',
              student_code: 'SV001',
              full_name: 'Nguyễn A',
              assignment_status: 'ASSIGNED',
              station_assignment_status: 'ASSIGNED',
              planned_device_asset_tag: 'PC-01',
              session_status: 'IN_PROGRESS',
              submission_status: 'IN_PROGRESS',
              started_at: '2026-05-16T08:00:00+07:00',
            },
            {
              student_id: 11,
              station_code: 'A2',
              student_code: 'SV002',
              full_name: 'Nguyễn B',
              assignment_status: 'ASSIGNED',
              station_assignment_status: 'ASSIGNED',
              planned_device_asset_tag: 'PC-02',
              session_status: 'READY_TO_START',
            },
            {
              student_id: 12,
              station_code: 'A3',
              student_code: 'SV003',
              full_name: 'Nguyễn C',
              assignment_status: 'ASSIGNED',
              station_assignment_status: 'ASSIGNED',
              planned_device_asset_tag: 'PC-03',
              session_status: 'IN_PROGRESS',
              submission_status: 'SUBMITTED',
              submitted_at: '2026-05-16T09:00:00+07:00',
            },
          ],
        });
      }
      if (path === '/proctor/sitting-rooms/100/readiness') {
        return ok({ items: [{ station_code: 'A1', asset_tag: 'PC-01', health_status: 'READY', mismatch: false }] });
      }
      if (path === '/proctor/sitting-rooms/100/incidents' && init?.method === 'POST') {
        return ok({ incident_id: 1 });
      }
      if (path === '/delivery/exam-sitting-rooms/100/students/10/revoke-stale-session' && init?.method === 'POST') {
        return ok({ status: 'revoked' });
      }
      if (path === '/delivery/exam-sitting-rooms/100/students/11/revoke-stale-session' && init?.method === 'POST') {
        return ok({ status: 'no_active_session' });
      }
      if (path === '/auth/logout' && init?.method === 'POST') {
        return ok({ status: 'OK' });
      }
      return ok({ items: [] });
    });
  });

  test('renders assigned rooms, roster, readiness, progress status, and logout control', async () => {
    renderPanel();
    expect(await screen.findByRole('heading', { name: 'Phòng được phân công' })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText('SV001')).toBeInTheDocument();
      expect(screen.getAllByText('A1').length).toBeGreaterThan(0);
      expect(screen.getByText('READY')).toBeInTheDocument();
    });

    expect(screen.getAllByText('Đang thi').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Đã thi').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Chưa thi').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: 'Thoát tài khoản' })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Thu hồi phiên đăng nhập kẹt' }).length).toBeGreaterThan(0);
  });

  test('incident form calls API', async () => {
    renderPanel();
    await screen.findByRole('heading', { name: 'Báo sự cố' });
    fireEvent.change(screen.getByLabelText('Mô tả'), { target: { value: 'Mất mạng' } });
    fireEvent.click(screen.getByRole('button', { name: 'Báo sự cố' }));
    await waitFor(() => {
      expect(vi.mocked(httpRequest)).toHaveBeenCalledWith(
        '/proctor/sitting-rooms/100/incidents',
        expect.objectContaining({ method: 'POST' })
      );
    });
  });

  test('revoke action requires confirmation before calling API', async () => {
    vi.mocked(window.confirm).mockReturnValue(false);

    renderPanel();
    await screen.findByText('SV001');
    fireEvent.click(screen.getAllByRole('button', { name: 'Thu hồi phiên đăng nhập kẹt' })[0]);

    expect(window.confirm).toHaveBeenCalledWith(
      'Thao tác này sẽ thu hồi phiên đăng nhập hiện tại của sinh viên. Sinh viên cần đăng nhập lại. Bạn có chắc chắn muốn tiếp tục?'
    );
    expect(vi.mocked(httpRequest)).not.toHaveBeenCalledWith(
      '/delivery/exam-sitting-rooms/100/students/10/revoke-stale-session',
      expect.objectContaining({ method: 'POST' })
    );
  });

  test('revoke action calls correct endpoint and shows revoked message', async () => {
    renderPanel();
    await screen.findByText('SV001');

    fireEvent.click(screen.getAllByRole('button', { name: 'Thu hồi phiên đăng nhập kẹt' })[0]);

    await waitFor(() => {
      expect(vi.mocked(httpRequest)).toHaveBeenCalledWith(
        '/delivery/exam-sitting-rooms/100/students/10/revoke-stale-session',
        expect.objectContaining({ method: 'POST' })
      );
    });
    expect(await screen.findByText('Đã thu hồi phiên đăng nhập. Sinh viên có thể đăng nhập lại.')).toBeInTheDocument();
  });

  test('revoke action shows no active session message safely', async () => {
    renderPanel();
    await screen.findByText('SV002');

    fireEvent.click(screen.getAllByRole('button', { name: 'Thu hồi phiên đăng nhập kẹt' })[1]);

    expect(await screen.findByText('Sinh viên hiện không có phiên đăng nhập đang hoạt động.')).toBeInTheDocument();
  });

  test('revoke action shows permission message on 403', async () => {
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === '/proctor/my-sitting-rooms') {
        return ok({ items: [{ exam_sitting_id: 10, exam_sitting_room_id: 100, room_code: 'D13', sitting_code: 'S1' }] });
      }
      if (path === '/proctor/sitting-rooms/100/roster') {
        return ok({
          items: [{ student_id: 10, station_code: 'A1', student_code: 'SV001', full_name: 'Nguyễn A', assignment_status: 'ASSIGNED', station_assignment_status: 'ASSIGNED' }],
        });
      }
      if (path === '/proctor/sitting-rooms/100/readiness') {
        return ok({ items: [] });
      }
      if (path === '/delivery/exam-sitting-rooms/100/students/10/revoke-stale-session' && init?.method === 'POST') {
        return err('permission_denied', 'forbidden');
      }
      return ok({ items: [] });
    });

    renderPanel();
    await screen.findByText('SV001');
    fireEvent.click(screen.getByRole('button', { name: 'Thu hồi phiên đăng nhập kẹt' }));

    expect(await screen.findByText('Bạn không có quyền thực hiện thao tác này.')).toBeInTheDocument();
  });

  test('revoke action shows generic error on network failure', async () => {
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === '/proctor/my-sitting-rooms') {
        return ok({ items: [{ exam_sitting_id: 10, exam_sitting_room_id: 100, room_code: 'D13', sitting_code: 'S1' }] });
      }
      if (path === '/proctor/sitting-rooms/100/roster') {
        return ok({
          items: [{ student_id: 10, station_code: 'A1', student_code: 'SV001', full_name: 'Nguyễn A', assignment_status: 'ASSIGNED', station_assignment_status: 'ASSIGNED' }],
        });
      }
      if (path === '/proctor/sitting-rooms/100/readiness') {
        return ok({ items: [] });
      }
      if (path === '/delivery/exam-sitting-rooms/100/students/10/revoke-stale-session' && init?.method === 'POST') {
        return err('network_error', 'Network request failed');
      }
      return ok({ items: [] });
    });

    renderPanel();
    await screen.findByText('SV001');
    fireEvent.click(screen.getByRole('button', { name: 'Thu hồi phiên đăng nhập kẹt' }));

    expect(await screen.findByText('Không thể thu hồi phiên đăng nhập lúc này. Vui lòng thử lại sau.')).toBeInTheDocument();
  });

  test('revoke action is not rendered for unauthorized context', async () => {
    renderPanel({ allowSessionRevoke: false });
    await screen.findByText('SV001');

    expect(screen.queryByRole('button', { name: 'Thu hồi phiên đăng nhập kẹt' })).not.toBeInTheDocument();
  });
});
