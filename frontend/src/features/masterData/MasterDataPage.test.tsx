import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { httpRequest } from '../../shared/api/httpClient';
import { FacilityPage } from '../facility/FacilityPage';
import { AcademicMasterDataPage } from './academic/AcademicMasterDataPage';
import { MasterDataPage, importEntityKeyByType } from './MasterDataPage';
import { PeopleMasterDataPage } from './people/PeopleMasterDataPage';

vi.mock('../../shared/api/httpClient', () => ({
  httpRequest: vi.fn(),
}));

const mockedHttpRequest = vi.mocked(httpRequest);

function ok(data: unknown) {
  return { ok: true, success: true, data, error: null, message: null };
}

beforeEach(() => {
  mockedHttpRequest.mockReset();
  mockedHttpRequest.mockImplementation((path, init) => {
    if (path === '/master-data/import-templates') return Promise.resolve(ok({ items: [] }));
    if (path === '/master-data/departments?page=1&page_size=20') {
      return Promise.resolve(ok({ items: [{ department_id: 3, department_code: 'SFA', department_name: 'Khoa Tài chính' }] }));
    }
    if (path === '/master-data/programs?page=1&page_size=20') return Promise.resolve(ok({ items: [] }));
    if (path === '/master-data/courses?page=1&page_size=20') {
      return Promise.resolve(ok({ items: [{ course_id: 5, course_code: 'ACC101', course_name: 'Kế toán căn bản' }] }));
    }
    if (path === '/master-data/class-sections?page=1&page_size=20') {
      return Promise.resolve(ok({ items: [{ class_section_id: 8, class_code: 'ACC101-01', class_name: 'Lớp ACC101-01' }] }));
    }
    if (path === '/master-data/enrollments?page=1&page_size=20') {
      return Promise.resolve(ok({ items: [{ enrollment_id: 12, class_code: 'ACC101-01', student_code: 'SV001' }] }));
    }
    if (path === '/master-data/rooms?page=1&page_size=20') {
      return Promise.resolve(ok({ items: [{ room_id: 1, room_code: 'D13', room_name: 'Phòng D13', status: 'ACTIVE', room_type: 'LAB' }] }));
    }
    if (path === '/master-data/rooms/1/stations?page=1&page_size=200') {
      return Promise.resolve(ok({ items: [{ station_id: 11, station_code: 'A1', status: 'ACTIVE' }] }));
    }
    if (path === '/master-data/rooms/1/station-readiness') {
      return Promise.resolve(ok({ items: [{ room_code: 'D13', station_code: 'A1', asset_tag: 'PC-01', latest_health_status: 'READY' }] }));
    }
    if (path === '/master-data/devices?page=1&page_size=20') {
      return Promise.resolve(ok({ items: [{ device_id: 7, asset_tag: 'PC-01', device_type: 'LAB_PC', status: 'ACTIVE' }] }));
    }
    if (init?.method === 'POST') return Promise.resolve(ok({}));
    return Promise.resolve(ok({ items: [] }));
  });
});

