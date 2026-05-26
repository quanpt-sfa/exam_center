import { beforeEach, describe, expect, test, vi } from 'vitest';
import { httpRequest } from '../../shared/api/httpClient';
import { getSubmissionProcessingStatus } from '../submissionProcessing/api';
import {
  autosaveAnswers,
  bindExamDevice,
  getAnswerFileMetadata,
  getAnswerState,
  getExamRuntimePayload,
  getProcessingStatus,
  getSealPreflight,
  getSubmissionSealStatus,
  listAvailableExams,
  loadAnswerState,
  loadExamSessionPaperAssets,
  loadExamTakingPayload,
  sealSubmissionStrict,
  sendHeartbeat,
  startExamSessionStrict,
  supersedeAnswerFile,
  sealSubmission,
  startExamSession,
  uploadAnswerFile,
  uploadAnswerFileStrict,
} from './api';
import { ExamTakingApiError } from './contracts';

vi.mock('../../shared/api/httpClient', () => ({
  httpRequest: vi.fn(),
}));

vi.mock('../submissionProcessing/api', () => ({
  getSubmissionProcessingStatus: vi.fn(),
}));

const mockedHttpRequest = vi.mocked(httpRequest);
const mockedGetSubmissionProcessingStatus = vi.mocked(getSubmissionProcessingStatus);
const ok = <T,>(data: T) => ({ ok: true as const, success: true as const, data, message: null, error: null });
const err = (code: string, message: string, details: Record<string, unknown> = {}) => ({
  ok: false as const,
  success: false as const,
  data: null,
  message: null,
  error: { code, message, details, request_id: 'req-test' },
});

beforeEach(() => {
  vi.clearAllMocks();
  mockedHttpRequest.mockResolvedValue(ok({}));
  mockedGetSubmissionProcessingStatus.mockResolvedValue({ ok: true, data: { overall_status: 'WAITING_GRADING' } as never });
});

