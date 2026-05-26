import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { ExamSetupPage } from './ExamSetupPage';
import * as examAuthoringApi from './api/examAuthoringApi';
import * as deliverySetupApi from './api/deliverySetupApi';

vi.mock('./api/examAuthoringApi', async () => {
  const actual = await vi.importActual<typeof import('./api/examAuthoringApi')>('./api/examAuthoringApi');
  return {
    ...actual,
    loadExamAuthoringBaseData: vi.fn(),
    loadExamVersions: vi.fn(),
    loadExamVersionQuestions: vi.fn(),
    createExamVersionQuestion: vi.fn(),
    updateExamVersionQuestion: vi.fn(),
    loadExamVersionDeliveryProfile: vi.fn(),
    loadExamVersionQuestionGradingProfiles: vi.fn(),
    loadExamVersionPaperAssets: vi.fn(),
    createExam: vi.fn(),
    updateExam: vi.fn(),
    createExamVersion: vi.fn(),
    validateExamVersion: vi.fn(),
    publishExamVersion: vi.fn(),
    upsertExamVersionDeliveryProfile: vi.fn(),
    configureFileUploadManualGrading: vi.fn(),
    createFileUploadPlaceholderQuestion: vi.fn(),
    retireExamVersionPaperAsset: vi.fn(),
    uploadExamVersionPaperAsset: vi.fn(),
  };
});

vi.mock('./api/deliverySetupApi', async () => {
  const actual = await vi.importActual<typeof import('./api/deliverySetupApi')>('./api/deliverySetupApi');
  return {
    ...actual,
    loadDeliverySetupBaseData: vi.fn(),
    listDeliverySittings: vi.fn(),
    listSittingRooms: vi.fn(),
    listExamAssignments: vi.fn(),
    listSeatingPlan: vi.fn(),
    listRoomProctors: vi.fn(),
    getExamSittingReadiness: vi.fn(),
    prepareExamSittingRuntime: vi.fn(),
    createDeliverySitting: vi.fn(),
    createSittingRoom: vi.fn(),
    createRoomProctor: vi.fn(),
    createExamAssignment: vi.fn(),
    assignExamStation: vi.fn(),
  };
});

