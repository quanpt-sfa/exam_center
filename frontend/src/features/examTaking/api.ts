import { httpRequest } from '../../shared/api/httpClient';
import { getSubmissionProcessingStatus as getSubmissionProcessingStatusResult } from '../submissionProcessing/api';
import type {
  AnswerAutosaveRequest,
  AnswerAutosaveResponse,
  AnswerFileMetadataResponse,
  AnswerFileSupersedeResponse,
  AnswerFileUploadResponse,
  AnswerStateResponse,
  ExamRuntimePayload,
  ExamSessionPaperAssetListResponse,
  ExamTakingApiErrorPayload,
  ProcessingStatusResponse,
  RuntimeDeviceBindingRequirement,
  SealPreflightResponse,
  SealRequest,
  SealResponse,
  StudentExamSession,
} from './types';
import { ExamTakingApiError } from './contracts';

type ExamSessionListResponse = {
  items: StudentExamSession[];
};

type LegacyApiResult<T> = Awaited<ReturnType<typeof httpRequest<T>>>;

type StartExamSessionPayload = {
  metadata_json?: Record<string, unknown>;
};

type StartExamSessionResponse = ExamRuntimePayload['session'] & { timer?: ExamRuntimePayload['timer'] };

type DeviceBindRequest = {
  station_id: number;
  device_id?: number;
  bind_reason?: string;
  ip_address?: string | null;
  hostname?: string | null;
  client_fingerprint?: string | null;
  metadata_json?: Record<string, unknown>;
};

type HeartbeatRequest = {
  last_activity_at?: string | null;
  metadata_json?: Record<string, unknown>;
};

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : {};
}

function asNullableNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function normalizeRuntimePayload(payload: ExamRuntimePayload): ExamRuntimePayload {
  const raw = asRecord(payload as unknown);
  const session = asRecord(raw.session);
  const activeDeviceBinding = asRecord(raw.active_device_binding);

  const legacyBindingRequired = raw.device_binding_required === true;
  const hasModernRequirement = raw.device_binding_requirement && typeof raw.device_binding_requirement === 'object';
  const hasModernBinding = raw.device_binding && typeof raw.device_binding === 'object';

  if (!legacyBindingRequired && hasModernRequirement && hasModernBinding) {
    return payload;
  }

  const assignedStationId = asNullableNumber(session.assigned_station_id);
  const plannedDeviceId = asNullableNumber(session.planned_device_id);
  const activeStationId = asNullableNumber(activeDeviceBinding.station_id);
  const activeDeviceId = asNullableNumber(activeDeviceBinding.device_id);
  const bindingStatus = String(activeDeviceBinding.binding_status || '').trim().toUpperCase();
  const hasActiveBinding = bindingStatus === 'ACTIVE' || activeStationId !== null || activeDeviceId !== null;

  return {
    ...payload,
    device_binding_requirement: hasModernRequirement
      ? payload.device_binding_requirement
      : {
          required: legacyBindingRequired,
          can_bind: legacyBindingRequired ? assignedStationId !== null : true,
          bind_reason: legacyBindingRequired ? 'INITIAL_START' : null,
          station_id: assignedStationId,
          device_id: plannedDeviceId,
          status: hasActiveBinding ? 'ACTIVE' : legacyBindingRequired ? 'REQUIRED' : 'OPTIONAL',
        },
    device_binding: hasModernBinding
      ? payload.device_binding
      : {
          exam_session_id: asNullableNumber(session.exam_session_id),
          station_id: activeStationId,
          device_id: activeDeviceId,
          binding_status: String(activeDeviceBinding.binding_status || ''),
          station_code: String(activeDeviceBinding.station_code || ''),
          device_code: String(activeDeviceBinding.device_code || ''),
          asset_tag: String(activeDeviceBinding.asset_tag || ''),
          bound_at: String(activeDeviceBinding.bound_at || ''),
        },
  };
}

function mapApiErrorPayload<T>(response: LegacyApiResult<T>, status?: number): ExamTakingApiErrorPayload {
  return {
    code: response.error.code,
    message: response.error.message,
    details: response.error.details,
    request_id: response.error.request_id,
    status,
  };
}

