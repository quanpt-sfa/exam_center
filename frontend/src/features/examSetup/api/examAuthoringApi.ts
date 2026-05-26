import { httpRequest } from '../../../shared/api/httpClient';
import type {
  ApiListResponse,
  AtomicFileUploadManualGradingConfigResponse,
  DeliveryProfileUpsertPayload,
  ExamAuthoringBaseData,
  ExamCreatePayload,
  ExamSetupRow,
  ExamUpdatePayload,
  ExamVersionCreatePayload,
  ExamVersionDeliveryProfile,
  ExamVersionPaperAsset,
  ExamVersionQuestionAuthoringItem,
  ExamVersionQuestionAuthoringSummary,
  ExamVersionQuestionAuthoringUpsertPayload,
  ExamVersionUpdatePayload,
  ExpectedAnswerMetadataSummary,
  FileUploadPlaceholderQuestionPayload,
  QuestionGradingProfileCreatePayload,
  QuestionGradingProfilePatchPayload,
  QuestionGradingProfileSummary,
} from './contracts';

export type ExamVersionPublishValidationItem = {
  code: string;
  message: string;
  severity?: string;
  status?: string;
  details?: Record<string, unknown>;
};

export type ExamVersionPublishValidationResult = {
  exam_id: number;
  exam_version_id: number;
  exam_status?: string | null;
  version_status?: string | null;
  exam_modality?: string | null;
  is_valid: boolean;
  missing_items: ExamVersionPublishValidationItem[];
};

async function fetchList(endpoint: string): Promise<ExamSetupRow[]> {
  const response = await httpRequest<ApiListResponse<ExamSetupRow>>(endpoint);
  if (!response.ok) {
    throw new Error(response.error.message);
  }
  return response.data.items ?? [];
}

export async function listExams(): Promise<ExamSetupRow[]> {
  return fetchList('/master-data/exams?page=1&page_size=20');
}

export async function listClassSections(): Promise<ExamSetupRow[]> {
  return fetchList('/master-data/class-sections?page=1&page_size=100');
}

export async function listAssessmentTypes(): Promise<ExamSetupRow[]> {
  return fetchList('/master-data/assessment-types?page=1&page_size=100&is_active=true');
}

export async function loadExamAuthoringBaseData(): Promise<ExamAuthoringBaseData> {
  const [exams, classSections, assessmentTypes] = await Promise.all([listExams(), listClassSections(), listAssessmentTypes()]);
  return { exams, classSections, assessmentTypes };
}

export function loadExamVersions(examId: string): Promise<ExamSetupRow[]> {
  return fetchList(`/master-data/exams/${examId}/versions?page=1&page_size=20`);
}

export function createExam(payload: ExamCreatePayload) {
  return httpRequest<ExamSetupRow>('/master-data/exams', { method: 'POST', body: JSON.stringify(payload) });
}

export function updateExam(examId: string, payload: ExamUpdatePayload) {
  return httpRequest<ExamSetupRow>(`/master-data/exams/${examId}`, { method: 'PATCH', body: JSON.stringify(payload) });
}

export function createExamVersion(examId: string, payload: ExamVersionCreatePayload) {
  return httpRequest<ExamSetupRow>(`/master-data/exams/${examId}/versions`, { method: 'POST', body: JSON.stringify(payload) });
}

export function updateExamVersion(examVersionId: string, payload: ExamVersionUpdatePayload) {
  return httpRequest<ExamSetupRow>(`/master-data/exam-versions/${examVersionId}`, { method: 'PATCH', body: JSON.stringify(payload) });
}

export function validateExamVersion(examVersionId: string) {
  return httpRequest<ExamVersionPublishValidationResult>(`/master-data/exam-versions/${examVersionId}/validate`, {
    method: 'POST',
  });
}

export function publishExamVersion(examVersionId: string) {
  return httpRequest<ExamSetupRow>(`/master-data/exam-versions/${examVersionId}/publish`, { method: 'POST' });
}

export function retireExamVersion(examVersionId: string, reason?: string) {
  return httpRequest<ExamSetupRow>(`/master-data/exam-versions/${examVersionId}/retire`, {
    method: 'POST',
    body: JSON.stringify({ reason: reason ?? null }),
  });
}

export async function loadExamVersionPaperAssets(examId: string, examVersionId: string): Promise<ExamVersionPaperAsset[]> {
  const response = await httpRequest<ApiListResponse<ExamVersionPaperAsset>>(`/master-data/exams/${examId}/versions/${examVersionId}/paper-assets`);
  if (!response.ok) {
    throw new Error(response.error.message);
  }
  return response.data.items ?? [];
}

