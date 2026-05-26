import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { ExamSetupPage } from './ExamSetupPage';
import { httpRequest } from '../../shared/api/httpClient';

vi.mock('../../shared/api/httpClient', () => ({ httpRequest: vi.fn() }));

const ok = <T,>(data: T) => ({ ok: true as const, success: true as const, data, error: null, message: null });
const list = (items: Array<Record<string, unknown>>) => ok({ items, pagination: { page: 1, page_size: 20, total_items: items.length } });

describe('Exam setup sitting-scoped sections', () => {
  beforeEach(() => {
    vi.mocked(httpRequest).mockReset();
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path.startsWith('/master-data/exams?page')) return list([{ exam_id: 11, exam_code: 'ACC101', exam_name: 'Kế toán', class_section_id: 21, assessment_type_id: 1 }]);
      if (path.startsWith('/master-data/class-sections')) return list([{ class_section_id: 21, class_code: 'ACC101-01', class_name: 'Lớp 1' }]);
      if (path.startsWith('/master-data/assessment-types')) return list([{ assessment_type_id: 1, type_code: 'MIDTERM', type_name: 'Giữa kỳ' }]);
      if (path.startsWith('/master-data/facilities/rooms')) return list([{ room_id: 31, room_code: 'D13', room_name: 'Phòng D13', capacity: 40 }]);
      if (path.startsWith('/master-data/rooms/31/stations')) return list([{ station_id: 91, room_id: 31, room_code: 'D13', station_code: 'A1' }, { station_id: 92, room_id: 31, room_code: 'D13', station_code: '1' }]);
      if (path.startsWith('/master-data/facilities/stations')) return list([{ station_id: 91, room_id: 31, room_code: 'D13', station_code: 'A1' }, { station_id: 92, room_id: 31, room_code: 'D13', station_code: '1' }, { station_id: 93, room_id: 32, room_code: 'D14', station_code: 'B1' }]);
      if (path.startsWith('/master-data/students')) return list([{ student_id: 1, student_code: 'SV001', full_name: 'Nguyễn A' }]);
      if (path.startsWith('/master-data/instructors')) return list([{ instructor_id: 2, user_id: 12, username: 'gv001', instructor_code: 'GV001', full_name: 'Giảng viên A' }]);
      if (path.endsWith('/status')) return ok({ module: 'ok', status: 'ok', ready: true });
      if (path.startsWith('/master-data/exams/11/versions')) return list([{ exam_version_id: 101, exam_id: 11, exam_code: 'ACC101', version_label: 'V1', version_no: 1, status: 'DRAFT' }]);
      if (path.startsWith('/master-data/exam-versions/101/delivery-profile')) return ok({ exam_version_delivery_profile_id: 1, exam_version_id: 101, delivery_mode: 'FORM_BASED', work_mode: 'INDIVIDUAL', primary_answer_source: 'SEALED_TEXT_ANSWER', requires_capture: false, capture_timing: 'NONE', allow_mixed_question_sources: false, form_autosave_enabled: true, database_work_mode: 'NONE', status: 'ACTIVE' });
      if (path.startsWith('/master-data/exam-versions/101/question-grading-profiles')) return list([]);
      if (path.startsWith('/master-data/exam-versions/101/questions')) return ok({ items: [], readiness_summary: { ready: false, missing_items: [] } });
      if (path === '/delivery/exam-sittings') return list([{ exam_sitting_id: 2000, exam_version_id: 101, exam_version_label: 'V1', sitting_code: 'S0', sitting_name: 'Ca 0', scheduled_start_at: '2026-06-10T01:00:00Z', scheduled_end_at: '2026-06-10T03:00:00Z', sitting_status: 'DRAFT' }]);
      if (path.startsWith('/delivery/exam-sittings/2000/rooms') && init?.method === 'POST') return ok({ exam_sitting_room_id: 3001, exam_sitting_id: 2000, room_id: 31, room_code: 'D13', room_name: 'Phòng D13', room_status: 'PLANNED' });
      if (path.startsWith('/delivery/exam-sittings/2000/rooms')) return list([{ exam_sitting_room_id: 3001, exam_sitting_id: 2000, room_id: 31, room_code: 'D13', room_name: 'Phòng D13', room_status: 'PLANNED' }]);
      if (path.startsWith('/delivery/exam-sittings/2000/assignments') && init?.method === 'POST') return ok({ exam_assignment_id: 4001, exam_sitting_id: 2000, student_id: 1, student_code: 'SV001', student_name: 'Nguyễn A', assignment_status: 'ASSIGNED' });
      if (path.startsWith('/delivery/exam-sittings/2000/assignments')) return list([{ exam_assignment_id: 4001, exam_sitting_id: 2000, student_id: 1, student_code: 'SV001', student_name: 'Nguyễn A', assignment_status: 'ASSIGNED' }]);
      if (path.startsWith('/delivery/exam-assignments/4001/station') && init?.method === 'POST') return ok({ station_assignment_id: 5001, exam_assignment_id: 4001, exam_sitting_room_id: 3001, station_id: 91, station_code: 'A1', status: 'ASSIGNED' });
      if (path.startsWith('/delivery/station-assignments/5001') && init?.method === 'PATCH') return ok({ station_assignment_id: 5001, exam_assignment_id: 4001, exam_sitting_room_id: 3001, station_id: 91, station_code: 'A1', status: 'ASSIGNED' });
      if (path.startsWith('/delivery/station-assignments/5002') && init?.method === 'PATCH') return ok({ station_assignment_id: 5002, exam_assignment_id: 4001, exam_sitting_room_id: 3001, station_id: 92, station_code: '1', status: 'ASSIGNED' });
      if (path.startsWith('/delivery/exam-sittings/2000/seating-plan')) return list([{ station_assignment_id: 5002, exam_assignment_id: 4001, exam_sitting_room_id: 3001, station_id: 92, station_code: '1', status: 'ASSIGNED' }]);
      if (path.startsWith('/delivery/exam-sitting-rooms/3001/proctors') && init?.method === 'POST') return ok({ proctor_assignment_id: 6001, exam_sitting_room_id: 3001, proctor_user_id: 12, proctor_role: 'ROOM_PROCTOR', status: 'ASSIGNED' });
      if (path.startsWith('/delivery/exam-sitting-rooms/3001/proctors')) return list([{ proctor_assignment_id: 6001, exam_sitting_room_id: 3001, proctor_user_id: 12, proctor_role: 'ROOM_PROCTOR', status: 'ASSIGNED' }]);
      if (path.startsWith('/delivery/exam-sitting-rooms/3001') && init?.method === 'PATCH') return ok({ exam_sitting_room_id: 3001, room_status: 'READY' });
      if (path.startsWith('/delivery/proctor-assignments/6001') && init?.method === 'PATCH') return ok({ proctor_assignment_id: 6001, status: 'ASSIGNED' });
      if (path.startsWith('/delivery/exam-assignments/4001') && init?.method === 'PATCH') return ok({ exam_assignment_id: 4001, assignment_status: 'ASSIGNED' });
      return ok({});
    });
  });

  test('rooms, students, seating, and proctors call sitting-scoped APIs', async () => {
    render(<ExamSetupPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Phòng thi' }));
    fireEvent.change(await screen.findByLabelText('Phòng thi'), { target: { value: '31' } });
    fireEvent.click(screen.getByRole('button', { name: 'Thêm phòng thi' }));
    await waitFor(() => expect(vi.mocked(httpRequest)).toHaveBeenCalledWith('/delivery/exam-sittings/2000/rooms', expect.objectContaining({ method: 'POST' })));

    fireEvent.click(screen.getByRole('button', { name: 'Sinh viên dự thi' }));
    fireEvent.change(await screen.findByLabelText('Danh sách thí sinh'), { target: { value: '1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Thêm thí sinh' }));
    await waitFor(() => expect(vi.mocked(httpRequest)).toHaveBeenCalledWith('/delivery/exam-sittings/2000/assignments', expect.objectContaining({ method: 'POST' })));

    fireEvent.click(screen.getByRole('button', { name: 'Xếp máy' }));
    expect(await screen.findByLabelText('Vị trí máy')).toHaveTextContent('A1');
    await screen.findByText('1');
    fireEvent.change(screen.getByLabelText('Danh sách thí sinh'), { target: { value: '4001' } });
    fireEvent.change(screen.getByLabelText('Phòng thi trong ca'), { target: { value: '3001' } });
    fireEvent.change(screen.getByLabelText('Vị trí máy'), { target: { value: '91' } });
    fireEvent.click(screen.getByRole('button', { name: 'Gán chỗ' }));
    await waitFor(() => expect(vi.mocked(httpRequest)).toHaveBeenCalledWith('/delivery/exam-assignments/4001/station', expect.objectContaining({ method: 'POST' })));

    fireEvent.click(screen.getByRole('button', { name: 'Giám thị' }));
    fireEvent.change(await screen.findByLabelText('Tài khoản giám thị'), { target: { value: '12' } });
    fireEvent.click(screen.getByRole('button', { name: 'Gán giám thị' }));
    await waitFor(() => expect(vi.mocked(httpRequest)).toHaveBeenCalledWith('/delivery/exam-sitting-rooms/3001/proctors', expect.objectContaining({ method: 'POST' })));
  });

  test('room select requires an explicit room_id before adding the room', async () => {
    render(<ExamSetupPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Phòng thi' }));

    const roomSelect = await screen.findByLabelText('Phòng thi');
    const addButton = screen.getByRole('button', { name: 'Thêm phòng thi' });
    expect(roomSelect).toHaveValue('');
    expect(addButton).toBeDisabled();

    fireEvent.change(roomSelect, { target: { value: '31' } });
    expect(addButton).toBeEnabled();
    fireEvent.click(addButton);

    await waitFor(() =>
      expect(vi.mocked(httpRequest)).toHaveBeenCalledWith(
        '/delivery/exam-sittings/2000/rooms',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"room_id":31'),
        })
      )
    );
  });

  test('seating filters stations by selected room and auto assigns unseated students', async () => {
    const postCalls: Array<{ path: string; body: string | undefined }> = [];
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path.startsWith('/master-data/exams?page')) return list([{ exam_id: 11, exam_code: 'ACC101', exam_name: 'Káº¿ toÃ¡n', class_section_id: 21, assessment_type_id: 1 }]);
      if (path.startsWith('/master-data/class-sections')) return list([{ class_section_id: 21, class_code: 'ACC101-01', class_name: 'Lá»›p 1' }]);
      if (path.startsWith('/master-data/assessment-types')) return list([{ assessment_type_id: 1, type_code: 'MIDTERM', type_name: 'Giá»¯a ká»³' }]);
      if (path.startsWith('/master-data/facilities/rooms')) return list([{ room_id: 31, room_code: 'D13', room_name: 'PhÃ²ng D13', capacity: 40 }]);
      if (path.startsWith('/master-data/rooms/31/stations')) return list([
        { station_id: 91, room_id: 31, room_code: 'D13', station_code: 'A1' },
        { station_id: 92, room_id: 31, room_code: 'D13', station_code: 'A2' },
      ]);
      if (path.startsWith('/master-data/facilities/stations')) return list([
        { station_id: 91, room_id: 31, room_code: 'D13', station_code: 'A1' },
        { station_id: 92, room_id: 31, room_code: 'D13', station_code: 'A2' },
        { station_id: 93, room_id: 32, room_code: 'D14', station_code: 'B1' },
      ]);
      if (path.startsWith('/master-data/students')) return list([{ student_id: 1, student_code: 'SV001', full_name: 'Nguyá»…n A' }, { student_id: 2, student_code: 'SV002', full_name: 'Nguyá»…n B' }]);
      if (path.startsWith('/master-data/instructors')) return list([]);
      if (path.endsWith('/status')) return ok({ module: 'ok', status: 'ok', ready: true });
      if (path.startsWith('/master-data/exams/11/versions')) return list([{ exam_version_id: 101, exam_id: 11, exam_code: 'ACC101', version_label: 'V1', version_no: 1, status: 'DRAFT' }]);
      if (path.startsWith('/master-data/exam-versions/101/delivery-profile')) return ok({ exam_version_delivery_profile_id: 1, exam_version_id: 101, delivery_mode: 'FORM_BASED', work_mode: 'INDIVIDUAL', primary_answer_source: 'SEALED_TEXT_ANSWER', requires_capture: false, capture_timing: 'NONE', allow_mixed_question_sources: false, form_autosave_enabled: true, database_work_mode: 'NONE', status: 'ACTIVE' });
      if (path.startsWith('/master-data/exam-versions/101/question-grading-profiles')) return list([]);
      if (path.startsWith('/master-data/exam-versions/101/questions')) return ok({ items: [], readiness_summary: { ready: false, missing_items: [] } });
      if (path === '/delivery/exam-sittings') return list([{ exam_sitting_id: 2000, exam_version_id: 101, exam_version_label: 'V1', sitting_code: 'S0', sitting_name: 'Ca 0', scheduled_start_at: '2026-06-10T01:00:00Z', scheduled_end_at: '2026-06-10T03:00:00Z', sitting_status: 'DRAFT' }]);
      if (path.startsWith('/delivery/exam-sittings/2000/rooms')) return list([{ exam_sitting_room_id: 3001, exam_sitting_id: 2000, room_id: 31, room_code: 'D13', room_name: 'PhÃ²ng D13', room_status: 'PLANNED' }]);
      if (path.startsWith('/delivery/exam-sittings/2000/assignments')) return list([
        { exam_assignment_id: 4001, exam_sitting_id: 2000, student_id: 1, student_code: 'SV001', student_name: 'Nguyá»…n A', assignment_status: 'ASSIGNED' },
        { exam_assignment_id: 4002, exam_sitting_id: 2000, student_id: 2, student_code: 'SV002', student_name: 'Nguyá»…n B', assignment_status: 'ASSIGNED' },
      ]);
      if (path.startsWith('/delivery/exam-sittings/2000/seating-plan')) return list([]);
      if (path.startsWith('/delivery/exam-assignments/') && path.endsWith('/station') && init?.method === 'POST') {
        postCalls.push({ path, body: String(init.body) });
        return ok({ station_assignment_id: 5000 + postCalls.length, status: 'ASSIGNED' });
      }
      return ok({});
    });

    render(<ExamSetupPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Xếp máy' }));
    const stationSelect = await screen.findByLabelText('Vị trí máy');
    expect(stationSelect).toHaveTextContent('A1');
    expect(stationSelect).toHaveTextContent('A2');
    expect(stationSelect).not.toHaveTextContent('B1');

    fireEvent.click(screen.getByRole('button', { name: 'Gán tự động' }));

    await waitFor(() => expect(postCalls).toHaveLength(2));
    expect(postCalls[0]).toMatchObject({ path: '/delivery/exam-assignments/4001/station' });
    expect(postCalls[0].body).toContain('"station_id":91');
    expect(postCalls[1]).toMatchObject({ path: '/delivery/exam-assignments/4002/station' });
    expect(postCalls[1].body).toContain('"station_id":92');
  });

  test('sitting-scoped sections expose edit and update controls', async () => {
    render(<ExamSetupPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Phòng thi' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Sửa' }));
    fireEvent.click(screen.getByRole('button', { name: 'Cập nhật phòng thi' }));
    await waitFor(() => expect(vi.mocked(httpRequest)).toHaveBeenCalledWith('/delivery/exam-sitting-rooms/3001', expect.objectContaining({ method: 'PATCH' })));

    fireEvent.click(screen.getByRole('button', { name: 'Sinh viên dự thi' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Sửa' }));
    fireEvent.click(screen.getByRole('button', { name: 'Cập nhật thí sinh' }));
    await waitFor(() => expect(vi.mocked(httpRequest)).toHaveBeenCalledWith('/delivery/exam-assignments/4001', expect.objectContaining({ method: 'PATCH' })));

    fireEvent.click(screen.getByRole('button', { name: 'Xếp máy' }));
    fireEvent.click((await screen.findAllByRole('button', { name: 'Sửa' }))[0]);
    fireEvent.click(screen.getByRole('button', { name: 'Cập nhật chỗ ngồi' }));
    await waitFor(() => expect(vi.mocked(httpRequest)).toHaveBeenCalledWith('/delivery/station-assignments/5002', expect.objectContaining({ method: 'PATCH' })));

    fireEvent.click(screen.getByRole('button', { name: 'Giám thị' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Sửa' }));
    fireEvent.click(screen.getByRole('button', { name: 'Cập nhật giám thị' }));
    await waitFor(() => expect(vi.mocked(httpRequest)).toHaveBeenCalledWith('/delivery/proctor-assignments/6001', expect.objectContaining({ method: 'PATCH' })));
  });

  test('cancelled imported student is removed from active sitting assignments', async () => {
    const base = vi.mocked(httpRequest).getMockImplementation();
    let assignmentStatus = 'ASSIGNED';
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path.startsWith('/delivery/exam-sittings/2000/assignments')) {
        return list([{ exam_assignment_id: 4001, exam_sitting_id: 2000, student_id: 1, student_code: 'SV001', student_name: 'Nguyá»…n A', assignment_status: assignmentStatus }]);
      }
      if (path === '/delivery/exam-assignments/4001' && init?.method === 'PATCH') {
        assignmentStatus = String(JSON.parse(String(init.body)).assignment_status || assignmentStatus);
        return ok({ exam_assignment_id: 4001, exam_sitting_id: 2000, student_id: 1, student_code: 'SV001', student_name: 'Nguyá»…n A', assignment_status: assignmentStatus });
      }
      return base ? base(path, init) : ok({});
    });

    render(<ExamSetupPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Sinh viên dự thi' }));
    await screen.findByText('SV001');

    fireEvent.click(screen.getByRole('button', { name: 'Hủy' }));

    await waitFor(() =>
      expect(vi.mocked(httpRequest)).toHaveBeenCalledWith(
        '/delivery/exam-assignments/4001',
        expect.objectContaining({ method: 'PATCH', body: expect.stringContaining('"assignment_status":"CANCELLED"') })
      )
    );
    await waitFor(() => expect(screen.queryByText('SV001')).not.toBeInTheDocument());
  });

  test('publish panel moves a ready sitting from DRAFT to READY then OPEN', async () => {
    let sittingStatus = 'DRAFT';
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path.startsWith('/master-data/exams?page')) return list([{ exam_id: 11, exam_code: 'ACC101', exam_name: 'Kế toán', class_section_id: 21, assessment_type_id: 1 }]);
      if (path.startsWith('/master-data/class-sections')) return list([{ class_section_id: 21, class_code: 'ACC101-01', class_name: 'Lớp 1' }]);
      if (path.startsWith('/master-data/assessment-types')) return list([{ assessment_type_id: 1, type_code: 'MIDTERM', type_name: 'Giữa kỳ' }]);
      if (path.startsWith('/master-data/facilities/rooms')) return list([{ room_id: 31, room_code: 'D13', room_name: 'Phòng D13', capacity: 40 }]);
      if (path.startsWith('/master-data/rooms/31/stations')) return list([{ station_id: 91, room_id: 31, room_code: 'D13', station_code: 'A1' }]);
      if (path.startsWith('/master-data/facilities/stations')) return list([{ station_id: 91, room_id: 31, room_code: 'D13', station_code: 'A1' }]);
      if (path.startsWith('/master-data/students')) return list([{ student_id: 1, student_code: 'SV001', full_name: 'Nguyễn A' }]);
      if (path.startsWith('/master-data/instructors')) return list([{ instructor_id: 2, user_id: 12, username: 'gv001', instructor_code: 'GV001', full_name: 'Giảng viên A' }]);
      if (path.endsWith('/status')) return ok({ module: 'ok', status: 'ok', ready: true });
      if (path.startsWith('/master-data/exams/11/versions')) return list([{ exam_version_id: 101, exam_id: 11, exam_code: 'ACC101', version_label: 'V1', version_no: 1, status: 'PUBLISHED' }]);
      if (path.startsWith('/master-data/exam-versions/101/delivery-profile')) return ok({ exam_version_delivery_profile_id: 1, exam_version_id: 101, delivery_mode: 'FORM_BASED', work_mode: 'INDIVIDUAL', primary_answer_source: 'SEALED_TEXT_ANSWER', requires_capture: false, capture_timing: 'NONE', allow_mixed_question_sources: false, form_autosave_enabled: true, database_work_mode: 'NONE', status: 'ACTIVE' });
      if (path.startsWith('/master-data/exam-versions/101/question-grading-profiles')) return list([]);
      if (path.startsWith('/master-data/exam-versions/101/questions')) return ok({
        items: [{ question_template_id: 2001, question_no: 1, question_title: 'Câu 1', prompt_text: 'SQL', question_type: 'TEXTBOX_SQL', response_mode: 'SQL_TEXT', render_component: 'SQL_EDITOR', input_source: 'SEALED_TEXT_ANSWER', grading_engine_code: 'SQL_RESULT_COMPARATOR', comparison_method: 'EXACT_RESULT_SET', max_score: 10, status: 'ACTIVE', required: true, mcq_options: [], has_expected_answer: true }],
        readiness_summary: { ready: true, missing_items: [] },
      });
      if (path === '/delivery/exam-sittings/2000/status' && init?.method === 'POST') {
        sittingStatus = String(JSON.parse(String(init.body)).sitting_status);
        return ok({ exam_sitting_id: 2000, exam_version_id: 101, exam_version_label: 'V1', sitting_code: 'S0', sitting_name: 'Ca 0', scheduled_start_at: '2026-06-10T01:00:00Z', scheduled_end_at: '2026-06-10T03:00:00Z', sitting_status: sittingStatus });
      }
      if (path === '/delivery/exam-sittings/2000/readiness') {
        return ok({
          exam_sitting_id: 2000,
          exam_version_id: 101,
          ready: true,
          blockers: [],
          warnings: [],
          counts: { assignment_count: 1, room_count: 1, station_assignment_count: 1, proctor_count: 1, question_source_count: 1, paper_asset_count: 0 },
        });
      }
      if (path === '/delivery/exam-sittings/2000/prepare' && init?.method === 'POST') {
        return ok({ prepared: true, exam_sitting_id: 2000, exam_version_id: 101, assignment_count: 1, question_count: 1, created_session_count: 1, reused_session_count: 0, created_instance_count: 1, reused_instance_count: 0, created_generated_question_count: 1 });
      }
      if (path === '/delivery/exam-sittings') return list([{ exam_sitting_id: 2000, exam_version_id: 101, exam_version_label: 'V1', sitting_code: 'S0', sitting_name: 'Ca 0', scheduled_start_at: '2026-06-10T01:00:00Z', scheduled_end_at: '2026-06-10T03:00:00Z', sitting_status: sittingStatus }]);
      if (path.startsWith('/delivery/exam-sittings/2000/rooms')) return list([{ exam_sitting_room_id: 3001, exam_sitting_id: 2000, room_id: 31, room_code: 'D13', room_name: 'Phòng D13', room_status: 'READY' }]);
      if (path.startsWith('/delivery/exam-sittings/2000/assignments')) return list([{ exam_assignment_id: 4001, exam_sitting_id: 2000, student_id: 1, student_code: 'SV001', student_name: 'Nguyễn A', assignment_status: 'ASSIGNED' }]);
      if (path.startsWith('/delivery/exam-sittings/2000/seating-plan')) return list([{ station_assignment_id: 5001, exam_assignment_id: 4001, exam_sitting_room_id: 3001, station_id: 91, station_code: 'A1', status: 'ASSIGNED' }]);
      if (path.startsWith('/delivery/exam-sitting-rooms/3001/proctors')) return list([{ proctor_assignment_id: 6001, exam_sitting_room_id: 3001, proctor_user_id: 12, proctor_display_name: 'Giảng viên A', proctor_role: 'ROOM_PROCTOR', status: 'ASSIGNED' }]);
      return ok({});
    });

    render(<ExamSetupPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Phát hành / Mở ca thi' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Đánh dấu READY' }));
    await waitFor(() =>
      expect(vi.mocked(httpRequest)).toHaveBeenCalledWith(
        '/delivery/exam-sittings/2000/status',
        expect.objectContaining({ method: 'POST', body: expect.stringContaining('"sitting_status":"READY"') })
      )
    );

    await waitFor(() => expect(screen.getByRole('button', { name: 'Mở ca thi' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Mở ca thi' }));
    await waitFor(() =>
      expect(vi.mocked(httpRequest)).toHaveBeenCalledWith(
        '/delivery/exam-sittings/2000/status',
        expect.objectContaining({ method: 'POST', body: expect.stringContaining('"sitting_status":"OPEN"') })
      )
    );
  });
});
