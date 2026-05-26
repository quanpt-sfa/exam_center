import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import {
  autosaveAnswers,
  bindExamDevice,
  getExamRuntimePayload,
  getSealPreflight,
  loadAnswerState,
  loadExamSessionPaperAssets,
  sendHeartbeat,
  sealSubmission,
  startExamSessionStrict,
  uploadAnswerFile,
} from './api';
import { ExamTakingPage } from './ExamTakingPage';
import type { ExamQuestion, ExamTakingPayload } from './types';

vi.mock('./api', () => ({
  autosaveAnswers: vi.fn(),
  bindExamDevice: vi.fn(),
  getExamRuntimePayload: vi.fn(),
  getSealPreflight: vi.fn(),
  loadAnswerState: vi.fn(),
  loadExamSessionPaperAssets: vi.fn(),
  sendHeartbeat: vi.fn(),
  sealSubmission: vi.fn(),
  startExamSessionStrict: vi.fn(),
  uploadAnswerFile: vi.fn(),
}));

const mockedLoad = vi.mocked(getExamRuntimePayload);
const mockedBind = vi.mocked(bindExamDevice);
const mockedPreflight = vi.mocked(getSealPreflight);
const mockedLoadAnswerState = vi.mocked(loadAnswerState);
const mockedLoadPaperAssets = vi.mocked(loadExamSessionPaperAssets);
const mockedAutosave = vi.mocked(autosaveAnswers);
const mockedSeal = vi.mocked(sealSubmission);
const mockedStart = vi.mocked(startExamSessionStrict);
const mockedHeartbeat = vi.mocked(sendHeartbeat);
const mockedUploadFile = vi.mocked(uploadAnswerFile);

const HEARTBEAT_INTERVAL_MS = 30000;

function success<T>(data: T) {
  return { ok: true as const, success: true as const, data, message: null, error: null };
}

function failure(code: string, message: string) {
  return {
    ok: false as const,
    success: false as const,
    data: null,
    message: null,
    error: { code, message },
  };
}

function buildQuestion(overrides?: Partial<ExamQuestion>): ExamQuestion {
  return {
    generated_exam_question_id: 777,
    question_order: 1,
    question_code: 'QTXT',
    question_type: 'ESSAY',
    rendered_question_text: 'Viết câu trả lời',
    score: 5,
    answer_ui: {
      ui_mode: 'TEXTAREA',
      input_source: 'SEALED_TEXT_ANSWER',
      answer_format: 'TEXT',
      required: true,
      current_file: null,
    },
    ...overrides,
  };
}

function buildPayload(overrides?: Partial<ExamTakingPayload>): ExamTakingPayload {
  const questions = overrides?.paper?.questions || [buildQuestion()];

  return {
    ...overrides,
    session: {
      exam_session_id: 99,
      session_code: 'UE2E-SQL-01',
      session_status: 'IN_PROGRESS',
      exam_name: 'Kiểm tra SQL 2E',
      room_name: 'Phòng 201',
      station_code: 'ST-09',
      ...overrides?.session,
    },
    candidate: {
      student_id: 1,
      full_name: 'Nguyễn Văn A',
      student_code: 'B22DCCN001',
      photo_url: 'https://assets.local/photo.jpg',
      ...(overrides?.candidate || {}),
    },
    submission: {
      exam_submission_id: 12001,
      exam_session_id: 99,
      generated_exam_instance_id: 7001,
      submission_status: 'DRAFT',
      ...overrides?.submission,
    },
    paper: {
      exam_session_id: 99,
      generated_exam_instance_id: 7001,
      generation_status: 'GENERATED',
      questions,
      ...overrides?.paper,
    },
    timer: {
      remaining_seconds: 3600,
      ...(overrides?.timer || {}),
    },
    runtime_contract: {
      contract_name: 'student_exam_runtime',
      contract_version: '2026-05-16',
      runtime_readiness: 'READY',
      modality: 'TEXT',
      ...(overrides?.runtime_contract || {}),
    },
    delivery_profile: {
      modality: 'TEXT',
      runtime_readiness: 'READY',
      requires_capture: false,
      ...(overrides?.delivery_profile || {}),
    },
    device_binding_requirement: overrides?.device_binding_requirement,
    device_binding: overrides?.device_binding,
    submission_capabilities: overrides?.submission_capabilities,
    resource_bindings: overrides?.resource_bindings,
    blockers: overrides?.blockers || [],
    warnings: overrides?.warnings || [],
    client_revision: 1,
  };
}