async function requestOrThrow<T>(path: string, init?: RequestInit, status?: number): Promise<T> {
  const response = await httpRequest<T>(path, init);
  if (!response.ok) {
    throw new ExamTakingApiError(mapApiErrorPayload(response, status));
  }
  return response.data;
}

function defaultMetadata(source: string): Record<string, unknown> {
  return { source };
}

export function listAvailableExams() {
  return httpRequest<ExamSessionListResponse>('/exam-sessions');
}

export function getExamRuntimePayload(examSessionId: string | number) {
  return requestOrThrow<ExamRuntimePayload>(`/exam-sessions/${examSessionId}/runtime`).then(normalizeRuntimePayload);
}

export function loadExamTakingPayload(examSessionId: string | number) {
  return httpRequest<ExamRuntimePayload>(`/exam-sessions/${examSessionId}/runtime`).then((response) =>
    response.ok
      ? {
          ...response,
          data: normalizeRuntimePayload(response.data),
        }
      : response
  );
}

export function bindExamDevice(examSessionId: string | number, payload: DeviceBindRequest) {
  return requestOrThrow<RuntimeDeviceBindingRequirement>(`/exam-sessions/${examSessionId}/device-bind`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function startExamSession(examSessionId: string | number, payload?: StartExamSessionPayload) {
  const body = {
    metadata_json: payload?.metadata_json ?? defaultMetadata('frontend_exam_taking'),
  };

  return httpRequest<StartExamSessionResponse>(
    `/exam-sessions/${examSessionId}/start`,
    {
      method: 'POST',
      body: JSON.stringify(body),
    }
  );
}

export function startExamSessionStrict(examSessionId: string | number, payload?: StartExamSessionPayload) {
  const body = {
    metadata_json: payload?.metadata_json ?? defaultMetadata('frontend_exam_taking'),
  };
  return requestOrThrow<StartExamSessionResponse>(`/exam-sessions/${examSessionId}/start`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function sendHeartbeat(examSessionId: string | number, payload?: HeartbeatRequest) {
  return requestOrThrow<ExamRuntimePayload['session'] & { timer?: ExamRuntimePayload['timer'] }>(
    `/exam-sessions/${examSessionId}/heartbeat`,
    {
      method: 'POST',
      body: JSON.stringify({
        last_activity_at: payload?.last_activity_at ?? null,
        metadata_json: payload?.metadata_json ?? defaultMetadata('frontend_exam_taking_heartbeat'),
      }),
    }
  );
}

export function loadExamSessionPaperAssets(examSessionId: string | number) {
  return httpRequest<ExamSessionPaperAssetListResponse>(`/exam-sessions/${examSessionId}/paper-assets`);
}

export function autosaveAnswers(
  examSubmissionId: number,
  input: AnswerAutosaveRequest | {
    answers: AnswerAutosaveRequest['answers'];
    clientRevision: number;
    clientSequenceNo: number;
    idempotencyKey: string;
  }
) {
  const requestBody: AnswerAutosaveRequest = 'idempotency_key' in input
    ? input
    : {
        idempotency_key: input.idempotencyKey,
        client_sequence_no: input.clientSequenceNo,
        client_saved_at: new Date().toISOString(),
        client_revision: input.clientRevision,
        metadata_json: defaultMetadata('frontend_exam_taking'),
        answers: input.answers.map((answer) => ({
          generated_exam_question_id: answer.generated_exam_question_id,
          answer_type: answer.answer_type,
          answer_text: answer.answer_text ?? null,
          answer_payload_json: answer.answer_payload_json ?? null,
          answer_length: answer.answer_text?.length ?? answer.answer_length ?? 0,
          client_revision: answer.client_revision ?? null,
          metadata_json: answer.metadata_json ?? null,
          answer_hash: answer.answer_hash ?? null,
        })),
      };

  return httpRequest<AnswerAutosaveResponse>(`/submissions/${examSubmissionId}/answers/autosave`, {
    method: 'POST',
    body: JSON.stringify(requestBody),
  });
}

export function autosaveAnswersStrict(examSubmissionId: number, input: AnswerAutosaveRequest) {
  return requestOrThrow<AnswerAutosaveResponse>(`/submissions/${examSubmissionId}/answers/autosave`, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export function uploadAnswerFile(
  examSubmissionId: number,
  generatedExamQuestionId: number,
  file: File,
  metadataJson?: Record<string, unknown>
) {
  const formData = new FormData();
  formData.append('file', file);
  if (metadataJson) {
    formData.append('metadata_json', JSON.stringify(metadataJson));
  }
  return httpRequest<AnswerFileUploadResponse>(
    `/submissions/${examSubmissionId}/answers/${generatedExamQuestionId}/file`,
    {
      method: 'POST',
      body: formData,
    }
  );
}

export function uploadAnswerFileStrict(
  examSubmissionId: number,
  generatedExamQuestionId: number,
  file: File,
  metadataJson?: Record<string, unknown>
) {
  const formData = new FormData();
  formData.append('file', file);
  if (metadataJson) {
    formData.append('metadata_json', JSON.stringify(metadataJson));
  }
  return requestOrThrow<AnswerFileUploadResponse>(`/submissions/${examSubmissionId}/answers/${generatedExamQuestionId}/file`, {
    method: 'POST',
    body: formData,
  });
}

export function getAnswerState(examSubmissionId: number) {
  return requestOrThrow<AnswerStateResponse>(`/submissions/${examSubmissionId}/answers/state`);
}

export function loadAnswerState(examSubmissionId: number) {
  return httpRequest<AnswerStateResponse>(`/submissions/${examSubmissionId}/answers/state`);
}

export function getAnswerFileMetadata(examSubmissionId: number, generatedExamQuestionId: number) {
  return requestOrThrow<AnswerFileMetadataResponse>(
    `/submissions/${examSubmissionId}/answers/${generatedExamQuestionId}/file`
  );
}

export function getAnswerFileContent(examSubmissionId: number, generatedExamQuestionId: number) {
  return `/api/v1/submissions/${examSubmissionId}/answers/${generatedExamQuestionId}/file/content`;
}

export function supersedeAnswerFile(examSubmissionId: number, generatedExamQuestionId: number) {
  return requestOrThrow<AnswerFileSupersedeResponse>(
    `/submissions/${examSubmissionId}/answers/${generatedExamQuestionId}/file`,
    {
      method: 'DELETE',
    }
  );
}

export function getSealPreflight(examSubmissionId: number) {
  return requestOrThrow<SealPreflightResponse>(`/submissions/${examSubmissionId}/submit-preflight`);
}

export function sealSubmission(examSubmissionId: number, payload: string | SealRequest) {
  const requestBody: SealRequest = typeof payload === 'string'
    ? {
        seal_idempotency_key: payload,
        reason: 'STUDENT_SUBMIT',
        metadata_json: defaultMetadata('frontend_exam_taking'),
      }
    : {
        reason: payload.reason ?? 'STUDENT_SUBMIT',
        seal_idempotency_key: payload.seal_idempotency_key ?? payload.idempotency_key,
        metadata_json: payload.metadata_json ?? defaultMetadata('frontend_exam_taking'),
      };

  return httpRequest<SealResponse>(`/submissions/${examSubmissionId}/seal`, {
    method: 'POST',
    body: JSON.stringify(requestBody),
  });
}

export function sealSubmissionStrict(examSubmissionId: number, payload: SealRequest) {
  const requestBody: SealRequest = {
    reason: payload.reason ?? 'STUDENT_SUBMIT',
    seal_idempotency_key: payload.seal_idempotency_key ?? payload.idempotency_key,
    metadata_json: payload.metadata_json ?? defaultMetadata('frontend_exam_taking'),
  };
  return requestOrThrow<SealResponse>(`/submissions/${examSubmissionId}/seal`, {
    method: 'POST',
    body: JSON.stringify(requestBody),
  });
}

export function getSubmissionSealStatus(examSubmissionId: number) {
  return requestOrThrow<SealResponse>(`/submissions/${examSubmissionId}/seal`);
}

export function getSealStatus(examSubmissionId: number) {
  return httpRequest<SealResponse>(`/submissions/${examSubmissionId}/seal`);
}

export async function getProcessingStatus(examSubmissionId: number): Promise<ProcessingStatusResponse> {
  const result = await getSubmissionProcessingStatusResult(examSubmissionId);
  if (!result.ok) {
    throw new ExamTakingApiError({
      code: result.error.code,
      message: result.error.message,
      details: result.error.details,
      request_id: result.error.request_id,
      status: result.status,
    });
  }
  return result.data;
}