describe('Phase 2A master data surfaces', () => {
  test('landing page links to the four master data surfaces', async () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <MasterDataPage />
      </MemoryRouter>
    );

    expect(screen.getByRole('heading', { name: 'Trung tâm dữ liệu nền' })).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'Mở surface' })).toHaveLength(4);
    expect(screen.getAllByRole('link', { name: 'Mở surface' }).map((link) => link.getAttribute('href'))).toEqual([
      '/admin/master-data/academic',
      '/admin/master-data/people',
      '/admin/facility',
      '/admin/imports',
    ]);
    expect(screen.getByText('Học thuật')).toBeInTheDocument();
    expect(screen.getByText('Con người')).toBeInTheDocument();
    expect(screen.getByText('Cơ sở vật chất')).toBeInTheDocument();
    expect(screen.getByText('Import Center')).toBeInTheDocument();
  });

  test('academic page uses canonical Vietnamese labels for courses and class sections', async () => {
    render(<AcademicMasterDataPage />);

    expect(await screen.findByRole('button', { name: 'Môn học' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Lớp học phần' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Mở môn theo học kỳ' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ghi danh lớp học phần' })).toBeInTheDocument();
  });

  test('academic page keeps create forms visible for courses and class sections', async () => {
    render(<AcademicMasterDataPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Môn học' }));
    expect(screen.getByLabelText('Mã môn')).toBeInTheDocument();
    expect(screen.getByLabelText('Tên môn')).toBeInTheDocument();
    expect(screen.getByLabelText('Đơn vị quản lý')).toBeInTheDocument();
    expect(await screen.findByRole('option', { name: /SFA - Khoa Tài chính/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Lớp học phần' }));
    expect(screen.getByLabelText('Mã lớp học phần')).toBeInTheDocument();
    expect(screen.getByLabelText('Tên lớp học phần')).toBeInTheDocument();
    expect(screen.getByLabelText('Môn học')).toBeInTheDocument();
    expect(screen.getByLabelText('ID học kỳ')).toBeInTheDocument();
    expect(await screen.findByRole('option', { name: /ACC101 - Kế toán căn bản/i })).toBeInTheDocument();
  });

  test('academic page still creates a course via the existing API', async () => {
    render(<AcademicMasterDataPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Môn học' }));
    expect(await screen.findByRole('option', { name: /SFA - Khoa Tài chính/i })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Đơn vị quản lý'), { target: { value: '3' } });
    fireEvent.change(screen.getByLabelText('Mã môn'), { target: { value: 'ACC102' } });
    fireEvent.change(screen.getByLabelText('Tên môn'), { target: { value: 'Kế toán quản trị' } });
    fireEvent.click(screen.getByRole('button', { name: 'Lưu' }));

    await waitFor(() => {
      const matched = mockedHttpRequest.mock.calls.some(
        ([path, init]) =>
          path === '/master-data/courses' &&
          init?.method === 'POST' &&
          init.body === JSON.stringify({ department_id: 3, course_code: 'ACC102', course_name: 'Kế toán quản trị', status: 'ACTIVE' })
      );
      expect(matched).toBe(true);
    });
  });

  test('import types refresh the correct master-data entity', () => {
    expect(importEntityKeyByType.COURSES).toBe('courses');
    expect(importEntityKeyByType.SUBJECTS).toBe('courses');
    expect(importEntityKeyByType.CLASS_SECTIONS).toBe('classSections');
    expect(importEntityKeyByType.ENROLLMENTS).toBe('enrollments');
  });

  test('people page renders students and instructors', async () => {
    render(<PeopleMasterDataPage />);
    expect(await screen.findByRole('button', { name: 'Sinh viên' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Giảng viên' })).toBeInTheDocument();
  });

  test('people page still creates a student via the existing API', async () => {
    render(<PeopleMasterDataPage />);

    fireEvent.change(await screen.findByLabelText('Họ tên'), { target: { value: 'Nguyễn Văn B' } });
    fireEvent.change(screen.getByLabelText('Mã sinh viên'), { target: { value: 'SV002' } });
    fireEvent.click(screen.getByRole('button', { name: 'Lưu' }));

    await waitFor(() => {
      const matched = mockedHttpRequest.mock.calls.some(
        ([path, init]) =>
          path === '/master-data/students' &&
          init?.method === 'POST' &&
          init.body === JSON.stringify({ full_name: 'Nguyễn Văn B', student_code: 'SV002', student_status: 'ACTIVE' })
      );
      expect(matched).toBe(true);
    });
  });

  test('facility page renders facility section tabs', async () => {
    render(<FacilityPage />);
    expect(await screen.findByRole('button', { name: 'Phòng thi / phòng máy' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Vị trí máy trạm' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Thiết bị' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Kiểm tra thiết bị' })).toBeInTheDocument();
  });

  test('room list renders from canonical rooms endpoint', async () => {
    render(<FacilityPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Phòng thi / phòng máy' }));
    await waitFor(() => expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/rooms?page=1&page_size=20'));
    expect(screen.getByRole('button', { name: 'Tải lại' })).toBeInTheDocument();
  });

  test('station bulk generator previews A1-A6 and 1-50 then calls API', async () => {
    render(<FacilityPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Vị trí máy trạm' }));
    await screen.findByText('Tạo nhanh vị trí máy');
    expect(screen.getByText(/Xem trước: A1, A2, A3, A4, A5, A6, B1, B2, B3, B4, B5, B6/i)).toBeInTheDocument();

    const bulkPatternField = screen.getByLabelText('Dạng tạo').closest('div');
    expect(bulkPatternField).toHaveClass('master-data-field', 'field-span-sm');
    expect(bulkPatternField).toHaveAttribute('data-field-kind', 'select');
    expect(bulkPatternField).toHaveAttribute('data-field-size', 'sm');

    fireEvent.change(screen.getByLabelText('Dạng tạo'), { target: { value: 'numeric' } });
    fireEvent.change(screen.getByLabelText('Số bắt đầu'), { target: { value: '1' } });
    fireEvent.change(screen.getByLabelText('Số kết thúc'), { target: { value: '50' } });
    expect(screen.getByText(/Xem trước: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Tạo vị trí' }));
    await waitFor(() =>
      expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/rooms/1/stations/bulk-generate', {
        method: 'POST',
        body: JSON.stringify({
          row_labels: undefined,
          start_number: 1,
          end_number: 50,
          zero_pad: 0,
          status: 'ACTIVE',
        }),
      })
    );
  });

  test('device list renders and assign device to station calls API', async () => {
    render(<FacilityPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Thiết bị' }));
    await waitFor(() => expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/devices?page=1&page_size=20'));

    const assignDeviceField = screen.getByLabelText('ID thiết bị').closest('div');
    expect(assignDeviceField).toHaveClass('master-data-field', 'field-span-sm');
    expect(assignDeviceField).toHaveAttribute('data-field-kind', 'id');
    expect(assignDeviceField).toHaveAttribute('data-field-size', 'sm');

    fireEvent.change(screen.getByLabelText('ID thiết bị'), { target: { value: '7' } });
    fireEvent.change(screen.getByLabelText('ID vị trí máy'), { target: { value: '11' } });
    fireEvent.click(screen.getByRole('button', { name: 'Gán vào vị trí' }));

    await waitFor(() =>
      expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/devices/7/assign-station', {
        method: 'POST',
        body: JSON.stringify({ station_id: 11 }),
      })
    );
  });

  test('retire device action keeps canonical payload contract', async () => {
    render(<FacilityPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Thiết bị' }));
    await waitFor(() => expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/devices?page=1&page_size=20'));

    const deviceActionsPanel = screen.getByText('Thao tác thiết bị').closest('.compact-surface') as HTMLElement;
    fireEvent.change(screen.getByLabelText('ID thiết bị ngừng sử dụng'), { target: { value: '7' } });
    fireEvent.click(within(deviceActionsPanel).getByRole('button', { name: 'Ngừng sử dụng' }));

    await waitFor(() =>
      expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/devices/7/retire', {
        method: 'POST',
        body: JSON.stringify({ reason: 'Ngưng sử dụng' }),
      })
    );
  });

  test('readiness table displays health statuses', async () => {
    render(<FacilityPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Kiểm tra thiết bị' }));
    fireEvent.change(screen.getByLabelText('Phòng thi / phòng máy'), { target: { value: '1' } });
    await waitFor(() => {
      const called = mockedHttpRequest.mock.calls.some(([path]) => path === '/master-data/rooms/1/station-readiness');
      expect(called).toBe(true);
    });
  });

  test('no mojibake markers in touched files', async () => {
    const fs = await import('node:fs');
    const content = fs.readFileSync('src/features/masterData/MasterDataPage.tsx', 'utf8');
    for (const marker of ['\u00c4\u2018', '\u00e1\u00bb', '\u00c3', 'M\u00c3', 'ph\u00c3\u00b2ng', 'm\u00c3\u00a1y']) {
      expect(content.includes(marker)).toBe(false);
    }
  });
});