function buildFilePayload(overrides?: Partial<ExamTakingPayload>): ExamTakingPayload {
  return buildPayload({
    ...overrides,
    paper: {
      exam_session_id: 99,
      generated_exam_instance_id: 7001,
      generation_status: 'GENERATED',
      questions: [
        buildQuestion({
          generated_exam_question_id: 501,
          question_order: 1,
          question_code: 'Q1',
          question_type: 'FILE_UPLOAD',
          rendered_question_text: 'Đính kèm bài làm',
          answer_ui: {
            ui_mode: 'FILE_UPLOAD',
            input_source: 'SEALED_FILE_REF',
            answer_format: 'FILE_REF',
            required: true,
            allowed_mime_types: ['application/zip'],
            allowed_extensions: ['.zip'],
            max_file_size_bytes: 26214400,
            current_file: null,
          },
        }),
      ],
      ...(overrides?.paper || {}),
    },
  });
}

function renderPage(path = '/exams/99') {
  return render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }} initialEntries={[path]}>
      <Routes>
        <Route path="/exams/:id" element={<ExamTakingPage />} />
        <Route path="/submissions/:examSubmissionId/result" element={<div>Result page</div>} />
      </Routes>
    </MemoryRouter>
  );
}

function getIntervalCallbackByDelay(spy: ReturnType<typeof vi.spyOn>, delayMs: number) {
  const call = [...spy.mock.calls].reverse().find((entry) => entry[1] === delayMs);
  return call?.[0] as (() => Promise<void>) | undefined;
}

beforeEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
  Object.defineProperty(window.navigator, 'onLine', { configurable: true, value: true });

  mockedLoad.mockResolvedValue(buildFilePayload());
  mockedBind.mockResolvedValue({ required: false, status: 'ACTIVE', station_id: 9 });
  mockedPreflight.mockResolvedValue({
    exam_submission_id: 12001,
    can_seal: true,
    modality: 'TEXT',
    runtime_readiness: 'READY',
    supported_answer_modes: ['TEXT', 'FILE_UPLOAD'],
    counts: {},
    blockers: [],
    warnings: [],
    generated_at: '2026-05-23T10:00:00Z',
  });
  mockedLoadAnswerState.mockResolvedValue(success({ exam_submission_id: 12001, server_ack_revision: 0, items: [] }));
  mockedLoadPaperAssets.mockResolvedValue(success({ exam_session_id: 99, items: [] }));
  mockedStart.mockResolvedValue({
    exam_session_id: 99,
    session_code: 'UE2E-SQL-01',
    session_status: 'IN_PROGRESS',
    timer: { remaining_seconds: 3599 },
  });
  mockedHeartbeat.mockResolvedValue({
    exam_session_id: 99,
    session_status: 'IN_PROGRESS',
    timer: { remaining_seconds: 3590 },
  });
  mockedAutosave.mockResolvedValue(
    success({
      exam_submission_id: 12001,
      batch_status: 'APPLIED',
      idempotent: false,
      server_ack_revision: 1,
    })
  );
  mockedSeal.mockResolvedValue(
    success({
      exam_submission_id: 12001,
      submission_seal_id: 9001,
      seal_status: 'SEALED',
      submission_status: 'SUBMITTED',
      idempotent: false,
    })
  );
  mockedUploadFile.mockResolvedValue(
    success({
      submission_id: 12001,
      generated_exam_question_id: 501,
      answer_file: {
        file_asset_id: 7001,
        file_name: 'bai_lam.zip',
        mime_type: 'application/zip',
        file_size_bytes: 512,
        sha256: 'a'.repeat(64),
        status: 'ACTIVE',
        uploaded_at: '2026-05-23T10:10:00Z',
      },
    })
  );
});