export function uploadExamVersionPaperAsset(examId: string, examVersionId: string, file: File) {
  const formData = new FormData();
  formData.append('file', file);
  return httpRequest<ExamVersionPaperAsset>(`/master-data/exams/${examId}/versions/${examVersionId}/paper-assets`, { method: 'POST', body: formData });
}

export function retireExamVersionPaperAsset(examId: string, examVersionId: string, paperAssetId: number) {
  return httpRequest<ExamVersionPaperAsset>(`/master-data/exams/${examId}/versions/${examVersionId}/paper-assets/${paperAssetId}/retire`, { method: 'POST' });
}

export async function loadExamVersionDeliveryProfile(examVersionId: string): Promise<ExamVersionDeliveryProfile | null> {
  const response = await httpRequest<ExamVersionDeliveryProfile>(`/master-data/exam-versions/${examVersionId}/delivery-profile`);
  if (!response.ok) {
    if (response.error.code === 'master_data_not_found') {
      return null;
    }
    throw new Error(response.error.message);
  }
  return response.data ?? null;
}

export function upsertExamVersionDeliveryProfile(examVersionId: string, payload: DeliveryProfileUpsertPayload) {
  return httpRequest<ExamVersionDeliveryProfile>(`/master-data/exam-versions/${examVersionId}/delivery-profile`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function loadExamVersionQuestionGradingProfiles(examVersionId: string): Promise<QuestionGradingProfileSummary[]> {
  const response = await httpRequest<ApiListResponse<QuestionGradingProfileSummary>>(`/master-data/exam-versions/${examVersionId}/question-grading-profiles?page=1&page_size=50`);
  if (!response.ok) {
    throw new Error(response.error.message);
  }
  return response.data.items ?? [];
}

export function createExamVersionQuestionGradingProfile(examVersionId: string, payload: QuestionGradingProfileCreatePayload) {
  return httpRequest<QuestionGradingProfileSummary>(`/master-data/exam-versions/${examVersionId}/question-grading-profiles`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function retireQuestionGradingProfile(questionGradingProfileId: number, reason: string) {
  return httpRequest<QuestionGradingProfileSummary>(`/master-data/question-grading-profiles/${questionGradingProfileId}/retire`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

export function patchQuestionGradingProfile(questionGradingProfileId: number, payload: QuestionGradingProfilePatchPayload) {
  return httpRequest<QuestionGradingProfileSummary>(`/master-data/question-grading-profiles/${questionGradingProfileId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function createFileUploadPlaceholderQuestion(examVersionId: string, payload: FileUploadPlaceholderQuestionPayload) {
  return httpRequest<QuestionGradingProfileSummary>(`/master-data/exam-versions/${examVersionId}/file-upload-placeholder-question`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function configureFileUploadManualGrading(examVersionId: string, payload: FileUploadPlaceholderQuestionPayload) {
  return httpRequest<AtomicFileUploadManualGradingConfigResponse>(`/master-data/exam-versions/${examVersionId}/configure-file-upload-manual-grading`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function loadExamVersionQuestions(examVersionId: string): Promise<ExamVersionQuestionAuthoringSummary> {
  const response = await httpRequest<ExamVersionQuestionAuthoringSummary>(`/master-data/exam-versions/${examVersionId}/questions`);
  if (!response.ok) {
    throw new Error(response.error.message);
  }
  return {
    items: Array.isArray(response.data?.items) ? response.data.items : [],
    readiness_summary: {
      ready: Boolean(response.data?.readiness_summary?.ready),
      missing_items: Array.isArray(response.data?.readiness_summary?.missing_items)
        ? response.data.readiness_summary.missing_items
        : [],
    },
  };
}

export function createExamVersionQuestion(examVersionId: string, payload: ExamVersionQuestionAuthoringUpsertPayload) {
  return httpRequest<ExamVersionQuestionAuthoringItem>(`/master-data/exam-versions/${examVersionId}/questions`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateExamVersionQuestion(examVersionId: string, questionTemplateId: number, payload: ExamVersionQuestionAuthoringUpsertPayload) {
  return httpRequest<ExamVersionQuestionAuthoringItem>(`/master-data/exam-versions/${examVersionId}/questions/${questionTemplateId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function getExamVersionExpectedAnswerMetadata(examVersionId: string): Promise<ExpectedAnswerMetadataSummary> {
  const response = await httpRequest<ExpectedAnswerMetadataSummary>(`/master-data/exam-versions/${examVersionId}/expected-answer-metadata`);
  if (!response.ok) {
    throw new Error(response.error.message);
  }
  return (response.data ?? {}) as ExpectedAnswerMetadataSummary;
}