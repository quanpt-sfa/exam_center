import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { httpRequest } from '../../shared/api/httpClient';
import { FacilityPage } from '../facility/FacilityPage';
import { AcademicMasterDataPage } from './academic/AcademicMasterDataPage';
import { PeopleMasterDataPage } from './people/PeopleMasterDataPage';

vi.mock('../../shared/api/httpClient', () => ({
  httpRequest: vi.fn(),
}));

const mockedHttpRequest = vi.mocked(httpRequest);

function ok(data: unknown) {
  return { ok: true, success: true, data, error: null, message: null };
}

describe('Phase 3A master data workflow completeness', () => {
  beforeEach(() => {
    mockedHttpRequest.mockReset();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    mockedHttpRequest.mockImplementation((path, init) => {
      if (path === '/master-data/import-templates') {
        return Promise.resolve(ok({ items: [] }));
      }
      if (typeof path === 'string' && path.startsWith('/master-data/departments?')) {
        return Promise.resolve(
          ok({
            items: [{ department_id: 3, department_code: 'SFA', department_name: 'Khoa Tài chính', status: 'ACTIVE' }],
            pagination: { page: 1, page_size: 20, total: 30, total_pages: 2, has_next: true, has_previous: false },
          })
        );
      }
      if (typeof path === 'string' && path.startsWith('/master-data/programs?')) {
        return Promise.resolve(ok({ items: [] }));
      }
      if (typeof path === 'string' && path.startsWith('/master-data/courses?')) {
        return Promise.resolve(
          ok({
            items: [{ course_id: 5, department_id: 3, course_code: 'ACC101', course_name: 'Kế toán căn bản', status: 'ACTIVE' }],
            pagination: { page: 1, page_size: 20, total: 1, total_pages: 1, has_next: false, has_previous: false },
          })
        );
      }
      if (typeof path === 'string' && path.startsWith('/master-data/class-sections?')) {
        return Promise.resolve(ok({ items: [], pagination: { page: 1, page_size: 20, total: 0, total_pages: 0, has_next: false, has_previous: false } }));
      }
      if (typeof path === 'string' && path.startsWith('/master-data/enrollments?')) {
        return Promise.resolve(ok({ items: [], pagination: { page: 1, page_size: 20, total: 0, total_pages: 0, has_next: false, has_previous: false } }));
      }
      if (typeof path === 'string' && path.startsWith('/master-data/students?')) {
        return Promise.resolve(
          ok({
            items: [{ student_id: 12, full_name: 'Nguyễn Văn B', student_code: 'SV002', student_status: 'ACTIVE' }],
            pagination: { page: 1, page_size: 20, total: 1, total_pages: 1, has_next: false, has_previous: false },
          })
        );
      }
      if (typeof path === 'string' && path.startsWith('/master-data/instructors?')) {
        return Promise.resolve(ok({ items: [], pagination: { page: 1, page_size: 20, total: 0, total_pages: 0, has_next: false, has_previous: false } }));
      }
      if (typeof path === 'string' && path.startsWith('/master-data/rooms?')) {
        return Promise.resolve(
          ok({
            items: [{ room_id: 1, room_code: 'D13', room_name: 'Phòng D13', status: 'ACTIVE', room_type: 'LAB' }],
            pagination: { page: 1, page_size: 20, total: 1, total_pages: 1, has_next: false, has_previous: false },
          })
        );
      }
      if (typeof path === 'string' && path.startsWith('/master-data/rooms/1/stations?')) {
        return Promise.resolve(ok({ items: [{ station_id: 11, station_code: 'A1', status: 'ACTIVE' }] }));
      }
      if (path === '/master-data/rooms/1/station-readiness') {
        return Promise.resolve(ok({ items: [{ room_code: 'D13', station_code: 'A1', latest_health_status: 'READY' }] }));
      }
      if (typeof path === 'string' && path.startsWith('/master-data/devices?')) {
        return Promise.resolve(
          ok({
            items: [{ device_id: 7, asset_tag: 'PC-01', device_name: 'Máy 01', device_type: 'LAB_PC', status: 'ACTIVE' }],
            pagination: { page: 1, page_size: 20, total: 1, total_pages: 1, has_next: false, has_previous: false },
          })
        );
      }
      if (init?.method === 'PATCH' || init?.method === 'POST') {
        return Promise.resolve(ok({}));
      }
      return Promise.resolve(ok({ items: [] }));
    });
  });

  test('academic lists expose search, status, and pagination controls with canonical query params', async () => {
    render(<AcademicMasterDataPage />);

    await screen.findByRole('button', { name: 'Khoa / phòng ban' });
    fireEvent.change(screen.getByLabelText('Tìm kiếm'), { target: { value: 'tai chinh' } });
    fireEvent.change(screen.getAllByLabelText('Trạng thái')[0], { target: { value: 'ACTIVE' } });
    fireEvent.click(screen.getByRole('button', { name: 'Áp dụng' }));

    await waitFor(() => {
      const called = mockedHttpRequest.mock.calls.some(([path]) =>
        typeof path === 'string' &&
        path.includes('/master-data/departments?page=1&page_size=20') &&
        path.includes('query=tai+chinh') &&
        path.includes('status=ACTIVE')
      );
      expect(called).toBe(true);
    });

    fireEvent.click(screen.getByRole('button', { name: 'Sau' }));

    await waitFor(() => {
      const called = mockedHttpRequest.mock.calls.some(([path]) =>
        typeof path === 'string' &&
        path.includes('/master-data/departments?page=2&page_size=20') &&
        path.includes('query=tai+chinh') &&
        path.includes('status=ACTIVE')
      );
      expect(called).toBe(true);
    });
  });

  test('people page blocks invalid whitespace-only submits with field-level validation', async () => {
    render(<PeopleMasterDataPage />);

    fireEvent.change(await screen.findByLabelText('Họ tên'), { target: { value: '   ' } });
    fireEvent.change(screen.getByLabelText('Mã sinh viên'), { target: { value: '   ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Lưu' }));

    expect(await screen.findByText('Họ tên không được để trống.')).toBeInTheDocument();
    expect(screen.getByText('Mã sinh viên không được để trống.')).toBeInTheDocument();
    expect(mockedHttpRequest.mock.calls.some(([path, init]) => path === '/master-data/students' && init?.method === 'POST')).toBe(false);
  });

  test('academic page supports minimal edit workflow where PATCH exists', async () => {
    render(<AcademicMasterDataPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Môn học' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Sửa' }));

    expect(screen.getByRole('heading', { name: 'Cập nhật môn học' })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Tên môn'), { target: { value: 'Kế toán quản trị' } });
    fireEvent.click(screen.getByRole('button', { name: 'Cập nhật' }));

    await waitFor(() => {
      const called = mockedHttpRequest.mock.calls.some(
        ([path, init]) =>
          path === '/master-data/courses/5' &&
          init?.method === 'PATCH' &&
          init.body ===
            JSON.stringify({
              department_id: 3,
              course_code: 'ACC101',
              course_name: 'Kế toán quản trị',
              course_type: undefined,
              credit: undefined,
              status: 'ACTIVE',
            })
      );
      expect(called).toBe(true);
    });
  });

  test('facility page exposes deactivate action only where backend endpoint exists', async () => {
    render(<FacilityPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Thiết bị' }));
    await screen.findByText('PC-01');
    fireEvent.click(screen.getAllByRole('button', { name: 'Ngừng sử dụng' }).find((button) => button.closest('table')) as HTMLButtonElement);
    fireEvent.click(within(screen.getByRole('dialog', { name: 'Xác nhận ngưng sử dụng' })).getByRole('button', { name: 'Ngưng sử dụng' }));

    await waitFor(() => {
      const called = mockedHttpRequest.mock.calls.some(
        ([path, init]) =>
          path === '/master-data/devices/7/deactivate' &&
          init?.method === 'POST' &&
          init.body === JSON.stringify({ reason: 'Ngưng sử dụng từ giao diện quản trị.' })
      );
      expect(called).toBe(true);
    });
  });
});