describe('ExamTakingPage runtime UX', () => {
  test('header renders identity and runtime status', async () => {
    mockedLoad.mockResolvedValueOnce(buildTextPayload());

    renderPage();

    expect(await screen.findByRole('heading', { name: 'Kiểm tra SQL 2E' })).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Điều hướng bài thi' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveAttribute('href', '/dashboard');
    expect(screen.getByRole('link', { name: 'Danh sách ca thi' })).toHaveAttribute('href', '/exams');
    expect(screen.getByText('Ca hiện tại')).toBeInTheDocument();
    expect(screen.getByText('Nguyễn Văn A')).toBeInTheDocument();
    expect(screen.getByText('B22DCCN001')).toBeInTheDocument();
    expect(screen.getAllByText('Đang làm bài').length).toBeGreaterThan(0);
    expect(screen.getByText('Phòng 201')).toBeInTheDocument();
  });

  test('runtime load does not call start automatically and shows explicit start action', async () => {
    mockedLoad.mockResolvedValueOnce(
      buildTextPayload({
        session: { session_status: 'READY_TO_START' },
      })
    );

    renderPage();

    expect(await screen.findByRole('button', { name: 'Bắt đầu làm bài' })).toBeInTheDocument();
    expect(mockedStart).not.toHaveBeenCalled();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });

  test('device binding gate is clear and blocks start until binding completes', async () => {
    mockedLoad
      .mockResolvedValueOnce(
        buildTextPayload({
          session: { session_status: 'READY_TO_START' },
          device_binding_requirement: { required: true, station_id: 9, station_code: 'ST-09', device_id: 18, status: 'REQUIRED' },
          device_binding: null,
        })
      )
      .mockResolvedValueOnce(
        buildTextPayload({
          session: { session_status: 'READY_TO_START' },
          device_binding_requirement: { required: true, station_id: 9, station_code: 'ST-09', device_id: 18, status: 'ACTIVE' },
          device_binding: { station_id: 9, station_code: 'ST-09', device_id: 18, device_code: 'DEV-18', binding_status: 'ACTIVE' },
        })
      );

    renderPage();

    expect(await screen.findByRole('heading', { name: 'Yêu cầu gắn thiết bị' })).toBeInTheDocument();
    expect(screen.getByText(/Autosave, tải tệp và heartbeat chỉ hoạt động sau khi phiên thi được bắt đầu hợp lệ/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Bắt đầu làm bài' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận thiết bị' }));

    await waitFor(() => expect(mockedBind).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(mockedLoad).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole('button', { name: 'Bắt đầu làm bài' })).toBeInTheDocument();
  });

  test('start action is explicit and heartbeat starts only after start succeeds', async () => {
    const setIntervalSpy = vi.spyOn(window, 'setInterval');
    mockedLoad.mockResolvedValueOnce(
      buildTextPayload({
        session: { session_status: 'READY_TO_START' },
        timer: { remaining_seconds: null },
      })
    );

    renderPage();

    expect(await screen.findByRole('button', { name: 'Bắt đầu làm bài' })).toBeInTheDocument();
    expect(mockedHeartbeat).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Bắt đầu làm bài' }));

    await waitFor(() => expect(mockedStart).toHaveBeenCalledWith(99, expect.any(Object)));
    expect(await screen.findByRole('textbox')).toBeInTheDocument();
    await waitFor(() => expect(setIntervalSpy).toHaveBeenCalledWith(expect.any(Function), HEARTBEAT_INTERVAL_MS));
    setIntervalSpy.mockRestore();
  });

  test('heartbeat degraded state is visible', async () => {
    const setIntervalSpy = vi.spyOn(window, 'setInterval');
    mockedHeartbeat.mockRejectedValueOnce(new Error('network_error'));
    mockedLoad.mockResolvedValueOnce(buildTextPayload({ timer: { remaining_seconds: null } }));

    renderPage();
    await screen.findByRole('textbox');
    await waitFor(() => expect(setIntervalSpy).toHaveBeenCalledWith(expect.any(Function), HEARTBEAT_INTERVAL_MS));

    const heartbeatTick = getIntervalCallbackByDelay(setIntervalSpy, HEARTBEAT_INTERVAL_MS);
    await act(async () => {
      await heartbeatTick?.();
    });

    expect(await screen.findByText(/Heartbeat tới backend đang bị gián đoạn/i)).toBeInTheDocument();
    setIntervalSpy.mockRestore();
  });

  test('autosave success label is shown only after backend success', async () => {
    mockedLoad.mockResolvedValueOnce(buildTextPayload());

    renderPage();
    const textarea = await screen.findByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'select 1' } });

    expect(screen.getByText('Có thay đổi chưa lưu')).toBeInTheDocument();

    await waitFor(() => expect(mockedAutosave).toHaveBeenCalledTimes(1));
    expect(screen.getByText('Đã lưu lên máy chủ')).toBeInTheDocument();
  }, 10000);

  test('autosave failure label does not show saved state', async () => {
    mockedLoad.mockResolvedValueOnce(buildTextPayload());
    mockedAutosave.mockResolvedValueOnce(failure('network_error', 'Network request failed'));

    renderPage();
    const textarea = await screen.findByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'select 1' } });

    await waitFor(() => expect(mockedAutosave).toHaveBeenCalledTimes(1));
    expect(screen.queryByText('Đã lưu lên máy chủ')).not.toBeInTheDocument();
    expect(screen.getByText('Lưu thất bại')).toBeInTheDocument();
    expect(screen.getAllByText(/Không kết nối được tới máy chủ/i).length).toBeGreaterThan(0);
  }, 10000);

  test('SQL and code answer editors show no execute action', async () => {
    mockedLoad.mockResolvedValueOnce(
      buildPayload({
        paper: {
          exam_session_id: 99,
          generated_exam_instance_id: 7001,
          generation_status: 'GENERATED',
          questions: [
            buildQuestion({
              generated_exam_question_id: 777,
              question_order: 1,
              question_code: 'QSQL',
              question_type: 'SQL_QUERY',
              answer_ui: {
                ui_mode: 'SQL_TEXT',
                input_source: 'SEALED_TEXT_ANSWER',
                answer_format: 'TEXT',
                required: true,
                current_file: null,
              },
            }),
            buildQuestion({
              generated_exam_question_id: 778,
              question_order: 2,
              question_code: 'QCODE',
              question_type: 'CUSTOM',
              answer_ui: {
                ui_mode: 'CODE_TEXT',
                input_source: 'CODE_TEXT',
                answer_format: 'TEXT',
                required: false,
                current_file: null,
              },
            }),
          ],
        },
      })
    );

    renderPage();

    expect(await screen.findByText('SQL text answer')).toBeInTheDocument();
    expect(screen.getByText('Code text answer')).toBeInTheDocument();
    expect(screen.getAllByText(/No execute or run action is available in this phase/i)).toHaveLength(2);
    expect(screen.queryByRole('button', { name: /run|execute/i })).not.toBeInTheDocument();
  });

  test('file upload shows backend metadata after upload succeeds', async () => {
    mockedLoad.mockResolvedValueOnce(buildFilePayload());

    renderPage();
    await screen.findByLabelText('Đính kèm bài làm câu 1');

    const input = screen.getByLabelText('Chọn tệp') as HTMLInputElement;
    const file = new File(['zip-content'], 'bai_lam.zip', { type: 'application/zip' });
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole('button', { name: 'Tải tệp' }));

    await waitFor(() => expect(mockedUploadFile).toHaveBeenCalledTimes(1));
    expect(await screen.findByText('ACTIVE')).toBeInTheDocument();
    expect(screen.getByText('bai_lam.zip')).toBeInTheDocument();
    expect(screen.getAllByText('application/zip').length).toBeGreaterThan(0);
  });

  test('unsupported database or foundation-only runtime stays read-only', async () => {
    mockedLoad.mockResolvedValueOnce(
      buildTextPayload({
        runtime_contract: {
          contract_name: 'student_exam_runtime',
          contract_version: '2026-05-16',
          runtime_readiness: 'FOUNDATION_ONLY',
          modality: 'STUDENT_DATABASE',
        },
        blockers: [
          { code: 'UNSUPPORTED_MODALITY', message: 'Database workspace chưa sẵn sàng', severity: 'blocker' },
          { code: 'RESOURCE_NOT_READY', message: 'Resource chưa sẵn sàng', severity: 'blocker' },
        ],
      })
    );

    renderPage();

    expect(await screen.findByRole('heading', { name: 'Chế độ làm bài chưa được hỗ trợ' })).toBeInTheDocument();
    expect(
      screen.getAllByText((_, element) => element?.textContent?.includes('Database workspace chưa sẵn sàng') ?? false).length
    ).toBeGreaterThan(0);
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Chọn tệp')).not.toBeInTheDocument();
  });

  test('question navigator shows answered, missing, and blocked states', async () => {
    mockedLoad.mockResolvedValueOnce(
      buildPayload({
        paper: {
          exam_session_id: 99,
          generated_exam_instance_id: 7001,
          generation_status: 'GENERATED',
          questions: [
            buildQuestion({ generated_exam_question_id: 777, question_order: 1, question_code: 'Q1' }),
            buildQuestion({
              generated_exam_question_id: 778,
              question_order: 2,
              question_code: 'Q2',
              question_type: 'FILE_UPLOAD',
              answer_ui: {
                ui_mode: 'FILE_UPLOAD',
                input_source: 'SEALED_FILE_REF',
                answer_format: 'FILE_REF',
                required: true,
                allowed_mime_types: ['text/plain'],
                allowed_extensions: ['.txt'],
                current_file: null,
              },
            }),
            buildQuestion({
              generated_exam_question_id: 779,
              question_order: 3,
              question_code: 'Q3',
              answer_ui: {
                ui_mode: 'INSTRUCTION_ONLY',
                input_source: 'MANUAL_RESPONSE',
                answer_format: 'TEXT',
                required: false,
                current_file: null,
              },
            }),
          ],
        },
      })
    );
    mockedLoadAnswerState.mockResolvedValueOnce(
      success({
        exam_submission_id: 12001,
        server_ack_revision: 1,
        items: [
          {
            answer_state_id: 1,
            generated_exam_question_id: 777,
            answer_text: 'đã trả lời',
            server_version: 1,
          },
        ],
      })
    );

    renderPage();

    const nav = await screen.findByRole('navigation', { name: 'Danh sách câu hỏi' });
    expect(within(nav).getByText('Đã trả lời')).toBeInTheDocument();
    expect(within(nav).getByText('Thiếu bắt buộc')).toBeInTheDocument();
    expect(within(nav).getByText('Chỉ đọc')).toBeInTheDocument();
  });

  test('preflight blockers are displayed and block seal', async () => {
    mockedLoad.mockResolvedValueOnce(buildTextPayload());
    mockedPreflight.mockResolvedValueOnce({
      exam_submission_id: 12001,
      can_seal: false,
      modality: 'TEXT',
      runtime_readiness: 'READY',
      supported_answer_modes: ['TEXT'],
      counts: {},
      blockers: [{ code: 'MISSING_REQUIRED_ANSWER', message: 'Câu 1 còn thiếu câu trả lời bắt buộc.', severity: 'blocker', generated_exam_question_id: 777 }],
      warnings: [{ code: 'FINAL_REVIEW', message: 'Kiểm tra lại trước khi nộp.', severity: 'warning' }],
      generated_at: '2026-05-23T10:00:00Z',
    });

    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Nộp bài' }));

    expect(await screen.findByRole('heading', { name: 'Preflight đang chặn nộp bài' })).toBeInTheDocument();
    expect(screen.getByText('Câu 1 còn thiếu câu trả lời bắt buộc.')).toBeInTheDocument();
    expect(screen.getByText('Kiểm tra lại trước khi nộp.')).toBeInTheDocument();
    expect(mockedSeal).not.toHaveBeenCalled();
  });

  test('preflight success enables seal confirmation before seal call', async () => {
    mockedLoad.mockResolvedValueOnce(buildTextPayload());
    mockedLoadAnswerState.mockResolvedValueOnce(
      success({
        exam_submission_id: 12001,
        server_ack_revision: 1,
        items: [
          {
            answer_state_id: 1,
            generated_exam_question_id: 777,
            answer_text: 'đáp án hợp lệ',
            server_version: 1,
          },
        ],
      })
    );

    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Nộp bài' }));

    await waitFor(() => expect(mockedPreflight).toHaveBeenCalledWith(12001));
    expect(mockedSeal).not.toHaveBeenCalled();
    expect(await screen.findByRole('heading', { name: 'Sẵn sàng nộp và khóa bài' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận nộp và khóa bài' }));
    await waitFor(() => expect(mockedSeal).toHaveBeenCalledTimes(1));
  });

  test('already sealed runtime is read-only', async () => {
    mockedLoad.mockResolvedValueOnce(
      buildTextPayload({
        submission: {
          exam_submission_id: 12001,
          exam_session_id: 99,
          generated_exam_instance_id: 7001,
          submission_status: 'SEALED',
          sealed_at: '2026-05-23T10:00:00Z',
        },
      })
    );

    renderPage();

    expect(await screen.findByRole('heading', { name: 'Bài làm đã được khóa' })).toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });

  test('unknown answer mode does not render a textbox', async () => {
    mockedLoad.mockResolvedValueOnce(
      buildPayload({
        paper: {
          exam_session_id: 99,
          generated_exam_instance_id: 7001,
          generation_status: 'GENERATED',
          questions: [
            buildQuestion({
              generated_exam_question_id: 889,
              question_order: 1,
              question_code: 'QY',
              question_type: 'CUSTOM',
              rendered_question_text: 'Unknown',
              answer_ui: { ui_mode: 'FUTURE_MODE', input_source: 'FUTURE_MODE', required: true, current_file: null },
            }),
          ],
        },
      })
    );

    renderPage();

    expect(await screen.findByRole('heading', { name: 'Chế độ làm bài chưa được hỗ trợ' })).toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });

  test('runtime layout exposes structural hooks for responsive navigation', async () => {
    mockedLoad.mockResolvedValueOnce(buildTextPayload());

    const { container } = renderPage();
    await screen.findByRole('textbox');

    expect(container.querySelector('.exam-taking-layout')).not.toBeNull();
    expect(container.querySelector('.question-nav-list')).not.toBeNull();
  });
});

describe('UTF-8 guard', () => {
  test('touched UI files do not contain mojibake markers', () => {
    const files = [
      resolve(process.cwd(), 'src/features/examTaking/ExamTakingPage.tsx'),
      resolve(process.cwd(), 'src/features/examTaking/VisualPaperViewer.tsx'),
    ];
    const markers = ['Ä‘', 'á»', 'Ã', '?í'];

    files.forEach((filePath) => {
      const content = readFileSync(filePath, 'utf-8');
      markers.forEach((marker) => {
        expect(content.includes(marker)).toBe(false);
      });
    });
  });
});

function buildTextPayload(overrides?: Partial<ExamTakingPayload>): ExamTakingPayload {
  return buildPayload({
    ...overrides,
    paper: {
      exam_session_id: 99,
      generated_exam_instance_id: 7001,
      generation_status: 'GENERATED',
      questions: overrides?.paper?.questions || [buildQuestion()],
      ...(overrides?.paper || {}),
    },
  });
}