describe('ExamSetupPage API-client boundary', () => {
  beforeEach(() => {
    vi.resetAllMocks();

    vi.mocked(examAuthoringApi.loadExamAuthoringBaseData).mockResolvedValue({
      exams: [{ exam_id: 11, exam_code: 'ACC101', exam_name: 'Kế toán 1' }],
      classSections: [{ class_section_id: 21, class_code: 'ACC101-01', class_name: 'LHP 01' }],
      assessmentTypes: [{ assessment_type_id: 1, type_code: 'MIDTERM', type_name: 'Giữa kỳ' }],
    });
    vi.mocked(deliverySetupApi.loadDeliverySetupBaseData).mockResolvedValue({
      exams: [{ exam_id: 11, exam_code: 'ACC101', exam_name: 'Kế toán 1' }],
      rooms: [],
      stations: [],
      students: [],
      instructors: [],
      modules: [],
    });
    vi.mocked(examAuthoringApi.loadExamVersions).mockResolvedValue([
      {
        exam_version_id: 101,
        exam_id: 11,
        exam_code: 'ACC101',
        version_no: 1,
        version_label: 'Version 1',
        duration_seconds: 3600,
        total_score: 10,
        randomization_mode: 'FIXED',
        status: 'DRAFT',
      },
    ]);
    vi.mocked(examAuthoringApi.loadExamVersionQuestions).mockResolvedValue({
      items: [],
      readiness_summary: { ready: false, missing_items: [] },
    });
    const item = {
      question_template_id: 2001,
      question_grading_profile_id: 8001,
      question_no: 1,
      question_title: 'Câu 1',
      prompt_text: 'Nhập câu trả lời.',
      question_type: 'TEXTAREA',
      response_mode: 'LONG_TEXT',
      render_component: 'TEXTAREA',
      input_source: 'SEALED_TEXT_ANSWER',
      grading_engine_code: 'MANUAL_RUBRIC',
      comparison_method: 'MANUAL_RUBRIC',
      max_score: 1,
      status: 'ACTIVE',
      required: true,
      mcq_options: [],
      has_expected_answer: false,
    };
    vi.mocked(examAuthoringApi.createExamVersionQuestion).mockResolvedValue({
      ok: true,
      success: true,
      data: item,
      message: null,
      error: null,
    });
    vi.mocked(examAuthoringApi.createExam).mockResolvedValue({
      ok: true,
      success: true,
      data: {
        exam_id: 11,
        exam_code: 'ACC101',
        exam_name: 'Kế toán 1',
        class_section_id: 21,
        assessment_type_id: 1,
        exam_status: 'DRAFT',
      },
      message: null,
      error: null,
    });
    vi.mocked(examAuthoringApi.updateExam).mockResolvedValue({
      ok: true,
      success: true,
      data: {
        exam_id: 11,
        exam_code: 'ACC101',
        exam_name: 'Kế toán 1',
        class_section_id: 21,
        assessment_type_id: 1,
        exam_status: 'DRAFT',
      },
      message: null,
      error: null,
    });
    vi.mocked(examAuthoringApi.updateExamVersionQuestion).mockResolvedValue({
      ok: true,
      success: true,
      data: item,
      message: null,
      error: null,
    });
    vi.mocked(examAuthoringApi.loadExamVersionDeliveryProfile).mockResolvedValue(null);
    vi.mocked(examAuthoringApi.loadExamVersionQuestionGradingProfiles).mockResolvedValue([]);
    vi.mocked(examAuthoringApi.loadExamVersionPaperAssets).mockResolvedValue([]);
    vi.mocked(examAuthoringApi.validateExamVersion).mockResolvedValue({
      ok: true,
      success: true,
      data: {
        exam_id: 11,
        exam_version_id: 101,
        exam_status: 'ACTIVE',
        version_status: 'DRAFT',
        exam_modality: 'TEXT_ONLY',
        is_valid: true,
        missing_items: [],
      },
      message: null,
      error: null,
    });
    vi.mocked(examAuthoringApi.publishExamVersion).mockResolvedValue({
      ok: true,
      success: true,
      data: {
        exam_version_id: 101,
        status: 'PUBLISHED',
      },
      message: null,
      error: null,
    });
    vi.mocked(deliverySetupApi.listDeliverySittings).mockResolvedValue([]);
    vi.mocked(deliverySetupApi.listSittingRooms).mockResolvedValue([]);
    vi.mocked(deliverySetupApi.listExamAssignments).mockResolvedValue([]);
    vi.mocked(deliverySetupApi.listSeatingPlan).mockResolvedValue([]);
    vi.mocked(deliverySetupApi.listRoomProctors).mockResolvedValue([]);
    vi.mocked(deliverySetupApi.getExamSittingReadiness).mockResolvedValue({
      exam_sitting_id: 0,
      exam_version_id: 101,
      ready: false,
      blockers: [],
      warnings: [],
      counts: {
        assignment_count: 0,
        room_count: 0,
        station_assignment_count: 0,
        proctor_count: 0,
        question_source_count: 0,
        paper_asset_count: 0,
      },
    });
    vi.mocked(deliverySetupApi.prepareExamSittingRuntime).mockResolvedValue({
      ok: true,
      success: true,
      data: {
        prepared: true,
        exam_sitting_id: 0,
        exam_version_id: 101,
        assignment_count: 0,
        question_count: 0,
        created_session_count: 0,
        reused_session_count: 0,
        created_instance_count: 0,
        reused_instance_count: 0,
        created_generated_question_count: 0,
      },
      message: null,
      error: null,
    });
  });

  async function openVersionReadinessSection() {
    fireEvent.click(await screen.findByRole('button', { name: 'Độ sẵn sàng phiên bản đề' }));
    await screen.findByRole('button', { name: 'Publish phiên bản đề' });
  }

  async function openBlueprintSection() {
    fireEvent.click(await screen.findByRole('button', { name: 'Đề gốc' }));
    await screen.findByLabelText('Mã đề thi');
  }

  function mockSelectedExamStatus(status: string) {
    vi.mocked(examAuthoringApi.loadExamAuthoringBaseData).mockResolvedValue({
      exams: [
        {
          exam_id: 11,
          exam_code: 'ACC101',
          exam_name: 'Kế toán 1',
          class_section_id: 21,
          assessment_type_id: 1,
          exam_status: status,
        },
      ],
      classSections: [{ class_section_id: 21, class_code: 'ACC101-01', class_name: 'LHP 01' }],
      assessmentTypes: [{ assessment_type_id: 1, type_code: 'MIDTERM', type_name: 'Giữa kỳ' }],
    });
  }

  function mockExamNotActiveBlocker() {
    vi.mocked(examAuthoringApi.validateExamVersion)
      .mockResolvedValueOnce({
        ok: true,
        success: true,
        data: {
          exam_id: 11,
          exam_version_id: 101,
          exam_status: 'DRAFT',
          version_status: 'DRAFT',
          exam_modality: 'TEXT_ONLY',
          is_valid: false,
          missing_items: [
            {
              code: 'exam_not_active',
              message: 'Exam must be ACTIVE before publishing a version',
            },
          ],
        },
        message: null,
        error: null,
      })
      .mockResolvedValue({
        ok: true,
        success: true,
        data: {
          exam_id: 11,
          exam_version_id: 101,
          exam_status: 'ACTIVE',
          version_status: 'DRAFT',
          exam_modality: 'TEXT_ONLY',
          is_valid: true,
          missing_items: [],
        },
        message: null,
        error: null,
      });
  }

  async function showExamNotActiveBlocker() {
    render(<ExamSetupPage />);
    await openVersionReadinessSection();
    fireEvent.click(screen.getByRole('button', { name: 'Publish phiên bản đề' }));
    await waitFor(() => expect(examAuthoringApi.validateExamVersion).toHaveBeenCalledWith('101'));
    return screen.findByRole('button', { name: 'Kích hoạt đề gốc' });
  }

  test('loading base data does not auto-select the first class section', async () => {
    vi.mocked(examAuthoringApi.loadExamAuthoringBaseData).mockResolvedValue({
      exams: [{ exam_id: 11, exam_code: 'ACC101', exam_name: 'Kế toán 1', class_section_id: null, assessment_type_id: 1 }],
      classSections: [
        { class_section_id: 21, class_code: 'ACC101-01', class_name: 'LHP 01' },
        { class_section_id: 22, class_code: 'ACC101-02', class_name: 'LHP 02' },
      ],
      assessmentTypes: [{ assessment_type_id: 1, type_code: 'MIDTERM', type_name: 'Giữa kỳ' }],
    });

    render(<ExamSetupPage />);
    await openBlueprintSection();

    expect(screen.getByLabelText('Lớp học phần liên kết (tùy chọn)')).toHaveValue('');
  });

  test('switching from an exam with class section to one without clears the field', async () => {
    vi.mocked(examAuthoringApi.loadExamAuthoringBaseData).mockResolvedValue({
      exams: [
        { exam_id: 11, exam_code: 'ACC101', exam_name: 'Kế toán 1', class_section_id: 21, assessment_type_id: 1 },
        { exam_id: 12, exam_code: 'ACC102', exam_name: 'Kế toán 2', class_section_id: null, assessment_type_id: 1 },
      ],
      classSections: [{ class_section_id: 21, class_code: 'ACC101-01', class_name: 'LHP 01' }],
      assessmentTypes: [{ assessment_type_id: 1, type_code: 'MIDTERM', type_name: 'Giữa kỳ' }],
    });

    render(<ExamSetupPage />);
    await openBlueprintSection();

    expect(screen.getByLabelText('Lớp học phần liên kết (tùy chọn)')).toHaveValue('21');

    fireEvent.change(screen.getByLabelText('Đề gốc'), { target: { value: '12' } });

    await waitFor(() => {
      expect(screen.getByLabelText('Lớp học phần liên kết (tùy chọn)')).toHaveValue('');
    });
  });

  test('updating a blueprint with empty class section sends null', async () => {
    render(<ExamSetupPage />);
    await openBlueprintSection();

    fireEvent.change(screen.getByLabelText('Lớp học phần liên kết (tùy chọn)'), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: 'Cập nhật đề gốc' }));

    await waitFor(() =>
      expect(examAuthoringApi.updateExam).toHaveBeenCalledWith(
        '11',
        expect.objectContaining({
          class_section_id: null,
          assessment_type_id: 1,
        })
      )
    );
  });

  test('saving question uses typed API client function', async () => {
    render(<ExamSetupPage />);
    fireEvent.click(screen.getByRole('button', { name: /Câu hỏi/i }));

    fireEvent.change(await screen.findByLabelText('Số câu'), { target: { value: '1' } });
    fireEvent.change(screen.getByLabelText(/Tiêu đề câu hỏi/i), { target: { value: 'Câu 1' } });
    fireEvent.change(screen.getByLabelText(/Nội dung câu hỏi/i), { target: { value: 'Nhập câu trả lời.' } });
    fireEvent.change(screen.getByLabelText('Điểm tối đa'), { target: { value: '1' } });
    fireEvent.click(screen.getByRole('button', { name: /Thêm câu hỏi/i }));

    await waitFor(() => {
      expect(examAuthoringApi.createExamVersionQuestion).toHaveBeenCalledTimes(1);
    });
    expect(examAuthoringApi.createExamVersionQuestion).toHaveBeenCalledWith(
      '101',
      expect.objectContaining({
        question_type: 'TEXTAREA',
        question_no: 1,
      })
    );
  });

  test('delivery publish flow uses typed delivery readiness and prepare clients', async () => {
    vi.mocked(deliverySetupApi.listDeliverySittings).mockResolvedValue([
      {
        exam_sitting_id: 2000,
        exam_version_id: 101,
        exam_version_label: 'Version 1',
        sitting_code: 'S0',
        sitting_name: 'Ca 0',
        sitting_status: 'READY',
      },
    ]);
    vi.mocked(deliverySetupApi.getExamSittingReadiness).mockResolvedValue({
      exam_sitting_id: 2000,
      exam_version_id: 101,
      ready: true,
      blockers: [],
      warnings: [],
      counts: {
        assignment_count: 1,
        room_count: 1,
        station_assignment_count: 1,
        proctor_count: 1,
        question_source_count: 1,
        paper_asset_count: 0,
      },
    });
    vi.mocked(deliverySetupApi.prepareExamSittingRuntime).mockResolvedValue({
      ok: true,
      success: true,
      data: {
        prepared: true,
        exam_sitting_id: 2000,
        exam_version_id: 101,
        assignment_count: 1,
        question_count: 1,
        created_session_count: 1,
        reused_session_count: 0,
        created_instance_count: 1,
        reused_instance_count: 0,
        created_generated_question_count: 1,
      },
      message: null,
      error: null,
    });

    render(<ExamSetupPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Phát hành / Mở ca thi' }));

    await waitFor(() => expect(deliverySetupApi.getExamSittingReadiness).toHaveBeenCalledWith(2000));
    const prepareButton = await screen.findByRole('button', { name: 'Chuẩn bị runtime' });
    await waitFor(() => expect(prepareButton).toBeEnabled());
    fireEvent.click(prepareButton);

    await waitFor(() => expect(deliverySetupApi.prepareExamSittingRuntime).toHaveBeenCalledWith('2000'));
    expect(await screen.findByText(/Đã chuẩn bị runtime: 1 session mới/)).toBeInTheDocument();
  });

  test('publish flow does not show final readiness success without backend readiness data', async () => {
    vi.mocked(deliverySetupApi.listDeliverySittings).mockResolvedValue([
      {
        exam_sitting_id: 2000,
        exam_version_id: 101,
        exam_version_label: 'Version 1',
        sitting_code: 'S0',
        sitting_name: 'Ca 0',
        sitting_status: 'READY',
      },
    ]);
    vi.mocked(deliverySetupApi.getExamSittingReadiness).mockRejectedValue(new Error('Readiness unavailable'));

    render(<ExamSetupPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Phát hành / Mở ca thi' }));

    await waitFor(() => expect(deliverySetupApi.getExamSittingReadiness).toHaveBeenCalledWith(2000));
    expect(screen.queryByText('Đạt, có thể chuyển trạng thái.')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Thử lại readiness' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Chuẩn bị runtime' })).toBeDisabled();
  });

  test('publish validation errors are rendered from details.errors and block publish', async () => {
    vi.mocked(examAuthoringApi.validateExamVersion).mockResolvedValue({
      ok: true,
      success: true,
      data: {
        exam_id: 11,
        exam_version_id: 101,
        exam_status: 'ACTIVE',
        version_status: 'DRAFT',
        exam_modality: 'TEXT_ONLY',
        is_valid: false,
        missing_items: [
          {
            code: 'question_expected_answer_missing',
            message: 'Question is missing expected answer',
          },
        ],
      },
      message: null,
      error: null,
    });

    render(<ExamSetupPage />);
    await openVersionReadinessSection();
    fireEvent.click(screen.getByRole('button', { name: 'Publish phiên bản đề' }));

    await waitFor(() => expect(examAuthoringApi.validateExamVersion).toHaveBeenCalledWith('101'));
    expect(examAuthoringApi.publishExamVersion).not.toHaveBeenCalled();
    expect(screen.getByTestId('publish-blockers-table')).toBeInTheDocument();
    expect(screen.getByText('question_expected_answer_missing')).toBeInTheDocument();
    expect(screen.getByText('Question is missing expected answer')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Sửa cấu hình' }));
    expect(await screen.findByTestId('expected-answer-section')).toBeInTheDocument();
  });

  test('publish readiness exam_not_active blocker shows blueprint activation action', async () => {
    mockSelectedExamStatus('DRAFT');
    mockExamNotActiveBlocker();

    const activateButton = await showExamNotActiveBlocker();

    expect(activateButton).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Sửa cấu hình' })).not.toBeInTheDocument();
  });

  test('activating a DRAFT blueprint updates DRAFT to READY then ACTIVE', async () => {
    mockSelectedExamStatus('DRAFT');
    mockExamNotActiveBlocker();
    vi.mocked(examAuthoringApi.updateExam)
      .mockResolvedValueOnce({
        ok: true,
        success: true,
        data: {
          exam_id: 11,
          exam_code: 'ACC101',
          exam_name: 'Kế toán 1',
          class_section_id: 21,
          assessment_type_id: 1,
          exam_status: 'READY',
        },
        message: null,
        error: null,
      })
      .mockResolvedValueOnce({
        ok: true,
        success: true,
        data: {
          exam_id: 11,
          exam_code: 'ACC101',
          exam_name: 'Kế toán 1',
          class_section_id: 21,
          assessment_type_id: 1,
          exam_status: 'ACTIVE',
        },
        message: null,
        error: null,
      });

    fireEvent.click(await showExamNotActiveBlocker());

    await waitFor(() => expect(examAuthoringApi.updateExam).toHaveBeenCalledTimes(2));
    expect(examAuthoringApi.updateExam).toHaveBeenNthCalledWith(
      1,
      '11',
      expect.objectContaining({ exam_status: 'READY' })
    );
    expect(examAuthoringApi.updateExam).toHaveBeenNthCalledWith(
      2,
      '11',
      expect.objectContaining({ exam_status: 'ACTIVE' })
    );
  });

  test('activating a READY blueprint updates directly to ACTIVE', async () => {
    mockSelectedExamStatus('READY');
    mockExamNotActiveBlocker();

    fireEvent.click(await showExamNotActiveBlocker());

    await waitFor(() => expect(examAuthoringApi.updateExam).toHaveBeenCalledTimes(1));
    expect(examAuthoringApi.updateExam).toHaveBeenCalledWith('11', expect.objectContaining({ exam_status: 'ACTIVE' }));
  });

  test('activating an already ACTIVE blueprint is idempotent', async () => {
    mockSelectedExamStatus('ACTIVE');
    mockExamNotActiveBlocker();

    fireEvent.click(await showExamNotActiveBlocker());

    await waitFor(() => expect(examAuthoringApi.validateExamVersion).toHaveBeenCalledTimes(2));
    expect(examAuthoringApi.updateExam).not.toHaveBeenCalled();
    expect(await screen.findByText('Đề gốc đã ACTIVE. Phiên bản đề đã sẵn sàng để publish.')).toBeInTheDocument();
  });

  test.each(['ARCHIVED', 'CANCELLED'] as const)('activating a %s blueprint shows a non-actionable error', async (status) => {
    mockSelectedExamStatus(status);
    mockExamNotActiveBlocker();

    fireEvent.click(await showExamNotActiveBlocker());

    await waitFor(() => expect(screen.getByText(new RegExp(`Không thể tự động kích hoạt đề gốc ở trạng thái ${status}`))).toBeInTheDocument());
    expect(examAuthoringApi.updateExam).not.toHaveBeenCalled();
  });

  test('publish 422 renders response.error.details.errors as a blocker checklist', async () => {
    vi.mocked(examAuthoringApi.publishExamVersion).mockResolvedValue({
      ok: false,
      success: false,
      data: null,
      error: {
        code: 'validation_error',
        message: 'Exam version publish validation failed',
        details: {
          errors: [
            {
              code: 'paper_asset_missing',
              message: 'Visual paper asset is required',
              severity: 'error',
              status: 'OPEN',
            },
          ],
        },
      },
      message: null,
    });

    render(<ExamSetupPage />);
    await openVersionReadinessSection();
    fireEvent.click(screen.getByRole('button', { name: 'Publish phiên bản đề' }));

    await waitFor(() => expect(examAuthoringApi.validateExamVersion).toHaveBeenCalledWith('101'));
    await waitFor(() => expect(examAuthoringApi.publishExamVersion).toHaveBeenCalledWith('101'));
    expect(screen.getByTestId('publish-blockers-table')).toBeInTheDocument();
    expect(screen.getByText('paper_asset_missing')).toBeInTheDocument();
    expect(screen.getByText('Visual paper asset is required')).toBeInTheDocument();
    expect(screen.getByText('error')).toBeInTheDocument();
  });

  test.each([
    ['PUBLISHED', 'Phiên bản này đã được publish.'],
    ['RETIRED', 'Không thể publish lại version đã retired/voided; hãy tạo version mới.'],
    ['VOIDED', 'Không thể publish lại version đã retired/voided; hãy tạo version mới.'],
  ] as const)('publish button is disabled for %s versions', async (status, expectedMessage) => {
    vi.mocked(examAuthoringApi.loadExamVersions).mockResolvedValue([
      {
        exam_version_id: 101,
        exam_id: 11,
        exam_code: 'ACC101',
        version_no: 1,
        version_label: 'Version 1',
        duration_seconds: 3600,
        total_score: 10,
        randomization_mode: 'FIXED',
        status,
      },
    ]);

    render(<ExamSetupPage />);
    await openVersionReadinessSection();
    const publishButton = screen.getByRole('button', { name: 'Publish phiên bản đề' });
    expect(publishButton).toBeDisabled();
    expect(screen.getByText(expectedMessage)).toBeInTheDocument();
  });

  test.each(['DRAFT', 'UNDER_REVIEW'] as const)('draft-like version can validate and publish when status is %s', async (status) => {
    vi.mocked(examAuthoringApi.loadExamVersions).mockResolvedValue([
      {
        exam_version_id: 101,
        exam_id: 11,
        exam_code: 'ACC101',
        version_no: 1,
        version_label: 'Version 1',
        duration_seconds: 3600,
        total_score: 10,
        randomization_mode: 'FIXED',
        status,
      },
    ]);

    render(<ExamSetupPage />);
    await openVersionReadinessSection();
    const publishButton = screen.getByRole('button', { name: 'Publish phiên bản đề' });
    expect(publishButton).toBeEnabled();
    fireEvent.click(publishButton);

    await waitFor(() => expect(examAuthoringApi.validateExamVersion).toHaveBeenCalledWith('101'));
    await waitFor(() => expect(examAuthoringApi.publishExamVersion).toHaveBeenCalledWith('101'));
    expect(await screen.findByText('Đã publish phiên bản đề.')).toBeInTheDocument();
  });
});