describe('examTaking api client', () => {
  test('loads available exams through backend API path only', async () => {
    await listAvailableExams();
    expect(mockedHttpRequest).toHaveBeenCalledWith('/exam-sessions');
  });

  test('loads resolved runtime payload through delivery backend route', async () => {
    await loadExamTakingPayload(55);
    expect(mockedHttpRequest).toHaveBeenCalledWith('/exam-sessions/55/runtime');
  });

  test('getExamRuntimePayload uses strict runtime backend route and unwraps success', async () => {
    mockedHttpRequest.mockResolvedValueOnce(ok({ session: { exam_session_id: 55 }, submission: { exam_submission_id: 10, exam_session_id: 55 }, paper: { exam_session_id: 55, generated_exam_instance_id: 1, questions: [] }, client_revision: 1 }));

    await expect(getExamRuntimePayload(55)).resolves.toEqual(
      expect.objectContaining({ session: expect.objectContaining({ exam_session_id: 55 }) })
    );
    expect(mockedHttpRequest).toHaveBeenCalledWith('/exam-sessions/55/runtime', undefined);
  });

  test('bindExamDevice uses exact backend path method and payload', async () => {
    await bindExamDevice(55, { station_id: 9, device_id: 12, bind_reason: 'INITIAL_START', hostname: 'pc01' });
    const [path, init] = mockedHttpRequest.mock.calls[0];
    expect(path).toBe('/exam-sessions/55/device-bind');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(String(init?.body))).toEqual({ station_id: 9, device_id: 12, bind_reason: 'INITIAL_START', hostname: 'pc01' });
  });

  test('starts exam session through delivery backend route', async () => {
    await startExamSession(55);
    const [path, init] = mockedHttpRequest.mock.calls[0];
    expect(path).toBe('/exam-sessions/55/start');
    expect(path).not.toContain('worker');
    expect(init?.method).toBe('POST');
  });

  test('startExamSessionStrict uses exact backend path and payload', async () => {
    await startExamSessionStrict(55, { metadata_json: { source: 'strict-start' } });
    const [path, init] = mockedHttpRequest.mock.calls[0];
    expect(path).toBe('/exam-sessions/55/start');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(String(init?.body))).toEqual({ metadata_json: { source: 'strict-start' } });
  });

  test('sendHeartbeat uses exact backend path and payload', async () => {
    await sendHeartbeat(55, { last_activity_at: '2026-05-23T10:00:00Z', metadata_json: { idle: false } });
    const [path, init] = mockedHttpRequest.mock.calls[0];
    expect(path).toBe('/exam-sessions/55/heartbeat');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(String(init?.body))).toEqual({
      last_activity_at: '2026-05-23T10:00:00Z',
      metadata_json: { idle: false },
    });
  });

  test('loads paper assets through delivery backend route', async () => {
    await loadExamSessionPaperAssets(55);
    expect(mockedHttpRequest).toHaveBeenCalledWith('/exam-sessions/55/paper-assets');
  });

  test('autosave uses submission backend route and payload envelope', async () => {
    await autosaveAnswers(12001, {
      answers: [
        {
          generated_exam_question_id: 501,
          answer_type: 'SQL_TEXT',
          answer_text: 'select 1',
          client_revision: 2,
        },
      ],
      clientRevision: 2,
      clientSequenceNo: 3,
      idempotencyKey: 'autosave-test',
    });

    const [path, init] = mockedHttpRequest.mock.calls[0];
    expect(path).toBe('/submissions/12001/answers/autosave');
    expect(path).not.toContain('worker');
    expect(init?.method).toBe('POST');
    const body = JSON.parse(String(init?.body));
    expect(body.idempotency_key).toBe('autosave-test');
    expect(body.answers[0].answer_text).toBe('select 1');
  });

  test('getAnswerState uses strict backend path', async () => {
    await getAnswerState(12001);
    expect(mockedHttpRequest).toHaveBeenCalledWith('/submissions/12001/answers/state', undefined);
  });

  test('file upload uses multipart backend route only', async () => {
    const file = new File(['zip'], 'bai_lam.zip', { type: 'application/zip' });
    await uploadAnswerFile(12001, 501, file, { source: 'test' });

    const [path, init] = mockedHttpRequest.mock.calls[0];
    expect(path).toBe('/submissions/12001/answers/501/file');
    expect(path).not.toContain('worker');
    expect(init?.method).toBe('POST');
    expect(init?.body).toBeInstanceOf(FormData);
  });

  test('strict file upload keeps multipart form payload', async () => {
    const file = new File(['zip'], 'bai_lam.zip', { type: 'application/zip' });
    await uploadAnswerFileStrict(12001, 501, file, { source: 'test' });

    const [path, init] = mockedHttpRequest.mock.calls[0];
    expect(path).toBe('/submissions/12001/answers/501/file');
    expect(init?.body).toBeInstanceOf(FormData);
  });

  test('getAnswerFileMetadata uses exact backend path', async () => {
    await getAnswerFileMetadata(12001, 501);
    expect(mockedHttpRequest).toHaveBeenCalledWith('/submissions/12001/answers/501/file', undefined);
  });

  test('supersedeAnswerFile uses delete on exact backend path', async () => {
    await supersedeAnswerFile(12001, 501);
    const [path, init] = mockedHttpRequest.mock.calls[0];
    expect(path).toBe('/submissions/12001/answers/501/file');
    expect(init?.method).toBe('DELETE');
  });

  test('loads answer state through submission backend route', async () => {
    await loadAnswerState(12001);
    expect(mockedHttpRequest).toHaveBeenCalledWith('/submissions/12001/answers/state');
  });

  test('getSealPreflight uses exact backend path', async () => {
    await getSealPreflight(12001);
    expect(mockedHttpRequest).toHaveBeenCalledWith('/submissions/12001/submit-preflight', undefined);
  });

  test('seal uses submission backend route and does not call worker', async () => {
    await sealSubmission(12001, 'seal-test');
    const [path, init] = mockedHttpRequest.mock.calls[0];
    expect(path).toBe('/submissions/12001/seal');
    expect(path).not.toContain('worker');
    expect(init?.method).toBe('POST');
  });

  test('sealSubmissionStrict sends idempotency key and metadata payload', async () => {
    await sealSubmissionStrict(12001, {
      idempotency_key: 'seal-test',
      reason: 'STUDENT_SUBMIT',
      metadata_json: { source: 'strict-seal' },
    });
    const [path, init] = mockedHttpRequest.mock.calls[0];
    expect(path).toBe('/submissions/12001/seal');
    expect(JSON.parse(String(init?.body))).toEqual({
      seal_idempotency_key: 'seal-test',
      reason: 'STUDENT_SUBMIT',
      metadata_json: { source: 'strict-seal' },
    });
  });

  test('getSubmissionSealStatus uses exact backend path', async () => {
    await getSubmissionSealStatus(12001);
    expect(mockedHttpRequest).toHaveBeenCalledWith('/submissions/12001/seal', undefined);
  });

  test('backend envelope failure throws ExamTakingApiError and preserves permission_denied', async () => {
    mockedHttpRequest.mockResolvedValueOnce(err('permission_denied', 'Insufficient permissions'));

    await expect(getExamRuntimePayload(55)).rejects.toMatchObject({
      name: 'ExamTakingApiError',
      code: 'permission_denied',
      message: 'Insufficient permissions',
    });
  });

  test('409 submission_not_eligible is preserved', async () => {
    mockedHttpRequest.mockResolvedValueOnce(err('submission_not_eligible', 'Submission is not eligible'));

    await expect(getSealPreflight(12001)).rejects.toMatchObject({
      code: 'submission_not_eligible',
      message: 'Submission is not eligible',
    });
  });

  test('422 validation error is preserved', async () => {
    mockedHttpRequest.mockResolvedValueOnce(err('validation_error', 'Request validation failed'));

    await expect(bindExamDevice(55, { station_id: 0 })).rejects.toMatchObject({
      code: 'validation_error',
      message: 'Request validation failed',
    });
  });

  test('network failure is not reported as success', async () => {
    mockedHttpRequest.mockResolvedValueOnce(err('network_error', 'Network request failed'));

    await expect(getExamRuntimePayload(55)).rejects.toBeInstanceOf(ExamTakingApiError);
  });

  test('getProcessingStatus delegates to submission processing API and preserves errors', async () => {
    mockedGetSubmissionProcessingStatus.mockResolvedValueOnce({
      ok: false,
      status: 403,
      error: {
        code: 'permission_denied',
        message: 'Forbidden',
        details: {},
        request_id: null,
      },
    });

    await expect(getProcessingStatus(12001)).rejects.toMatchObject({
      code: 'permission_denied',
      message: 'Forbidden',
      status: 403,
    });
  });
});

