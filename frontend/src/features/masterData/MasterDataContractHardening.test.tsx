import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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

function fail(message: string, code = 'request_failed') {
  return { ok: false, success: false, data: null, error: { code, message }, message: null };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((innerResolve) => {
    resolve = innerResolve;
  });
  return { promise, resolve };
}

function installDefaultMasterDataMock(options?: {
  departmentList?: () => ReturnType<typeof ok> | ReturnType<typeof fail> | Promise<ReturnType<typeof ok> | ReturnType<typeof fail>>;
  courseList?: () => ReturnType<typeof ok> | ReturnType<typeof fail> | Promise<ReturnType<typeof ok> | ReturnType<typeof fail>>;
  classSectionList?: () => ReturnType<typeof ok> | ReturnType<typeof fail> | Promise<ReturnType<typeof ok> | ReturnType<typeof fail>>;
  studentList?: () => ReturnType<typeof ok> | ReturnType<typeof fail> | Promise<ReturnType<typeof ok> | ReturnType<typeof fail>>;
  deviceList?: () => ReturnType<typeof ok> | ReturnType<typeof fail> | Promise<ReturnType<typeof ok> | ReturnType<typeof fail>>;
  onMutation?: (path: string, init: RequestInit | undefined) => ReturnType<typeof ok> | ReturnType<typeof fail> | Promise<ReturnType<typeof ok> | ReturnType<typeof fail>>;
}) {
  mockedHttpRequest.mockImplementation((path, init) => {
    if (path === '/master-data/import-templates') {
      return Promise.resolve(ok({ items: [] }));
    }
    if (typeof path === 'string' && path.startsWith('/master-data/departments?')) {
      return Promise.resolve(
        options?.departmentList?.() ??
          ok({
            items: [{ department_id: 3, department_code: 'SFA', department_name: 'Khoa Tài chính', status: 'ACTIVE' }],
            pagination: { page: 1, page_size: 20, total: 30, total_pages: 2, has_next: true, has_previous: false },
          })
      );
    }
    if (typeof path === 'string' && path.startsWith('/master-data/programs?')) {
      return Promise.resolve(ok({ items: [], pagination: { page: 1, page_size: 20, total: 0, total_pages: 0, has_next: false, has_previous: false } }));
    }
    if (typeof path === 'string' && path.startsWith('/master-data/courses?')) {
      return Promise.resolve(
        options?.courseList?.() ??
          ok({
            items: [{ course_id: 5, department_id: 3, course_code: 'ACC101', course_name: 'Kế toán căn bản', status: 'ACTIVE' }],
            pagination: { page: 1, page_size: 20, total: 1, total_pages: 1, has_next: false, has_previous: false },
          })
      );
    }
    if (typeof path === 'string' && path.startsWith('/master-data/class-sections?')) {
      return Promise.resolve(
        options?.classSectionList?.() ??
          ok({ items: [], pagination: { page: 1, page_size: 20, total: 0, total_pages: 0, has_next: false, has_previous: false } })
      );
    }
    if (typeof path === 'string' && path.startsWith('/master-data/enrollments?')) {
      return Promise.resolve(ok({ items: [], pagination: { page: 1, page_size: 20, total: 0, total_pages: 0, has_next: false, has_previous: false } }));
    }
    if (typeof path === 'string' && path.startsWith('/master-data/students?')) {
      return Promise.resolve(
        options?.studentList?.() ??
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
      return Promise.resolve(ok({ items: [{ station_id: 11, station_code: 'A1', status: 'ACTIVE' }], pagination: { page: 1, page_size: 200, total: 1, total_pages: 1, has_next: false, has_previous: false } }));
    }
    if (path === '/master-data/rooms/1/station-readiness') {
      return Promise.resolve(ok({ items: [{ room_code: 'D13', station_code: 'A1', latest_health_status: 'READY' }] }));
    }
    if (typeof path === 'string' && path.startsWith('/master-data/devices?')) {
      return Promise.resolve(
        options?.deviceList?.() ??
          ok({
            items: [{ device_id: 7, asset_tag: 'PC-01', device_name: 'Máy 01', device_type: 'LAB_PC', status: 'ACTIVE' }],
            pagination: { page: 1, page_size: 20, total: 1, total_pages: 1, has_next: false, has_previous: false },
          })
      );
    }
    if (init?.method === 'POST' || init?.method === 'PATCH') {
      return Promise.resolve(options?.onMutation?.(String(path), init) ?? ok({}));
    }
    return Promise.resolve(ok({ items: [] }));
  });
}

describe('Phase 2A.5 master data contract and UX hardening', () => {
  beforeEach(() => {
    mockedHttpRequest.mockReset();
    vi.restoreAllMocks();
    installDefaultMasterDataMock();
  });

  test('prevents duplicate create submissions and keeps submit button in saving state', async () => {
    const createDeferred = deferred<ReturnType<typeof ok>>();
    installDefaultMasterDataMock({
      onMutation: (path, init) => {
        if (path === '/master-data/students' && init?.method === 'POST') {
          return createDeferred.promise;
        }
        return ok({});
      },
    });

    render(<PeopleMasterDataPage />);

    fireEvent.change(await screen.findByLabelText('Họ tên'), { target: { value: 'Nguyễn Văn B' } });
    fireEvent.change(screen.getByLabelText('Mã sinh viên'), { target: { value: 'SV002' } });
    const submitButton = screen.getByRole('button', { name: 'Lưu' });
    fireEvent.click(submitButton);
    fireEvent.click(submitButton);

    expect(mockedHttpRequest.mock.calls.filter(([path, init]) => path === '/master-data/students' && init?.method === 'POST')).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'Đang lưu...' })).toBeDisabled();

    createDeferred.resolve(ok({}));
    await waitFor(() => expect(screen.getByText('Đã lưu master data.')).toBeInTheDocument());
  });

  test('edit success pre-fills form, prevents duplicate PATCH, refreshes list, and exits edit mode', async () => {
    const patchDeferred = deferred<ReturnType<typeof ok>>();
    installDefaultMasterDataMock({
      onMutation: (path, init) => {
        if (path === '/master-data/courses/5' && init?.method === 'PATCH') {
          return patchDeferred.promise;
        }
        return ok({});
      },
    });

    render(<AcademicMasterDataPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Môn học' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Sửa' }));

    expect(screen.getByRole('heading', { name: 'Cập nhật môn học' })).toBeInTheDocument();
    expect(screen.getByLabelText('Mã môn')).toHaveValue('ACC101');
    expect(screen.getByLabelText('Tên môn')).toHaveValue('Kế toán căn bản');

    fireEvent.change(screen.getByLabelText('Tên môn'), { target: { value: 'Kế toán quản trị' } });
    const updateButton = screen.getByRole('button', { name: 'Cập nhật' });
    fireEvent.click(updateButton);
    fireEvent.click(updateButton);

    expect(mockedHttpRequest.mock.calls.filter(([path, init]) => path === '/master-data/courses/5' && init?.method === 'PATCH')).toHaveLength(1);

    patchDeferred.resolve(ok({}));

    await waitFor(() => expect(screen.getByText('Đã cập nhật master data.')).toBeInTheDocument());
    expect(screen.getByRole('heading', { name: 'Tạo mới môn học' })).toBeInTheDocument();
    expect(mockedHttpRequest.mock.calls.filter(([path]) => typeof path === 'string' && path.startsWith('/master-data/courses?')).length).toBeGreaterThan(1);
  });

  test('people edit appears for students, pre-fills values, prevents duplicate PATCH, and refreshes after success', async () => {
    const patchDeferred = deferred<ReturnType<typeof ok>>();
    installDefaultMasterDataMock({
      onMutation: (path, init) => {
        if (path === '/master-data/students/12' && init?.method === 'PATCH') {
          return patchDeferred.promise;
        }
        return ok({});
      },
    });

    render(<PeopleMasterDataPage />);

    const editButton = await screen.findByRole('button', { name: 'Sửa' });
    fireEvent.click(editButton);

    expect(screen.getByRole('heading', { name: 'Cập nhật sinh viên' })).toBeInTheDocument();
    expect(screen.getByLabelText('Họ tên')).toHaveValue('Nguyễn Văn B');
    expect(screen.getByLabelText('Mã sinh viên')).toHaveValue('SV002');

    fireEvent.change(screen.getByLabelText('Họ tên'), { target: { value: 'Nguyễn Văn C' } });
    const updateButton = screen.getByRole('button', { name: 'Cập nhật' });
    fireEvent.click(updateButton);
    fireEvent.click(updateButton);

    expect(mockedHttpRequest.mock.calls.filter(([path, init]) => path === '/master-data/students/12' && init?.method === 'PATCH')).toHaveLength(1);

    patchDeferred.resolve(ok({}));

    await waitFor(() => expect(screen.getByText('Đã cập nhật master data.')).toBeInTheDocument());
    expect(screen.getByRole('heading', { name: 'Tạo mới sinh viên' })).toBeInTheDocument();
  });

  test('edit failure keeps form open and shows backend error', async () => {
    installDefaultMasterDataMock({
      onMutation: (path, init) => {
        if (path === '/master-data/courses/5' && init?.method === 'PATCH') {
          return fail('Không thể cập nhật môn học');
        }
        return ok({});
      },
    });

    render(<AcademicMasterDataPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Môn học' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Sửa' }));
    fireEvent.change(screen.getByLabelText('Tên môn'), { target: { value: 'Kế toán quản trị' } });
    fireEvent.click(screen.getByRole('button', { name: 'Cập nhật' }));

    expect(await screen.findByText('Không thể cập nhật môn học')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Cập nhật môn học' })).toBeInTheDocument();
  });

  test('deferred and unsupported entities do not render misleading row actions', async () => {
    render(<AcademicMasterDataPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Chương trình đào tạo' }));
    expect(screen.queryByRole('button', { name: 'Sửa' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Ngừng sử dụng' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Ghi danh lớp học phần' }));
    expect(screen.queryByRole('button', { name: 'Sửa' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Ngừng sử dụng' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Môn học' }));
    expect(await screen.findByRole('button', { name: 'Sửa' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ngừng sử dụng' })).toBeInTheDocument();
  });

  test('deactivate dialog cancel, duplicate-confirm guard, failure, and success follow backend result', async () => {
    const deactivateDeferred = deferred<ReturnType<typeof ok>>();
    installDefaultMasterDataMock({
      onMutation: (path, init) => {
        if (path === '/master-data/devices/7/deactivate' && init?.method === 'POST') {
          return deactivateDeferred.promise;
        }
        return ok({});
      },
    });

    render(<FacilityPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Thiết bị' }));
    await screen.findByText('PC-01');

    fireEvent.click(within(screen.getByRole('table')).getByRole('button', { name: 'Ngừng sử dụng' }));
    const dialog = screen.getByRole('dialog', { name: 'Xác nhận ngưng sử dụng' });
    expect(within(dialog).getByText('Thao tác này sẽ ngưng sử dụng bản ghi đã chọn. Dữ liệu sẽ không bị xóa vĩnh viễn.')).toBeInTheDocument();
    expect(within(dialog).getByText(/Bản ghi:/)).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole('button', { name: 'Hủy' }));
    expect(mockedHttpRequest.mock.calls.filter(([path, init]) => path === '/master-data/devices/7/deactivate' && init?.method === 'POST')).toHaveLength(0);

    fireEvent.click(within(screen.getByRole('table')).getByRole('button', { name: 'Ngừng sử dụng' }));
    const failureDialog = screen.getByRole('dialog', { name: 'Xác nhận ngưng sử dụng' });
    const confirmButton = within(failureDialog).getByRole('button', { name: 'Ngưng sử dụng' });
    fireEvent.click(confirmButton);
    fireEvent.click(confirmButton);

    expect(mockedHttpRequest.mock.calls.filter(([path, init]) => path === '/master-data/devices/7/deactivate' && init?.method === 'POST')).toHaveLength(1);
    expect(within(failureDialog).getByRole('button', { name: 'Đang xử lý...' })).toBeDisabled();

    await act(async () => {
      deactivateDeferred.resolve(ok({}));
      await Promise.resolve();
    });
    expect(await screen.findByText('Đã ngưng sử dụng bản ghi.')).toBeInTheDocument();

    cleanup();
    const deactivateFailureDeferred = deferred<ReturnType<typeof fail>>();
    installDefaultMasterDataMock({
      onMutation: (path, init) => {
        if (path === '/master-data/devices/7/deactivate' && init?.method === 'POST') {
          return deactivateFailureDeferred.promise;
        }
        return ok({});
      },
    });
    render(<FacilityPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Thiết bị' }));
    await screen.findByText('PC-01');
    fireEvent.click(within(screen.getByRole('table')).getByRole('button', { name: 'Ngừng sử dụng' }));
    const failingDialog = screen.getByRole('dialog', { name: 'Xác nhận ngưng sử dụng' });
    fireEvent.click(within(failingDialog).getByRole('button', { name: 'Ngưng sử dụng' }));
    await act(async () => {
      deactivateFailureDeferred.resolve(fail('Không thể ngưng sử dụng thiết bị'));
      await Promise.resolve();
    });
    await waitFor(() => {
      expect(within(screen.getByRole('dialog', { name: 'Xác nhận ngưng sử dụng' })).getByText(/Không thể ngưng sử dụng thiết bị/i)).toBeInTheDocument();
    });

    cleanup();
    installDefaultMasterDataMock();
    render(<FacilityPage />);
    fireEvent.click((await screen.findAllByRole('button', { name: 'Thiết bị' }))[0]);
    await screen.findByText('PC-01');
    fireEvent.click(within(screen.getAllByRole('table')[0]).getByRole('button', { name: 'Ngừng sử dụng' }));
    fireEvent.click(within(screen.getByRole('dialog', { name: 'Xác nhận ngưng sử dụng' })).getByRole('button', { name: 'Ngưng sử dụng' }));

    await waitFor(() => {
      const deactivateCalls = mockedHttpRequest.mock.calls.filter(([path, init]) => path === '/master-data/devices/7/deactivate' && init?.method === 'POST');
      expect(deactivateCalls.length).toBeGreaterThan(0);
    });
    expect(await screen.findByText('Đã ngưng sử dụng bản ghi.')).toBeInTheDocument();
  });

  test('facility side actions are guarded while in flight', async () => {
    const assignDeferred = deferred<ReturnType<typeof ok>>();
    const retireDeferred = deferred<ReturnType<typeof ok>>();
    const bulkDeferred = deferred<ReturnType<typeof ok>>();
    installDefaultMasterDataMock({
      onMutation: (path, init) => {
        if (path === '/master-data/devices/7/assign-station' && init?.method === 'POST') {
          return assignDeferred.promise;
        }
        if (path === '/master-data/devices/7/retire' && init?.method === 'POST') {
          return retireDeferred.promise;
        }
        if (path === '/master-data/rooms/1/stations/bulk-generate' && init?.method === 'POST') {
          return bulkDeferred.promise;
        }
        return ok({});
      },
    });

    render(<FacilityPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Thiết bị' }));
    await screen.findByText('PC-01');
    const deviceActionsPanel = screen.getByRole('heading', { name: 'Thao tác thiết bị' }).closest('section');
    expect(deviceActionsPanel).not.toBeNull();
    fireEvent.change(within(deviceActionsPanel as HTMLElement).getByLabelText('ID thiết bị'), { target: { value: '7' } });
    fireEvent.change(within(deviceActionsPanel as HTMLElement).getByLabelText('ID vị trí máy'), { target: { value: '11' } });
    const assignButton = within(deviceActionsPanel as HTMLElement).getByRole('button', { name: 'Gán vào vị trí' });
    fireEvent.click(assignButton);
    fireEvent.click(assignButton);
    expect(mockedHttpRequest.mock.calls.filter(([path, init]) => path === '/master-data/devices/7/assign-station' && init?.method === 'POST')).toHaveLength(1);
    expect(within(deviceActionsPanel as HTMLElement).getByRole('button', { name: 'Đang gán...' })).toBeDisabled();
    await act(async () => {
      assignDeferred.resolve(ok({}));
      await Promise.resolve();
    });

    fireEvent.change(within(deviceActionsPanel as HTMLElement).getAllByLabelText('ID thiết bị')[0], { target: { value: '7' } });
    fireEvent.change(within(deviceActionsPanel as HTMLElement).getByLabelText('ID thiết bị ngừng sử dụng'), { target: { value: '7' } });
    const retireButton = within(deviceActionsPanel as HTMLElement).getByRole('button', { name: 'Ngừng sử dụng' });
    fireEvent.click(retireButton);
    fireEvent.click(retireButton);
    expect(mockedHttpRequest.mock.calls.filter(([path, init]) => path === '/master-data/devices/7/retire' && init?.method === 'POST')).toHaveLength(1);
    expect(within(deviceActionsPanel as HTMLElement).getByRole('button', { name: 'Đang ngừng sử dụng...' })).toBeDisabled();
    await act(async () => {
      retireDeferred.resolve(ok({}));
      await Promise.resolve();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Vị trí máy trạm' }));
    await screen.findByText('Tạo nhanh vị trí máy');
    const bulkButton = screen.getByRole('button', { name: 'Tạo vị trí' });
    fireEvent.click(bulkButton);
    fireEvent.click(bulkButton);
    expect(mockedHttpRequest.mock.calls.filter(([path, init]) => path === '/master-data/rooms/1/stations/bulk-generate' && init?.method === 'POST')).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'Đang tạo...' })).toBeDisabled();
    await act(async () => {
      bulkDeferred.resolve(ok({}));
      await Promise.resolve();
    });
  });

  test('facility side actions surface backend errors where available', async () => {
    installDefaultMasterDataMock({
      onMutation: (path, init) => {
        if (path === '/master-data/devices/7/assign-station' && init?.method === 'POST') {
          return fail('Không thể gán thiết bị');
        }
        if (path === '/master-data/devices/7/retire' && init?.method === 'POST') {
          return fail('Không thể retire thiết bị');
        }
        if (path === '/master-data/rooms/1/stations/bulk-generate' && init?.method === 'POST') {
          return fail('Không thể tạo vị trí máy');
        }
        return ok({});
      },
    });

    render(<FacilityPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Thiết bị' }));
    const deviceActionsPanel = screen.getByRole('heading', { name: 'Thao tác thiết bị' }).closest('section');
    expect(deviceActionsPanel).not.toBeNull();
    fireEvent.change(within(deviceActionsPanel as HTMLElement).getByLabelText('ID thiết bị'), { target: { value: '7' } });
    fireEvent.change(within(deviceActionsPanel as HTMLElement).getByLabelText('ID vị trí máy'), { target: { value: '11' } });
    fireEvent.click(within(deviceActionsPanel as HTMLElement).getByRole('button', { name: 'Gán vào vị trí' }));
    expect(await screen.findByText('Không thể gán thiết bị')).toBeInTheDocument();

    fireEvent.change(within(deviceActionsPanel as HTMLElement).getByLabelText('ID thiết bị ngừng sử dụng'), { target: { value: '7' } });
    fireEvent.click(within(deviceActionsPanel as HTMLElement).getByRole('button', { name: 'Ngừng sử dụng' }));
    expect(await screen.findByText('Không thể retire thiết bị')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Vị trí máy trạm' }));
    await screen.findByText('Tạo nhanh vị trí máy');
    fireEvent.click(screen.getByRole('button', { name: 'Tạo vị trí' }));
    expect(await screen.findByText('Không thể tạo vị trí máy')).toBeInTheDocument();
  });

  test('search, filter, page, previous, and page size changes send canonical query params and reset page where required', async () => {
    render(<AcademicMasterDataPage />);

    await screen.findByRole('button', { name: 'Khoa / phòng ban' });
    fireEvent.click(screen.getByRole('button', { name: 'Sau' }));

    await waitFor(() => {
      const called = mockedHttpRequest.mock.calls.some(([path]) => typeof path === 'string' && path.includes('page=2&page_size=20'));
      expect(called).toBe(true);
    });

    fireEvent.click(screen.getByRole('button', { name: 'Trước' }));
    await waitFor(() => {
      const called = mockedHttpRequest.mock.calls.some(([path]) => typeof path === 'string' && path.includes('page=1&page_size=20'));
      expect(called).toBe(true);
    });

    fireEvent.change(screen.getByLabelText('Tìm kiếm'), { target: { value: 'tai chinh' } });
    fireEvent.click(screen.getByRole('button', { name: 'Áp dụng' }));
    await waitFor(() => {
      const called = mockedHttpRequest.mock.calls.some(([path]) => typeof path === 'string' && path.includes('page=1&page_size=20') && path.includes('query=tai+chinh'));
      expect(called).toBe(true);
    });

    fireEvent.click(screen.getByRole('button', { name: 'Sau' }));
    await waitFor(() => {
      const called = mockedHttpRequest.mock.calls.some(([path]) => typeof path === 'string' && path.includes('page=2&page_size=20') && path.includes('query=tai+chinh'));
      expect(called).toBe(true);
    });

    fireEvent.change(screen.getAllByLabelText('Trạng thái')[0], { target: { value: 'ACTIVE' } });
    fireEvent.click(screen.getByRole('button', { name: 'Áp dụng' }));
    await waitFor(() => {
      const called = mockedHttpRequest.mock.calls.some(([path]) => typeof path === 'string' && path.includes('page=1&page_size=20') && path.includes('query=tai+chinh') && path.includes('status=ACTIVE'));
      expect(called).toBe(true);
    });

    fireEvent.change(screen.getByLabelText('Số dòng/trang'), { target: { value: '50' } });
    await waitFor(() => {
      const called = mockedHttpRequest.mock.calls.some(([path]) => typeof path === 'string' && path.includes('page=1&page_size=50') && path.includes('query=tai+chinh') && path.includes('status=ACTIVE'));
      expect(called).toBe(true);
    });
  });

  test('changing selected entity resets query, page, and edit state', async () => {
    render(<AcademicMasterDataPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Môn học' }));
    fireEvent.change(screen.getByLabelText('Tìm kiếm'), { target: { value: 'ACC' } });
    fireEvent.click(screen.getByRole('button', { name: 'Áp dụng' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Sửa' }));
    expect(screen.getByRole('heading', { name: 'Cập nhật môn học' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Lớp học phần' }));
    await screen.findByRole('heading', { name: 'Tạo mới lớp học phần' });
    expect(screen.getByLabelText('Tìm kiếm')).toHaveValue('');
    expect(screen.getByText(/Trang 1/)).toBeInTheDocument();
  });

  test('error state can retry and empty lists show the empty state', async () => {
    let shouldFail = true;
    installDefaultMasterDataMock({
      departmentList: () =>
        shouldFail
          ? fail('Không tải được danh mục đơn vị')
          : ok({ items: [], pagination: { page: 1, page_size: 20, total: 0, total_pages: 0, has_next: false, has_previous: false } }),
    });

    render(<AcademicMasterDataPage />);

    expect(await screen.findByText('Không tải được danh mục đơn vị')).toBeInTheDocument();
    shouldFail = false;
    fireEvent.click(screen.getByRole('button', { name: 'Tải lại' }));

    expect(await screen.findByText('Chưa có dữ liệu.')).toBeInTheDocument();
  });

  test('lookup fields prefer select when loaded and stay disabled while loading', async () => {
    const departmentDeferred = deferred<ReturnType<typeof ok>>();
    installDefaultMasterDataMock({
      departmentList: () => departmentDeferred.promise,
    });

    render(<AcademicMasterDataPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Môn học' }));
    const departmentField = screen.getByLabelText('Đơn vị quản lý');
    expect(departmentField).toBeDisabled();
    expect(screen.getByRole('option', { name: 'Đang tải...' })).toBeInTheDocument();

    await act(async () => {
      departmentDeferred.resolve(
        ok({
          items: [{ department_id: 3, department_code: 'SFA', department_name: 'Khoa Tài chính', status: 'ACTIVE' }],
          pagination: { page: 1, page_size: 20, total: 1, total_pages: 1, has_next: false, has_previous: false },
        })
      );
      await Promise.resolve();
    });

    await waitFor(() => expect(screen.getByLabelText('Đơn vị quản lý')).not.toBeDisabled());
    expect(screen.getByRole('option', { name: /SFA - Khoa Tài chính/i })).toBeInTheDocument();
  });

  test('lookup manual fallback is shown only for configured entities when lookup fails', async () => {
    installDefaultMasterDataMock({
      departmentList: () => fail('Lookup departments failed'),
      courseList: () => fail('Lookup courses failed'),
    });

    render(<AcademicMasterDataPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Môn học' }));
    expect(await screen.findByText('Không tải được danh mục. Có thể nhập ID thủ công.')).toBeInTheDocument();
    expect(screen.getByText('Nhập ID hiện có trong hệ thống.')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Lớp học phần' }));
    const courseLookup = screen.getByLabelText('Môn học');
    expect(courseLookup).toBeDisabled();
    const courseLookupContainer = courseLookup.closest('div');
    expect(courseLookupContainer).not.toBeNull();
    expect(within(courseLookupContainer as HTMLElement).queryByText('Nhập ID hiện có trong hệ thống.')).not.toBeInTheDocument();
    expect(await within(courseLookupContainer as HTMLElement).findByText('Không tải được danh mục. Hãy thử tải lại.')).toBeInTheDocument();
  });

  test('manual numeric fallback validation does not fail just because the lookup first page does not include the current ID', async () => {
    installDefaultMasterDataMock({
      studentList: () =>
        ok({
          items: [
            {
              student_id: 12,
              full_name: 'Nguyễn Văn B',
              student_code: 'SV002',
              student_status: 'ACTIVE',
              program_id: 999,
            },
          ],
          pagination: { page: 1, page_size: 20, total: 1, total_pages: 1, has_next: false, has_previous: false },
        }),
      onMutation: (path, init) => {
        if (path === '/master-data/students/12' && init?.method === 'PATCH') {
          return ok({});
        }
        return ok({});
      },
    });

    render(<PeopleMasterDataPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Sửa' }));
    expect(screen.getByRole('option', { name: 'ID hiện có: 999' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Cập nhật' }));

    await waitFor(() => {
      const called = mockedHttpRequest.mock.calls.some(([path, init]) => path === '/master-data/students/12' && init?.method === 'PATCH');
      expect(called).toBe(true);
    });
    expect(screen.queryByText('Chương trình đào tạo không hợp lệ.')).not.toBeInTheDocument();
  });
});
