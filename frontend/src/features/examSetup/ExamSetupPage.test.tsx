import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { ExamSetupPage } from './ExamSetupPage';
import { httpRequest } from '../../shared/api/httpClient';

vi.mock('../../shared/api/httpClient', () => ({ httpRequest: vi.fn() }));

const ok = <T,>(data: T) => ({ ok: true as const, success: true as const, data, error: null, message: null });
const list = (items: Array<Record<string, unknown>>) => ok({ items, pagination: { page: 1, page_size: 20, total_items: items.length } });

function navLabels() {
  return screen
    .getAllByRole('button')
    .filter((button) => button.className.includes('master-data-tab'))
    .map((button) => button.textContent || '');
}

describe('ExamSetupPage workflow', () => {
  beforeEach(() => {
    vi.mocked(httpRequest).mockReset();
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === '/master-data/exams' && init?.method === 'POST') {
        return ok({ exam_id: 12, exam_code: 'ACC102', exam_name: 'Kế toán 2', class_section_id: 21, assessment_type_id: 1, exam_status: 'DRAFT' });
      }
      if (path === '/master-data/exams/11' && init?.method === 'PATCH') {
        return ok({ exam_id: 11, exam_code: 'ACC101', exam_name: 'Kế toán 1', class_section_id: 21, assessment_type_id: 1, exam_status: 'DRAFT' });
      }
      if (path.startsWith('/master-data/exams?page')) {
        return list([{ exam_id: 11, exam_code: 'ACC101', exam_name: 'Kế toán 1', class_section_id: 21, assessment_type_id: 1, exam_status: 'DRAFT' }]);
      }
      if (path.startsWith('/master-data/class-sections')) return list([{ class_section_id: 21, class_code: 'ACC101-01', class_name: 'Lớp 01' }]);
      if (path.startsWith('/master-data/assessment-types')) return list([{ assessment_type_id: 1, type_code: 'MIDTERM', type_name: 'Giữa kỳ' }]);
      if (path.startsWith('/master-data/facilities/rooms')) return list([{ room_id: 31, room_code: 'LAB-A101', room_name: 'Phòng A101', capacity: 40 }]);
      if (path.startsWith('/master-data/facilities/stations')) {
        return list([
          { station_id: 91, room_code: 'LAB-A101', station_code: 'A101-01' },
          { station_id: 92, room_code: 'LAB-A101', station_code: 'A101-02' },
        ]);
      }
      if (path.startsWith('/master-data/students')) return list([{ student_id: 1, student_code: 'SV001', full_name: 'Nguyễn Minh An' }]);
      if (path.startsWith('/master-data/instructors')) return list([{ instructor_id: 2, user_id: 12, username: 'gv001', instructor_code: 'GV001', full_name: 'Phạm Quang Huy' }]);
      if (path.endsWith('/status')) return ok({ module: path.split('/')[1], status: 'ok', ready: true });

      if (path === '/master-data/exams/11/versions' && init?.method === 'POST') {
        return ok({ exam_version_id: 102, exam_id: 11, exam_code: 'ACC101', version_label: 'V2', duration_seconds: 3600, total_score: 10, randomization_mode: 'FIXED', status: 'DRAFT' });
      }
      if (path === '/master-data/exam-versions/101' && init?.method === 'PATCH') {
        return ok({ exam_version_id: 101, exam_id: 11, exam_code: 'ACC101', version_label: 'V1', duration_seconds: 5400, total_score: 10, randomization_mode: 'FIXED', status: 'DRAFT' });
      }
      if (path.startsWith('/master-data/exams/11/versions/101/paper-assets')) return list([]);
      if (path.startsWith('/master-data/exams/11/versions')) {
        return list([
          { exam_version_id: 101, exam_id: 11, exam_code: 'ACC101', version_no: 1, version_label: 'V1', duration_seconds: 5400, total_score: 10, randomization_mode: 'FIXED', status: 'DRAFT' },
          { exam_version_id: 102, exam_id: 11, exam_code: 'ACC101', version_no: 2, version_label: 'V2', duration_seconds: 3600, total_score: 10, randomization_mode: 'FIXED', status: 'DRAFT' },
        ]);
      }
      if (path.startsWith('/master-data/exam-versions/101/delivery-profile')) {
        if (init?.method === 'PUT') {
          return ok({ exam_version_delivery_profile_id: 1, exam_version_id: 101, delivery_mode: 'FILE_BASED', work_mode: 'INDIVIDUAL', primary_answer_source: 'FILE_ARTIFACT', requires_capture: false, capture_timing: 'NONE', allow_mixed_question_sources: false, form_autosave_enabled: false, database_work_mode: 'NONE', status: 'ACTIVE' });
        }
        return ok({ exam_version_delivery_profile_id: 1, exam_version_id: 101, delivery_mode: 'FORM_BASED', work_mode: 'INDIVIDUAL', primary_answer_source: 'SEALED_TEXT_ANSWER', requires_capture: false, capture_timing: 'NONE', allow_mixed_question_sources: false, form_autosave_enabled: true, database_work_mode: 'NONE', status: 'ACTIVE' });
      }
      if (path.startsWith('/master-data/exam-versions/101/question-grading-profiles')) return list([]);
      if (path === '/master-data/exam-versions/101/questions' && init?.method === 'POST') {
        const body = JSON.parse(String(init.body));
        return ok({ question_template_id: 3000 + Number(body.question_no), question_grading_profile_id: 8001, question_no: body.question_no, question_title: body.question_title, prompt_text: body.prompt_text, question_type: body.question_type, response_mode: body.response_mode, render_component: body.render_component, input_source: 'SEALED_TEXT_ANSWER', grading_engine_code: body.grading_engine_code, comparison_method: body.comparison_method, max_score: body.max_score, status: body.status, required: body.required, mcq_options: body.mcq_options ?? [], has_expected_answer: Boolean(body.expected_answer_text) });
      }
      if (path === '/master-data/exam-versions/101/questions' && !init?.method) {
        return ok({
          items: [{ question_template_id: 2001, question_grading_profile_id: 8001, question_no: 1, question_title: 'Câu 1', prompt_text: 'Nhập câu trả lời', question_type: 'TEXTAREA', response_mode: 'LONG_TEXT', render_component: 'TEXTAREA', input_source: 'SEALED_TEXT_ANSWER', grading_engine_code: 'MANUAL_RUBRIC', comparison_method: 'MANUAL_RUBRIC', max_score: 1, status: 'ACTIVE', required: true, mcq_options: [], has_expected_answer: false }],
          readiness_summary: { ready: false, missing_items: [{ code: 'question_expected_answer_missing' }] },
        });
      }
      if (path.startsWith('/master-data/exam-versions/102/questions')) return ok({ items: [], readiness_summary: { ready: false, missing_items: [] } });

      if (path === '/delivery/exam-sittings/2000/exam-version' && init?.method === 'PATCH') {
        return ok({ exam_sitting_id: 2000, exam_version_id: 102, exam_version_label: 'V2', exam_id: 11, sitting_code: 'S0', sitting_name: 'Ca 0', scheduled_start_at: '2026-06-10T01:00:00Z', scheduled_end_at: '2026-06-10T03:00:00Z', sitting_status: 'DRAFT' });
      }
      if (path === '/delivery/exam-sittings' && init?.method === 'POST') {
        return ok({ exam_sitting_id: 2001, exam_version_id: 101, exam_version_label: 'V1', exam_id: 11, sitting_code: 'S1', sitting_name: 'Ca 1', scheduled_start_at: '2026-06-10T01:00:00Z', scheduled_end_at: '2026-06-10T03:00:00Z', sitting_status: 'DRAFT' });
      }
      if (path === '/delivery/exam-sittings/2000' && init?.method === 'PATCH') {
        return ok({ exam_sitting_id: 2000, exam_version_id: 101, exam_version_label: 'V1', exam_id: 11, sitting_code: 'S0', sitting_name: 'Ca 0 edit', scheduled_start_at: '2026-06-10T01:00:00Z', scheduled_end_at: '2026-06-10T03:00:00Z', sitting_status: 'DRAFT' });
      }
      if (path === '/delivery/exam-assignments/import-by-code' && init?.method === 'POST') {
        return ok({ created: [{ exam_assignment_id: 4002, exam_sitting_id: 2000, student_id: 1, student_code: 'SV002', student_name: 'Trần Bình', assignment_status: 'ASSIGNED' }], errors: [], created_count: 1, error_count: 0 });
      }
      if (path === '/delivery/exam-sittings') return list([{ exam_sitting_id: 2000, exam_version_id: 101, exam_version_label: 'V1', exam_id: 11, exam_code: 'ACC101', exam_name: 'Kế toán 1', sitting_code: 'S0', sitting_name: 'Ca 0', scheduled_start_at: '2026-06-10T01:00:00Z', scheduled_end_at: '2026-06-10T03:00:00Z', sitting_status: 'DRAFT' }]);
      if (path === '/delivery/exam-sittings/2000/readiness') {
        return ok({
          exam_sitting_id: 2000,
          exam_version_id: 101,
          ready: false,
          blockers: [{ code: 'assignment_missing', message: 'Chưa đủ cấu hình để mở ca thi.' }],
          warnings: [],
          counts: { assignment_count: 1, room_count: 1, station_assignment_count: 1, proctor_count: 1, question_source_count: 1, paper_asset_count: 0 },
        });
      }
      if (path.startsWith('/delivery/exam-sittings/2000/rooms')) return list([{ exam_sitting_room_id: 3001, exam_sitting_id: 2000, room_id: 31, room_code: 'LAB-A101', room_name: 'Phòng A101', room_status: 'PLANNED' }]);
      if (path.startsWith('/delivery/exam-sittings/2000/assignments')) return list([{ exam_assignment_id: 4001, exam_sitting_id: 2000, student_id: 1, student_code: 'SV001', student_name: 'Nguyễn Minh An', assignment_status: 'ASSIGNED' }]);
      if (path.startsWith('/delivery/exam-sittings/2000/seating-plan')) return list([{ station_assignment_id: 5001, exam_assignment_id: 4001, exam_sitting_room_id: 3001, station_id: 91, station_code: 'A101-01', student_code: 'SV001', student_name: 'Nguyễn Minh An', status: 'ASSIGNED' }]);
      if (path.startsWith('/delivery/exam-sitting-rooms/3001/proctors')) return list([{ proctor_assignment_id: 6001, exam_sitting_room_id: 3001, proctor_user_id: 12, proctor_role: 'ROOM_PROCTOR', status: 'ASSIGNED' }]);
      return ok({});
    });
  });

  test('Workflow A and Workflow B appear in the required order', async () => {
    render(<ExamSetupPage />);
    await screen.findByRole('button', { name: 'Đề gốc' });
    const labels = navLabels();
    expect(labels.indexOf('Đề gốc')).toBeLessThan(labels.indexOf('Phiên bản đề'));
    expect(labels.indexOf('Phiên bản đề')).toBeLessThan(labels.indexOf('Dạng đề'));
    expect(labels.indexOf('Dạng đề')).toBeLessThan(labels.indexOf('Tài liệu đề thi'));
    expect(labels.indexOf('Tài liệu đề thi')).toBeLessThan(labels.indexOf('Câu hỏi'));
    expect(labels.indexOf('Câu hỏi')).toBeLessThan(labels.indexOf('Form làm bài'));
    expect(labels.indexOf('Form làm bài')).toBeLessThan(labels.indexOf('Cấu hình chấm'));
    expect(labels.indexOf('Cấu hình chấm')).toBeLessThan(labels.indexOf('Đáp án'));

    expect(labels.indexOf('Ca thi')).toBeLessThan(labels.indexOf('Phiên bản đề áp dụng'));
    expect(labels.indexOf('Phiên bản đề áp dụng')).toBeLessThan(labels.indexOf('Sinh viên dự thi'));
    expect(labels.indexOf('Sinh viên dự thi')).toBeLessThan(labels.indexOf('Phòng thi'));
    expect(labels.indexOf('Phòng thi')).toBeLessThan(labels.indexOf('Xếp máy'));
    expect(labels.indexOf('Xếp máy')).toBeLessThan(labels.indexOf('Giám thị'));
    expect(labels.indexOf('Giám thị')).toBeLessThan(labels.indexOf('Kiểm tra độ sẵn sàng'));
    expect(labels.indexOf('Kiểm tra độ sẵn sàng')).toBeLessThan(labels.indexOf('Phát hành / Mở ca thi'));
  });

  test('exam setup renders compact workflow shell with toolbar and status strip', async () => {
    render(<ExamSetupPage />);

    expect(await screen.findByTestId('exam-setup-page')).toBeInTheDocument();
    expect(screen.getByTestId('exam-setup-compact-toolbar')).toBeInTheDocument();
    expect(screen.getByText(/Workflow:/)).toBeInTheDocument();
    expect(screen.getByText('Exam status')).toBeInTheDocument();
    expect(screen.getByText('Version status')).toBeInTheDocument();
    expect(screen.getByText('Sitting status')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Tải lại API' })).toBeInTheDocument();
  });

  test('hides oversized API connection diagnostics outside debug mode', async () => {
    render(<ExamSetupPage />);

    await screen.findByTestId('exam-setup-compact-toolbar');
    expect(screen.queryByRole('heading', { name: 'Tình trạng nối API' })).not.toBeInTheDocument();
  });

  test('version creation does not require paper upload and paper upload is isolated', async () => {
    render(<ExamSetupPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Phiên bản đề' }));
    expect(screen.queryByTestId('paper-upload-input')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Nhập phiên bản mới' }));
    fireEvent.change(screen.getByLabelText('Tên version'), { target: { value: 'V2' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tạo version' }));
    await waitFor(() => expect(vi.mocked(httpRequest)).toHaveBeenCalledWith('/master-data/exams/11/versions', expect.objectContaining({ method: 'POST' })));

    fireEvent.click(screen.getByRole('button', { name: 'Tài liệu đề thi' }));
    expect(await screen.findByTestId('paper-upload-input')).toBeInTheDocument();
    expect(screen.getByText('Tài liệu PDF/ảnh là tùy chọn, chỉ bắt buộc với dạng đề hiển thị bằng tài liệu.')).toBeInTheDocument();
  });

  test('delivery type can save FORM_QUESTION_BASED through the API storage enum', async () => {
    render(<ExamSetupPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Dạng đề' }));

    fireEvent.change(await screen.findByLabelText('Dạng đề'), { target: { value: 'FORM_QUESTION_BASED' } });
    fireEvent.click(screen.getByTestId('save-delivery-content-type'));

    await waitFor(() =>
      expect(vi.mocked(httpRequest)).toHaveBeenCalledWith(
        '/master-data/exam-versions/101/delivery-profile',
        expect.objectContaining({
          method: 'PUT',
          body: expect.stringContaining('"delivery_mode":"FORM_BASED"'),
        })
      )
    );
    const putCall = vi
      .mocked(httpRequest)
      .mock.calls.find(([path, init]) => path === '/master-data/exam-versions/101/delivery-profile' && init?.method === 'PUT');
    expect(String(putCall?.[1]?.body)).toContain('"primary_answer_source":"SEALED_FORM_ANSWER"');
    expect(String(putCall?.[1]?.body)).toContain('"delivery_content_type":"FORM_QUESTION_BASED"');
    expect(String(putCall?.[1]?.body)).toContain('"paper_asset_required":false');
  });

  test('delivery type can save VISUAL_PAPER_BASED with manual rubric modality metadata', async () => {
    render(<ExamSetupPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Dạng đề' }));

    expect(screen.getByText('Đề PDF/ảnh, sinh viên xem đề và bài được chấm thủ công bằng rubric.')).toBeInTheDocument();
    fireEvent.change(await screen.findByLabelText('Dạng đề'), { target: { value: 'VISUAL_PAPER_BASED' } });
    fireEvent.click(screen.getByTestId('save-delivery-content-type'));

    await waitFor(() =>
      expect(vi.mocked(httpRequest)).toHaveBeenCalledWith(
        '/master-data/exam-versions/101/delivery-profile',
        expect.objectContaining({
          method: 'PUT',
          body: expect.stringContaining('"delivery_mode":"FILE_BASED"'),
        })
      )
    );
    const putCall = vi
      .mocked(httpRequest)
      .mock.calls.find(([path, init]) => path === '/master-data/exam-versions/101/delivery-profile' && init?.method === 'PUT');
    expect(String(putCall?.[1]?.body)).toContain('"primary_answer_source":"FILE_ARTIFACT"');
    expect(String(putCall?.[1]?.body)).toContain('"delivery_content_type":"VISUAL_PAPER_BASED"');
    expect(String(putCall?.[1]?.body)).toContain('"exam_modality":"VISUAL_PAPER_BASED"');
    expect(String(putCall?.[1]?.body)).toContain('"modality_code":"VISUAL_PAPER_BASED"');
    expect(String(putCall?.[1]?.body)).toContain('"grading_policy":"MANUAL_RUBRIC"');
  });

  test('question section supports generated editable panels and saved panels', async () => {
    render(<ExamSetupPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Câu hỏi' }));
    await screen.findByRole('heading', { name: 'Câu 1' });
    expect(screen.getByText('Đã lưu', { exact: false })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Số câu hỏi'), { target: { value: '3' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tạo khung câu hỏi' }));
    await screen.findByRole('heading', { name: 'Câu 3' });
    expect(screen.getByTestId('question-panels-generated')).toHaveClass('question-panel-list');
    expect(screen.getByTestId('question-preset-intro')).toHaveTextContent('TEXTBOX_SQL');
    expect(screen.getByTestId('question-panels-generated')).not.toHaveTextContent('Tóm tắt preset');
    expect(screen.getByTestId('panel-response-profile-1')).toHaveTextContent('Form làm bài');
    expect(screen.getByTestId('panel-response-profile-1')).toHaveTextContent('Ô nhập bài tự luận dạng văn bản dài');
    expect(screen.queryByLabelText('question_no')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('response_mode')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('render_component')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Hủy kích hoạt (DRAFT)' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Thêm câu hỏi' })).not.toBeInTheDocument();
    expect(screen.queryByText('Phiên bản đề đã chọn không còn hợp lệ. Vui lòng chọn lại phiên bản đề.')).not.toBeInTheDocument();
  });

  test('saving one generated question panel keeps remaining draft panels after reload', async () => {
    const base = vi.mocked(httpRequest).getMockImplementation();
    const questionItems: Array<Record<string, unknown>> = [
      { question_template_id: 2001, question_grading_profile_id: 8001, question_no: 1, question_title: 'Câu 1', prompt_text: 'Nhập câu trả lời', question_type: 'TEXTAREA', response_mode: 'LONG_TEXT', render_component: 'TEXTAREA', input_source: 'SEALED_TEXT_ANSWER', grading_engine_code: 'MANUAL_RUBRIC', comparison_method: 'MANUAL_RUBRIC', max_score: 1, status: 'ACTIVE', required: true, mcq_options: [], has_expected_answer: false },
    ];
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === '/master-data/exam-versions/101/questions' && init?.method === 'POST') {
        const body = JSON.parse(String(init.body));
        const item = {
          question_template_id: 3000 + Number(body.question_no),
          question_grading_profile_id: 8100 + Number(body.question_no),
          question_no: body.question_no,
          question_title: body.question_title,
          prompt_text: body.prompt_text,
          question_type: body.question_type,
          response_mode: body.response_mode,
          render_component: body.render_component,
          input_source: 'SEALED_TEXT_ANSWER',
          grading_engine_code: body.grading_engine_code,
          comparison_method: body.comparison_method,
          max_score: body.max_score,
          status: body.status,
          required: body.required,
          mcq_options: body.mcq_options ?? [],
          has_expected_answer: Boolean(body.expected_answer_text),
        };
        questionItems.push(item);
        return ok(item);
      }
      if (path === '/master-data/exam-versions/101/questions' && !init?.method) {
        return ok({ items: questionItems, readiness_summary: { ready: false, missing_items: [] } });
      }
      return base ? base(path, init) : ok({});
    });

    render(<ExamSetupPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Câu hỏi' }));
    await screen.findByRole('heading', { name: 'Câu 1' });
    fireEvent.change(screen.getByLabelText('Số câu hỏi'), { target: { value: '5' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tạo khung câu hỏi' }));
    await screen.findByRole('heading', { name: 'Câu 5' });

    fireEvent.change(screen.getAllByLabelText('prompt_text')[1], { target: { value: 'Nội dung câu 2' } });
    fireEvent.change(screen.getAllByLabelText('Loại câu hỏi')[1], { target: { value: 'TEXTBOX_SQL' } });
    expect(screen.getByTestId('panel-response-profile-2')).toHaveTextContent('Ô nhập câu lệnh SQL cho sinh viên');
    fireEvent.change(screen.getByLabelText('Đáp án mẫu / câu trả lời đúng (admin-only)'), { target: { value: 'SELECT 1;' } });
    fireEvent.click(screen.getAllByRole('button', { name: 'Lưu câu hỏi' })[1]);

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Câu 5' })).toBeInTheDocument());
    expect(screen.getByDisplayValue('SELECT 1;')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Câu 3' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Câu 4' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Câu 5' })).toBeInTheDocument();
  });

  test('question section accepts version list rows without exam_id without stale-version error', async () => {
    const base = vi.mocked(httpRequest).getMockImplementation();
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path.startsWith('/master-data/exams/11/versions')) {
        return list([{ exam_version_id: 101, version_no: 1, version_label: 'V1', duration_seconds: 5400, total_score: 10, randomization_mode: 'FIXED', status: 'DRAFT' }]);
      }
      return base ? base(path, init) : ok({});
    });
    render(<ExamSetupPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Câu hỏi' }));
    await screen.findByRole('heading', { name: 'Câu 1' });
    expect(screen.queryByText('Phiên bản đề đã chọn không còn hợp lệ. Vui lòng chọn lại phiên bản đề.')).not.toBeInTheDocument();
  });

  test('admin can explicitly switch the working exam version in question authoring', async () => {
    render(<ExamSetupPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Câu hỏi' }));
    const selector = await screen.findByLabelText('Phiên bản đề đang soạn');
    fireEvent.change(selector, { target: { value: '102' } });
    await waitFor(() => expect(vi.mocked(httpRequest)).toHaveBeenCalledWith('/master-data/exam-versions/102/questions'));
    expect(screen.queryByText('Phiên bản đề đã chọn không còn hợp lệ. Vui lòng chọn lại phiên bản đề.')).not.toBeInTheDocument();
  });

  test('does not call question APIs when no version is selected', async () => {
    const base = vi.mocked(httpRequest).getMockImplementation();
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path.startsWith('/master-data/exams/11/versions')) return list([]);
      if (path === '/delivery/exam-sittings') return list([]);
      return base ? base(path, init) : ok({});
    });
    vi.mocked(httpRequest).mockClear();
    render(<ExamSetupPage />);
    const questionCallsBefore = vi.mocked(httpRequest).mock.calls.filter(([path]) => String(path).includes('/questions')).length;
    fireEvent.click(await screen.findByRole('button', { name: 'Câu hỏi' }));
    await screen.findByText('Vui lòng chọn hoặc tạo phiên bản đề trước.');
    const questionCallsAfter = vi.mocked(httpRequest).mock.calls.filter(([path]) => String(path).includes('/questions')).length;
    expect(questionCallsAfter).toBe(questionCallsBefore);
  });

  test('selected sitting drives appliedExamVersionId and assignment uses the sitting endpoint', async () => {
    render(<ExamSetupPage />);
    await screen.findByText('S0 - Ca 0 · DRAFT');
    expect(screen.getByText('V1 · DRAFT')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Phiên bản đề áp dụng' }));
    fireEvent.change(await screen.findByLabelText('Phiên bản đề áp dụng'), { target: { value: '102' } });
    fireEvent.click(screen.getByRole('button', { name: 'Gắn phiên bản đề cho ca thi' }));
    await waitFor(() =>
      expect(vi.mocked(httpRequest)).toHaveBeenCalledWith(
        '/delivery/exam-sittings/2000/exam-version',
        expect.objectContaining({ method: 'PATCH', body: JSON.stringify({ exam_version_id: 102 }) })
      )
    );
  });

  test('editing existing sitting keeps lifecycle status read-only and does not PATCH status fields', async () => {
    render(<ExamSetupPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Ca thi' }));

    const lifecycleStatusField = await screen.findByLabelText('Trạng thái (vòng đời)');
    expect(lifecycleStatusField).toBeDisabled();
    expect(screen.getByText('Đổi trạng thái bằng khu vực Chuẩn bị/Mở ca thi.')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Tên ca thi'), { target: { value: 'Ca 0 cập nhật' } });
    fireEvent.click(screen.getByRole('button', { name: 'Cập nhật ca thi' }));

    await waitFor(() =>
      expect(vi.mocked(httpRequest)).toHaveBeenCalledWith(
        '/delivery/exam-sittings/2000',
        expect.objectContaining({ method: 'PATCH' })
      )
    );
    const patchCall = vi
      .mocked(httpRequest)
      .mock.calls.find(([path, init]) => path === '/delivery/exam-sittings/2000' && init?.method === 'PATCH');
    const patchBody = JSON.parse(String(patchCall?.[1]?.body ?? '{}')) as Record<string, unknown>;
    expect(patchBody).not.toHaveProperty('status');
    expect(patchBody).not.toHaveProperty('sitting_status');
    expect(await screen.findByText('Đã cập nhật thông tin ca thi.')).toBeInTheDocument();
  });

  test('clicking READY calls POST /delivery/exam-sittings/{id}/status with sitting_status READY', async () => {
    const base = vi.mocked(httpRequest).getMockImplementation();
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
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
      if (path === '/delivery/exam-sittings/2000/status' && init?.method === 'POST') {
        return ok({
          exam_sitting_id: 2000,
          exam_version_id: 101,
          exam_version_label: 'V1',
          exam_id: 11,
          sitting_code: 'S0',
          sitting_name: 'Ca 0',
          scheduled_start_at: '2026-06-10T01:00:00Z',
          scheduled_end_at: '2026-06-10T03:00:00Z',
          sitting_status: 'READY',
        });
      }
      return base ? base(path, init) : ok({});
    });

    render(<ExamSetupPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Phát hành / Mở ca thi' }));

    await waitFor(() => expect(screen.getByRole('button', { name: 'Đánh dấu READY' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Đánh dấu READY' }));

    await waitFor(() =>
      expect(vi.mocked(httpRequest)).toHaveBeenCalledWith(
        '/delivery/exam-sittings/2000/status',
        expect.objectContaining({ method: 'POST', body: expect.stringContaining('"sitting_status":"READY"') })
      )
    );
  });

  test('successful READY transition updates publish badge/dropdown and sitting form status immediately', async () => {
    const base = vi.mocked(httpRequest).getMockImplementation();
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
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
      if (path === '/delivery/exam-sittings/2000/status' && init?.method === 'POST') {
        return ok({
          exam_sitting_id: 2000,
          exam_version_id: 101,
          exam_version_label: 'V1',
          exam_id: 11,
          sitting_code: 'S0',
          sitting_name: 'Ca 0',
          scheduled_start_at: '2026-06-10T01:00:00Z',
          scheduled_end_at: '2026-06-10T03:00:00Z',
          sitting_status: 'READY',
        });
      }
      return base ? base(path, init) : ok({});
    });

    render(<ExamSetupPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Phát hành / Mở ca thi' }));

    await waitFor(() => expect(screen.getByRole('button', { name: 'Đánh dấu READY' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Đánh dấu READY' }));

    expect(await screen.findByText('Đã chuyển ca thi sang READY.')).toBeInTheDocument();
    expect(await screen.findByRole('option', { name: 'S0 - Ca 0 · READY' })).toBeInTheDocument();
    expect(screen.getByTestId('publish-open-section')).toHaveTextContent('READY');

    fireEvent.click(screen.getByRole('button', { name: 'Ca thi' }));
    expect(await screen.findByLabelText('Trạng thái (vòng đời)')).toHaveValue('READY');
  });

  test('reloaded sitting list preserves READY when backend returns READY', async () => {
    const base = vi.mocked(httpRequest).getMockImplementation();
    let listCalls = 0;
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === '/delivery/exam-sittings') {
        listCalls += 1;
        return list([
          {
            exam_sitting_id: 2000,
            exam_version_id: 101,
            exam_version_label: 'V1',
            exam_id: 11,
            exam_code: 'ACC101',
            exam_name: 'Kế toán 1',
            sitting_code: 'S0',
            sitting_name: 'Ca 0',
            scheduled_start_at: '2026-06-10T01:00:00Z',
            scheduled_end_at: '2026-06-10T03:00:00Z',
            sitting_status: listCalls > 1 ? 'READY' : 'DRAFT',
          },
        ]);
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
      if (path === '/delivery/exam-sittings/2000/status' && init?.method === 'POST') {
        return ok({
          exam_sitting_id: 2000,
          exam_version_id: 101,
          exam_version_label: 'V1',
          exam_id: 11,
          sitting_code: 'S0',
          sitting_name: 'Ca 0',
          scheduled_start_at: '2026-06-10T01:00:00Z',
          scheduled_end_at: '2026-06-10T03:00:00Z',
          sitting_status: 'READY',
        });
      }
      return base ? base(path, init) : ok({});
    });

    render(<ExamSetupPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Phát hành / Mở ca thi' }));

    await waitFor(() => expect(screen.getByRole('button', { name: 'Đánh dấu READY' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Đánh dấu READY' }));
    await screen.findByText('Đã chuyển ca thi sang READY.');

    fireEvent.click(screen.getByRole('button', { name: 'Tải lại API' }));

    await waitFor(() => expect(screen.getByRole('option', { name: 'S0 - Ca 0 · READY' })).toBeInTheDocument());
    expect(listCalls).toBeGreaterThan(1);
  });

  test('applied version selector keeps missing current version and still lets admin assign another visible version', async () => {
    const base = vi.mocked(httpRequest).getMockImplementation();
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === '/delivery/exam-sittings') {
        return list([{ exam_sitting_id: 2000, exam_version_id: 999, exam_version_label: 'Legacy', exam_id: 99, exam_code: 'OLD', exam_name: 'Old exam', sitting_code: 'S0', sitting_name: 'Ca 0', scheduled_start_at: '2026-06-10T01:00:00Z', scheduled_end_at: '2026-06-10T03:00:00Z', sitting_status: 'DRAFT' }]);
      }
      if (path === '/delivery/exam-sittings/2000/exam-version' && init?.method === 'PATCH') {
        return ok({ exam_sitting_id: 2000, exam_version_id: 101, exam_version_label: 'V1', exam_id: 11, sitting_code: 'S0', sitting_name: 'Ca 0', scheduled_start_at: '2026-06-10T01:00:00Z', scheduled_end_at: '2026-06-10T03:00:00Z', sitting_status: 'DRAFT' });
      }
      return base ? base(path, init) : ok({});
    });

    render(<ExamSetupPage />);
    await screen.findByText('S0 - Ca 0 · DRAFT');
    fireEvent.click(screen.getByRole('button', { name: 'Phiên bản đề áp dụng' }));
    expect((await screen.findAllByText('OLD - Legacy')).length).toBeGreaterThan(0);

    const selector = screen.getByLabelText('Phiên bản đề áp dụng');
    expect(selector).toHaveValue('999');
    fireEvent.change(selector, { target: { value: '101' } });
    fireEvent.click(screen.getByRole('button', { name: 'Gắn phiên bản đề cho ca thi' }));

    await waitFor(() =>
      expect(vi.mocked(httpRequest)).toHaveBeenCalledWith(
        '/delivery/exam-sittings/2000/exam-version',
        expect.objectContaining({ method: 'PATCH', body: JSON.stringify({ exam_version_id: 101 }) })
      )
    );
  });

  test('applied version table can assign a visible version without relying on select change', async () => {
    render(<ExamSetupPage />);
    await screen.findByText('S0 - Ca 0 · DRAFT');
    fireEvent.click(screen.getByRole('button', { name: 'Phiên bản đề áp dụng' }));

    const assignButtons = await screen.findAllByRole('button', { name: 'Gắn phiên bản này' });
    fireEvent.click(assignButtons[0]);

    await waitFor(() =>
      expect(vi.mocked(httpRequest)).toHaveBeenCalledWith(
        '/delivery/exam-sittings/2000/exam-version',
        expect.objectContaining({ method: 'PATCH', body: JSON.stringify({ exam_version_id: 102 }) })
      )
    );
  });

  test('student import uses student_code and sitting_code without class-section binding', async () => {
    render(<ExamSetupPage />);
    await screen.findByText('S0 - Ca 0 · DRAFT');
    fireEvent.click(screen.getByRole('button', { name: 'Sinh viên dự thi' }));
    fireEvent.change(await screen.findByLabelText('Nhập danh sách sinh viên dự thi (Import)'), { target: { value: 'SV002, S0' } });
    fireEvent.click(screen.getByRole('button', { name: 'Nhập danh sách sinh viên vào ca thi' }));

    await waitFor(() =>
      expect(vi.mocked(httpRequest)).toHaveBeenCalledWith(
        '/delivery/exam-assignments/import-by-code',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            assignment_status: 'ASSIGNED',
            items: [{ student_code: 'SV002', sitting_code: 'S0', note: null }],
          }),
        })
      )
    );
  });

  test('publish panel can select and open a sitting that is not the first row', async () => {
    const base = vi.mocked(httpRequest).getMockImplementation();
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === '/delivery/exam-sittings') {
        return list([
          { exam_sitting_id: 2000, exam_version_id: 101, exam_version_label: 'V1', exam_id: 11, exam_code: 'ACC101', exam_name: 'Kế toán 1', sitting_code: 'S0', sitting_name: 'Ca 0', scheduled_start_at: '2026-06-10T01:00:00Z', scheduled_end_at: '2026-06-10T03:00:00Z', sitting_status: 'READY' },
          { exam_sitting_id: 2001, exam_version_id: 101, exam_version_label: 'V1', exam_id: 11, exam_code: 'ACC101', exam_name: 'Kế toán 1', sitting_code: 'S1', sitting_name: 'Ca 1', scheduled_start_at: '2026-06-10T04:00:00Z', scheduled_end_at: '2026-06-10T06:00:00Z', sitting_status: 'READY' },
        ]);
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
      if (path === '/delivery/exam-sittings/2001/readiness') {
        return ok({
          exam_sitting_id: 2001,
          exam_version_id: 101,
          ready: true,
          blockers: [],
          warnings: [],
          counts: { assignment_count: 1, room_count: 1, station_assignment_count: 1, proctor_count: 1, question_source_count: 1, paper_asset_count: 0 },
        });
      }
      if (path === '/master-data/exam-versions/101/questions') {
        return ok({
          items: [{ question_template_id: 2001, question_grading_profile_id: 8001, question_no: 1, question_title: 'Câu 1', prompt_text: 'SQL', question_type: 'TEXTBOX_SQL', response_mode: 'SQL_TEXT', render_component: 'SQL_EDITOR', input_source: 'SEALED_TEXT_ANSWER', grading_engine_code: 'SQL_RESULT_COMPARATOR', comparison_method: 'EXACT_RESULT_SET', max_score: 10, status: 'ACTIVE', required: true, mcq_options: [], has_expected_answer: true }],
          readiness_summary: { ready: true, missing_items: [] },
        });
      }
      if (path.startsWith('/delivery/exam-sittings/2001/rooms')) return list([{ exam_sitting_room_id: 3101, exam_sitting_id: 2001, room_id: 31, room_code: 'LAB-A101', room_name: 'Phòng A101', room_status: 'READY' }]);
      if (path.startsWith('/delivery/exam-sittings/2001/assignments')) return list([{ exam_assignment_id: 4101, exam_sitting_id: 2001, student_id: 1, student_code: 'SV001', student_name: 'Nguyễn Minh An', assignment_status: 'ASSIGNED' }]);
      if (path.startsWith('/delivery/exam-sittings/2001/seating-plan')) return list([{ station_assignment_id: 5101, exam_assignment_id: 4101, exam_sitting_room_id: 3101, station_id: 91, station_code: 'A101-01', student_code: 'SV001', student_name: 'Nguyễn Minh An', status: 'ASSIGNED' }]);
      if (path.startsWith('/delivery/exam-sitting-rooms/3101/proctors')) return list([{ proctor_assignment_id: 6101, exam_sitting_room_id: 3101, proctor_user_id: 12, proctor_role: 'ROOM_PROCTOR', status: 'ASSIGNED' }]);
      if (path === '/delivery/exam-sittings/2001/status' && init?.method === 'POST') {
        return ok({ exam_sitting_id: 2001, exam_version_id: 101, exam_version_label: 'V1', exam_id: 11, sitting_code: 'S1', sitting_name: 'Ca 1', scheduled_start_at: '2026-06-10T04:00:00Z', scheduled_end_at: '2026-06-10T06:00:00Z', sitting_status: 'OPEN' });
      }
      return base ? base(path, init) : ok({});
    });

    render(<ExamSetupPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Phát hành / Mở ca thi' }));
    fireEvent.change(await screen.findByLabelText('Ca thi cần publish/open'), { target: { value: '2001' } });

    await waitFor(() => expect(screen.getByRole('button', { name: 'Mở ca thi' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Mở ca thi' }));

    await waitFor(() =>
      expect(vi.mocked(httpRequest)).toHaveBeenCalledWith(
        '/delivery/exam-sittings/2001/status',
        expect.objectContaining({ method: 'POST', body: expect.stringContaining('"sitting_status":"OPEN"') })
      )
    );
    expect(vi.mocked(httpRequest)).not.toHaveBeenCalledWith(
      '/delivery/exam-sittings/2000/status',
      expect.objectContaining({ method: 'POST', body: expect.stringContaining('"sitting_status":"OPEN"') })
    );
  });

  test('locked sitting disables applied exam version reassignment', async () => {
    const base = vi.mocked(httpRequest).getMockImplementation();
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === '/delivery/exam-sittings') {
        return list([{ exam_sitting_id: 2000, exam_version_id: 101, exam_version_label: 'V1', exam_id: 11, exam_code: 'ACC101', exam_name: 'Kế toán 1', sitting_code: 'S0', sitting_name: 'Ca 0', scheduled_start_at: '2026-06-10T01:00:00Z', scheduled_end_at: '2026-06-10T03:00:00Z', sitting_status: 'READY' }]);
      }
      if (path === '/delivery/exam-sittings/2000/exam-version' && init?.method === 'PATCH') {
        throw new Error('PATCH should not be called for locked sitting');
      }
      return base ? base(path, init) : ok({});
    });

    render(<ExamSetupPage />);
    await screen.findByText('S0 - Ca 0 · READY');
    fireEvent.click(screen.getByRole('button', { name: 'Phiên bản đề áp dụng' }));

    expect(await screen.findByText(/Ca thi đang ở trạng thái READY/)).toBeInTheDocument();
    expect(screen.getByLabelText('Phiên bản đề áp dụng')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Gắn phiên bản đề cho ca thi' })).toBeDisabled();
  });

  test('readiness is check-only and links to data-entry sections', async () => {
    render(<ExamSetupPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Kiểm tra độ sẵn sàng' }));
    await screen.findByTestId('sitting-readiness-section');
    expect(screen.getAllByText('Readiness chỉ kiểm tra cấu hình, không thay thế bước nhập liệu.').length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: /Thêm/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Tạo/ })).not.toBeInTheDocument();
  });

  test('readiness shows empty state when no sitting is selected', async () => {
    const base = vi.mocked(httpRequest).getMockImplementation();
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === '/delivery/exam-sittings') {
        return list([]);
      }
      return base ? base(path, init) : ok({});
    });

    render(<ExamSetupPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Kiểm tra độ sẵn sàng' }));

    await screen.findByTestId('sitting-readiness-section');
    expect(screen.getAllByText('Vui lòng chọn hoặc tạo ca thi trước.').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: 'Tải lại readiness' })).toBeDisabled();
    expect(screen.getByText('Chưa có dữ liệu.')).toBeInTheDocument();
  });

  test('readiness error can retry and reload backend data', async () => {
    const base = vi.mocked(httpRequest).getMockImplementation();
    let readinessCalls = 0;
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === '/delivery/exam-sittings/2000/readiness') {
        readinessCalls += 1;
        if (readinessCalls === 1) {
          throw new Error('Readiness service unavailable');
        }
        return ok({
          exam_sitting_id: 2000,
          exam_version_id: 101,
          ready: true,
          blockers: [],
          warnings: [{ code: 'late_sync', message: 'Đã đồng bộ lại readiness.', severity: 'WARNING' }],
          counts: { assignment_count: 1, room_count: 1, station_assignment_count: 1, proctor_count: 1, question_source_count: 1, paper_asset_count: 0 },
        });
      }
      return base ? base(path, init) : ok({});
    });

    render(<ExamSetupPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Kiểm tra độ sẵn sàng' }));

    expect(await screen.findByText('Readiness service unavailable')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Thử lại readiness' }));

    expect(await screen.findByText('Không có blocker từ backend.')).toBeInTheDocument();
    expect(readinessCalls).toBeGreaterThanOrEqual(2);
  });

  test('publish panel prefers backend action flags over fallback status gating', async () => {
    const base = vi.mocked(httpRequest).getMockImplementation();
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === '/delivery/exam-sittings') {
        return list([{ exam_sitting_id: 2000, exam_version_id: 101, exam_version_label: 'V1', exam_id: 11, exam_code: 'ACC101', exam_name: 'Kế toán 1', sitting_code: 'S0', sitting_name: 'Ca 0', scheduled_start_at: '2026-06-10T01:00:00Z', scheduled_end_at: '2026-06-10T03:00:00Z', sitting_status: 'READY' }]);
      }
      if (path === '/delivery/exam-sittings/2000/readiness') {
        return ok({
          exam_sitting_id: 2000,
          exam_version_id: 101,
          ready: true,
          can_prepare: true,
          can_open: false,
          blockers: [],
          warnings: [],
          counts: { assignment_count: 1, room_count: 1, station_assignment_count: 1, proctor_count: 1, question_source_count: 1, paper_asset_count: 0 },
        });
      }
      return base ? base(path, init) : ok({});
    });

    render(<ExamSetupPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Phát hành / Mở ca thi' }));

    expect(await screen.findByText('Theo cờ backend readiness.')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Chuẩn bị runtime' })).toBeEnabled());
    expect(screen.getByRole('button', { name: 'Mở ca thi' })).toBeDisabled();
  });

  test('prepare runtime refreshes readiness and ignores duplicate clicks while submitting', async () => {
    const base = vi.mocked(httpRequest).getMockImplementation();
    let prepareCalls = 0;
    let readinessCalls = 0;
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === '/delivery/exam-sittings') {
        return list([{ exam_sitting_id: 2000, exam_version_id: 101, exam_version_label: 'V1', exam_id: 11, exam_code: 'ACC101', exam_name: 'Kế toán 1', sitting_code: 'S0', sitting_name: 'Ca 0', scheduled_start_at: '2026-06-10T01:00:00Z', scheduled_end_at: '2026-06-10T03:00:00Z', sitting_status: 'READY' }]);
      }
      if (path === '/delivery/exam-sittings/2000/readiness') {
        readinessCalls += 1;
        return ok({
          exam_sitting_id: 2000,
          exam_version_id: 101,
          ready: true,
          summary: readinessCalls > 1 ? 'Runtime đã được làm mới.' : 'Sẵn sàng chuẩn bị runtime.',
          blockers: [],
          warnings: [],
          counts: { assignment_count: 1, room_count: 1, station_assignment_count: 1, proctor_count: 1, question_source_count: 1, paper_asset_count: 0 },
        });
      }
      if (path === '/delivery/exam-sittings/2000/prepare' && init?.method === 'POST') {
        prepareCalls += 1;
        return ok({ prepared: true, exam_sitting_id: 2000, exam_version_id: 101, assignment_count: 1, question_count: 1, created_session_count: 1, reused_session_count: 0, created_instance_count: 1, reused_instance_count: 0, created_generated_question_count: 1 });
      }
      return base ? base(path, init) : ok({});
    });

    render(<ExamSetupPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Phát hành / Mở ca thi' }));

    const prepareButton = await screen.findByRole('button', { name: 'Chuẩn bị runtime' });
    await waitFor(() => expect(prepareButton).toBeEnabled());
    fireEvent.click(prepareButton);
    fireEvent.click(prepareButton);

    await waitFor(() => expect(prepareCalls).toBe(1));
    expect(await screen.findByText(/Đã chuẩn bị runtime: 1 session mới/)).toBeInTheDocument();
    expect(readinessCalls).toBeGreaterThanOrEqual(2);
  });

  test('prepare runtime failure shows backend error and does not show false success or open state', async () => {
    const base = vi.mocked(httpRequest).getMockImplementation();
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === '/delivery/exam-sittings') {
        return list([{ exam_sitting_id: 2000, exam_version_id: 101, exam_version_label: 'V1', exam_id: 11, exam_code: 'ACC101', exam_name: 'Kế toán 1', sitting_code: 'S0', sitting_name: 'Ca 0', scheduled_start_at: '2026-06-10T01:00:00Z', scheduled_end_at: '2026-06-10T03:00:00Z', sitting_status: 'READY' }]);
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
        return {
          ok: false as const,
          success: false as const,
          data: null,
          message: null,
          error: { code: 'runtime_prepare_failed', message: 'Prepare runtime failed on backend' },
        };
      }
      return base ? base(path, init) : ok({});
    });

    render(<ExamSetupPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Phát hành / Mở ca thi' }));

    const prepareButton = await screen.findByRole('button', { name: 'Chuẩn bị runtime' });
    await waitFor(() => expect(prepareButton).toBeEnabled());
    fireEvent.click(prepareButton);

    expect(await screen.findByText('Prepare runtime failed on backend')).toBeInTheDocument();
    expect(screen.queryByText(/Đã chuẩn bị runtime:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Ca thi đã mở/)).not.toBeInTheDocument();
    expect(screen.getAllByText('S0 - Ca 0 · READY').length).toBeGreaterThan(0);
  });

  test('Vietnamese labels render as UTF-8 without mojibake markers', async () => {
    render(<ExamSetupPage />);
    await screen.findByRole('button', { name: 'Đề gốc' });
    expect(screen.getByText('Ca thi đang cấu hình')).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/Ã|Ä|á»|Â/);
  });

  test('blueprint form shows decoupled class-section labels and handles disabled states dynamically', async () => {
    // Override mocks to return empty options to trigger disabled state
    const base = vi.mocked(httpRequest).getMockImplementation();
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path.startsWith('/master-data/class-sections')) return list([]);
      if (path.startsWith('/master-data/assessment-types')) return list([]);
      return base ? base(path, init) : ok({});
    });

    render(<ExamSetupPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Đề gốc' }));

    // Click "Tạo đề mới" to enter create mode
    const resetFormButton = screen.getByRole('button', { name: 'Tạo đề mới' });
    expect(resetFormButton).toBeInTheDocument();
    fireEvent.click(resetFormButton);

    // Heading no longer carries backend-compat framing; blueprint is decoupled from class sections
    expect(screen.getByText('Đề gốc / Blueprint')).toBeInTheDocument();
    expect(screen.getByText(/tái sử dụng đề gốc này cho nhiều lớp học phần/)).toBeInTheDocument();
    // Class section is now an optional link, not a required field
    expect(screen.getByLabelText('Lớp học phần liên kết (tùy chọn)')).toBeInTheDocument();

    // Check create/reset buttons text in create mode
    const submitButton = screen.getByRole('button', { name: 'Tạo đề gốc' });
    expect(submitButton).toBeInTheDocument();
    // Disabled only because no assessment type is available — NOT because a class section is missing
    expect(submitButton).toBeDisabled();

    // Verify the only remaining disabled reason is the assessment type
    expect(screen.getByText(/Nút tạo\/cập nhật đề bị vô hiệu hóa vì lý do sau/)).toBeInTheDocument();
    expect(screen.getByText(/Chưa có hình thức đánh giá nào khả dụng trên hệ thống/)).toBeInTheDocument();
    // The old "no class section available" blocker must be gone
    expect(screen.queryByText(/Không có lớp học phần nào khả dụng/)).not.toBeInTheDocument();
  });

  test('sitting class sections panel handles selection, loading, toggling, and saving successfully', async () => {
    const putMock = vi.fn().mockResolvedValue(
      ok({
        items: [
          {
            exam_sitting_class_section_id: 121,
            exam_sitting_id: 2000,
            class_section_id: 21,
            status: 'ACTIVE',
            class_code: 'ACC101-01',
            class_name: 'Lớp 01',
          },
        ],
      })
    );

    const base = vi.mocked(httpRequest).getMockImplementation();
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === '/delivery/exam-sittings/2000/class-sections') {
        if (init?.method === 'PUT') {
          return putMock(path, init);
        }
        return ok({ items: [] });
      }
      if (path.startsWith('/master-data/class-sections')) {
        return list([{ class_section_id: 21, class_code: 'ACC101-01', class_name: 'Lớp 01' }]);
      }
      return base ? base(path, init) : ok({});
    });

    render(<ExamSetupPage />);

    // Click "Lớp học phần ca thi" tab to open the panel
    const tabButton = await screen.findByRole('button', { name: 'Lớp học phần ca thi' });
    fireEvent.click(tabButton);

    // Verify checkbox for class section is visible and can be toggled
    const checkbox = await screen.findByLabelText(/ACC101-01/);
    expect(checkbox).not.toBeChecked();

    // Toggle the checkbox
    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();

    // Save button should be enabled after draft change
    const saveButton = screen.getByTestId('class-section-save-btn');
    expect(saveButton).toBeEnabled();

    // Click save
    fireEvent.click(saveButton);

    // Verify PUT request is made
    await waitFor(() => {
      expect(putMock).toHaveBeenCalled();
    });

    // Check payload passed to update SittingClassSections
    const lastCall = putMock.mock.calls[0];
    const requestBody = JSON.parse(String(lastCall[1]?.body));
    expect(requestBody.class_section_ids).toContain(21);

    // Verify success message is rendered
    expect(await screen.findByText('Đã lưu lớp học phần cho ca thi.')).toBeInTheDocument();
  });

  test('authoring create-new flow creates a blueprint without a class section', async () => {
    const postMock = vi.fn().mockResolvedValue(
      ok({ exam_id: 99, exam_code: 'NOCLS', exam_name: 'Đề không lớp', class_section_id: null, assessment_type_id: 1, exam_status: 'DRAFT' })
    );
    const base = vi.mocked(httpRequest).getMockImplementation();
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === '/master-data/exams' && init?.method === 'POST') {
        return postMock(path, init);
      }
      return base ? base(path, init) : ok({});
    });

    render(<ExamSetupPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Đề gốc' }));
    fireEvent.click(screen.getByRole('button', { name: 'Tạo đề mới' }));

    fireEvent.change(screen.getByLabelText('Mã đề thi'), { target: { value: 'NOCLS' } });
    fireEvent.change(screen.getByLabelText('Tên đề thi'), { target: { value: 'Đề không lớp' } });
    fireEvent.change(screen.getByLabelText('Hình thức đánh giá'), { target: { value: '1' } });

    // Leave the optional class-section selector on its "Không có / Không bắt buộc" default
    const submitButton = screen.getByRole('button', { name: 'Tạo đề gốc' });
    expect(submitButton).toBeEnabled();
    fireEvent.click(submitButton);

    await waitFor(() => expect(postMock).toHaveBeenCalled());
    const body = JSON.parse(String(postMock.mock.calls[0][1]?.body));
    expect(body.class_section_id).toBeNull();
    expect(body.exam_code).toBe('NOCLS');
    expect(await screen.findByText('Đã tạo đề gốc.')).toBeInTheDocument();
  });

  test('delivery import-from-class-sections loads enrolled students into the sitting', async () => {
    const importMock = vi.fn().mockResolvedValue(
      ok({ created: [{}, {}], errors: [], created_count: 2, error_count: 0 })
    );
    const base = vi.mocked(httpRequest).getMockImplementation();
    vi.mocked(httpRequest).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === '/delivery/exam-sittings/2000/assignments/import-from-class-sections' && init?.method === 'POST') {
        return importMock(path, init);
      }
      if (path === '/delivery/exam-sittings/2000/class-sections') {
        return ok({
          items: [
            {
              exam_sitting_class_section_id: 1,
              exam_sitting_id: 2000,
              class_section_id: 21,
              status: 'ACTIVE',
              class_code: 'ACC101-01',
              class_name: 'Lớp 01',
            },
          ],
        });
      }
      if (path.startsWith('/master-data/class-sections')) {
        return list([{ class_section_id: 21, class_code: 'ACC101-01', class_name: 'Lớp 01' }]);
      }
      return base ? base(path, init) : ok({});
    });

    render(<ExamSetupPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Lớp học phần ca thi' }));

    // Import button is enabled only once at least one class section is attached to the sitting
    const importButton = await screen.findByTestId('class-section-import-btn');
    await waitFor(() => expect(importButton).toBeEnabled());
    fireEvent.click(importButton);

    await waitFor(() => expect(importMock).toHaveBeenCalled());
    expect(await screen.findByText('Đã nạp 2 sinh viên từ các lớp đã chọn vào ca thi.')).toBeInTheDocument();
  });
});
