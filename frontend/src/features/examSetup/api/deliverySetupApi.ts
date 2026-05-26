import { httpRequest } from '../../../shared/api/httpClient';
import type {
  ApiListResponse,
  DeliveryExamAssignment,
  DeliveryExamAssignmentCodeImportPayload,
  DeliveryExamAssignmentCodeImportResult,
  DeliveryExamAssignmentCreatePayload,
  DeliveryExamAssignmentUpdatePayload,
  DeliveryProctorAssignment,
  DeliveryProctorCreatePayload,
  DeliveryProctorUpdatePayload,
  DeliverySetupBaseData,
  DeliverySittingRoom,
  DeliverySittingRoomCreatePayload,
  DeliverySittingRoomUpdatePayload,
  DeliveryStationAssignment,
  DeliveryStationAssignmentCreatePayload,
  DeliveryStationAssignmentUpdatePayload,
  ExamSetupRow,
  ExamSittingPrepareResult,
  ModuleStatus,
  SittingClassSection,
  SittingClassSectionsUpdatePayload,
  SittingExamVersionPayload,
  SittingReadiness,
  SetupSitting,
  SetupSittingCreatePayload,
  SetupSittingUpdatePayload,
} from './contracts';

function asString(value: unknown, fallback = '-'): string {
  if (value === null || value === undefined || value === '') {
    return fallback;
  }
  return String(value);
}

async function fetchList(endpoint: string): Promise<ExamSetupRow[]> {
  const response = await httpRequest<ApiListResponse<ExamSetupRow>>(endpoint);
  if (!response.ok) {
    throw new Error(response.error.message);
  }
  return response.data.items ?? [];
}

async function fetchModuleStatus(endpoint: string): Promise<ModuleStatus> {
  const response = await httpRequest<Omit<ModuleStatus, 'endpoint'>>(endpoint);
  if (!response.ok) {
    return { module: endpoint, status: 'error', ready: false, endpoint, error: response.error.message };
  }
  return {
    module: asString(response.data.module, endpoint),
    status: asString(response.data.status, 'unknown'),
    ready: Boolean(response.data.ready ?? response.data.status === 'ok'),
    endpoint,
  };
}

function normalizeReadinessIssue(issue: unknown): SittingReadiness['blockers'][number] {
  const value = typeof issue === 'object' && issue !== null ? (issue as Record<string, unknown>) : {};
  return {
    code: asString(value.code, 'unknown'),
    message: asString(value.message, asString(value.code, 'Readiness issue')),
    severity: value.severity ? asString(value.severity) : undefined,
    status: value.status ? asString(value.status) : undefined,
    details: typeof value.details === 'object' && value.details !== null ? (value.details as Record<string, unknown>) : undefined,
  };
}

function normalizeSittingReadiness(data: Partial<SittingReadiness> | null | undefined, examSittingId: number): SittingReadiness {
  const explicitBlockers = Array.isArray(data?.blockers) ? data.blockers.map(normalizeReadinessIssue) : [];
  const blockingErrors = Array.isArray(data?.blocking_errors) ? data.blocking_errors.map(normalizeReadinessIssue) : [];
  const missingItems = Array.isArray(data?.missing_items) ? data.missing_items.map(normalizeReadinessIssue) : [];
  const warnings = Array.isArray(data?.warnings) ? data.warnings.map(normalizeReadinessIssue) : [];

  return {
    exam_sitting_id: Number(data?.exam_sitting_id ?? examSittingId),
    exam_version_id: data?.exam_version_id ?? null,
    sitting_status: data?.sitting_status ?? null,
    randomization_mode: data?.randomization_mode ?? null,
    shuffle_questions: Boolean(data?.shuffle_questions),
    shuffle_options: Boolean(data?.shuffle_options),
    prepare_strategy: data?.prepare_strategy ?? null,
    summary: typeof data?.summary === 'string' ? data.summary : null,
    can_prepare: typeof data?.can_prepare === 'boolean' ? data.can_prepare : null,
    can_open: typeof data?.can_open === 'boolean' ? data.can_open : null,
    created_session_count: typeof data?.created_session_count === 'number' ? data.created_session_count : null,
    reused_session_count: typeof data?.reused_session_count === 'number' ? data.reused_session_count : null,
    created_generated_question_count:
      typeof data?.created_generated_question_count === 'number' ? data.created_generated_question_count : null,
    missing_items: missingItems,
    blocking_errors: blockingErrors,
    ready: Boolean(data?.ready),
    blockers: explicitBlockers.length > 0 ? explicitBlockers : [...blockingErrors, ...missingItems],
    warnings,
    counts: {
      assignment_count: Number(data?.counts?.assignment_count ?? 0),
      room_count: Number(data?.counts?.room_count ?? 0),
      station_assignment_count: Number(data?.counts?.station_assignment_count ?? 0),
      proctor_count: Number(data?.counts?.proctor_count ?? 0),
      question_source_count: Number(data?.counts?.question_source_count ?? 0),
      paper_asset_count: Number(data?.counts?.paper_asset_count ?? 0),
    },
  };
}

export async function listExamsForDelivery(): Promise<ExamSetupRow[]> {
  return fetchList('/master-data/exams?page=1&page_size=20');
}

export async function listRooms(): Promise<ExamSetupRow[]> {
  return fetchList('/master-data/facilities/rooms?page=1&page_size=100');
}

export async function listStations(): Promise<ExamSetupRow[]> {
  return fetchList('/master-data/facilities/stations?page=1&page_size=100');
}

export async function listStudents(): Promise<ExamSetupRow[]> {
  return fetchList('/master-data/students?page=1&page_size=20');
}

export async function listInstructors(): Promise<ExamSetupRow[]> {
  return fetchList('/master-data/instructors?page=1&page_size=20');
}

export function loadRoomStations(roomId: number): Promise<ExamSetupRow[]> {
  return fetchList(`/master-data/rooms/${roomId}/stations?page=1&page_size=200`);
}

export async function listClassSectionsForDelivery(): Promise<ExamSetupRow[]> {
  return fetchList('/master-data/class-sections?page=1&page_size=200');
}

export async function loadDeliverySetupBaseData(): Promise<DeliverySetupBaseData> {
  const [exams, classSections, rooms, stations, students, instructors, modules] = await Promise.all([
    listExamsForDelivery(),
    listClassSectionsForDelivery().catch(() => [] as ExamSetupRow[]),
    listRooms(),
    listStations(),
    listStudents(),
    listInstructors(),
    Promise.all([
      fetchModuleStatus('/delivery/status'),
      fetchModuleStatus('/submission/status'),
      fetchModuleStatus('/capture/status'),
      fetchModuleStatus('/grading/status'),
    ]),
  ]);
  return { exams, classSections, rooms, stations, students, instructors, modules };
}

export async function listSetupSittings(): Promise<SetupSitting[]> {
  const response = await httpRequest<ApiListResponse<SetupSitting>>('/delivery/setup/sittings');
  if (!response.ok) {
    throw new Error(response.error.message);
  }
  return response.data.items ?? [];
}

export function createSetupSitting(payload: SetupSittingCreatePayload) {
  return httpRequest<SetupSitting>('/delivery/setup/sittings', { method: 'POST', body: JSON.stringify(payload) });
}

export function updateSetupSitting(examSittingId: string, payload: SetupSittingUpdatePayload) {
  return httpRequest<SetupSitting>(`/delivery/setup/sittings/${examSittingId}`, { method: 'PATCH', body: JSON.stringify(payload) });
}

export async function listDeliverySittings(): Promise<SetupSitting[]> {
  const response = await httpRequest<ApiListResponse<SetupSitting>>('/delivery/exam-sittings');
  if (!response.ok) {
    throw new Error(response.error.message);
  }
  return response.data.items ?? [];
}

export function createDeliverySitting(payload: SetupSittingCreatePayload) {
  return httpRequest<SetupSitting>('/delivery/exam-sittings', {
    method: 'POST',
    body: JSON.stringify({
      exam_version_id: payload.exam_version_id,
      sitting_code: payload.sitting_code,
      sitting_name: payload.sitting_name,
      scheduled_start_at: payload.scheduled_start_at,
      scheduled_end_at: payload.scheduled_end_at,
      sitting_status: payload.status,
    }),
  });
}

export function updateDeliverySitting(examSittingId: string, payload: SetupSittingUpdatePayload) {
  return httpRequest<SetupSitting>(`/delivery/exam-sittings/${examSittingId}`, { method: 'PATCH', body: JSON.stringify(payload) });
}

export function assignSittingExamVersion(examSittingId: string, payload: SittingExamVersionPayload) {
  return httpRequest<SetupSitting>(`/delivery/exam-sittings/${examSittingId}/exam-version`, { method: 'PATCH', body: JSON.stringify(payload) });
}

export function changeExamSittingStatus(examSittingId: string, sittingStatus: string) {
  return httpRequest<SetupSitting>(`/delivery/exam-sittings/${examSittingId}/status`, {
    method: 'POST',
    body: JSON.stringify({ sitting_status: sittingStatus }),
  });
}

export async function getExamSittingReadiness(examSittingId: number): Promise<SittingReadiness> {
  const response = await httpRequest<SittingReadiness>(`/delivery/exam-sittings/${examSittingId}/readiness`);
  if (!response.ok) {
    throw new Error(response.error.message);
  }
  return normalizeSittingReadiness(response.data, examSittingId);
}

export function prepareExamSittingRuntime(examSittingId: string) {
  return httpRequest<ExamSittingPrepareResult>(`/delivery/exam-sittings/${examSittingId}/prepare`, { method: 'POST' });
}

export async function listSittingRooms(examSittingId: number): Promise<DeliverySittingRoom[]> {
  const response = await httpRequest<ApiListResponse<DeliverySittingRoom>>(`/delivery/exam-sittings/${examSittingId}/rooms`);
  if (!response.ok) {
    throw new Error(response.error.message);
  }
  return response.data.items ?? [];
}

export function createSittingRoom(examSittingId: number, payload: DeliverySittingRoomCreatePayload) {
  return httpRequest<DeliverySittingRoom>(`/delivery/exam-sittings/${examSittingId}/rooms`, { method: 'POST', body: JSON.stringify(payload) });
}

export function updateSittingRoom(examSittingRoomId: number, payload: DeliverySittingRoomUpdatePayload) {
  return httpRequest<DeliverySittingRoom>(`/delivery/exam-sitting-rooms/${examSittingRoomId}`, { method: 'PATCH', body: JSON.stringify(payload) });
}

export function cancelSittingRoom(examSittingRoomId: number) {
  return httpRequest<DeliverySittingRoom>(`/delivery/exam-sitting-rooms/${examSittingRoomId}`, { method: 'DELETE' });
}

export async function listRoomProctors(examSittingRoomId: number): Promise<DeliveryProctorAssignment[]> {
  const response = await httpRequest<ApiListResponse<DeliveryProctorAssignment>>(`/delivery/exam-sitting-rooms/${examSittingRoomId}/proctors`);
  if (!response.ok) {
    throw new Error(response.error.message);
  }
  return response.data.items ?? [];
}

export function createRoomProctor(examSittingRoomId: number, payload: DeliveryProctorCreatePayload) {
  return httpRequest<DeliveryProctorAssignment>(`/delivery/exam-sitting-rooms/${examSittingRoomId}/proctors`, { method: 'POST', body: JSON.stringify(payload) });
}

export function updateRoomProctor(proctorAssignmentId: number, payload: DeliveryProctorUpdatePayload) {
  return httpRequest<DeliveryProctorAssignment>(`/delivery/proctor-assignments/${proctorAssignmentId}`, { method: 'PATCH', body: JSON.stringify(payload) });
}

export function cancelRoomProctor(proctorAssignmentId: number) {
  return httpRequest<DeliveryProctorAssignment>(`/delivery/proctor-assignments/${proctorAssignmentId}`, { method: 'DELETE' });
}

export async function listExamAssignments(examSittingId: number): Promise<DeliveryExamAssignment[]> {
  const response = await httpRequest<ApiListResponse<DeliveryExamAssignment>>(`/delivery/exam-sittings/${examSittingId}/assignments`);
  if (!response.ok) {
    throw new Error(response.error.message);
  }
  return response.data.items ?? [];
}

export function createExamAssignment(examSittingId: number, payload: DeliveryExamAssignmentCreatePayload) {
  return httpRequest<DeliveryExamAssignment>(`/delivery/exam-sittings/${examSittingId}/assignments`, { method: 'POST', body: JSON.stringify(payload) });
}

export function updateExamAssignment(examAssignmentId: number, payload: DeliveryExamAssignmentUpdatePayload) {
  return httpRequest<DeliveryExamAssignment>(`/delivery/exam-assignments/${examAssignmentId}`, { method: 'PATCH', body: JSON.stringify(payload) });
}

export function importExamAssignmentsByCode(payload: DeliveryExamAssignmentCodeImportPayload) {
  return httpRequest<DeliveryExamAssignmentCodeImportResult>('/delivery/exam-assignments/import-by-code', { method: 'POST', body: JSON.stringify(payload) });
}

export async function listSeatingPlan(examSittingId: number): Promise<DeliveryStationAssignment[]> {
  const response = await httpRequest<ApiListResponse<DeliveryStationAssignment>>(`/delivery/exam-sittings/${examSittingId}/seating-plan`);
  if (!response.ok) {
    throw new Error(response.error.message);
  }
  return response.data.items ?? [];
}

export function assignExamStation(examAssignmentId: number, payload: DeliveryStationAssignmentCreatePayload) {
  return httpRequest<DeliveryStationAssignment>(`/delivery/exam-assignments/${examAssignmentId}/station`, { method: 'POST', body: JSON.stringify(payload) });
}

export function updateExamStationAssignment(stationAssignmentId: number, payload: DeliveryStationAssignmentUpdatePayload) {
  return httpRequest<DeliveryStationAssignment>(`/delivery/station-assignments/${stationAssignmentId}`, { method: 'PATCH', body: JSON.stringify(payload) });
}

export async function listSittingClassSections(examSittingId: number): Promise<SittingClassSection[]> {
  const response = await httpRequest<ApiListResponse<SittingClassSection>>(
    `/delivery/exam-sittings/${examSittingId}/class-sections`
  );
  if (!response.ok) {
    throw new Error(response.error.message);
  }
  return response.data.items ?? [];
}

export function updateSittingClassSections(examSittingId: number, payload: SittingClassSectionsUpdatePayload) {
  return httpRequest<{ items: SittingClassSection[] }>(
    `/delivery/exam-sittings/${examSittingId}/class-sections`,
    { method: 'PUT', body: JSON.stringify(payload) }
  );
}

export function importAssignmentsFromClassSections(examSittingId: number) {
  return httpRequest<{ created_count: number; error_count: number }>(
    `/delivery/exam-sittings/${examSittingId}/assignments/import-from-class-sections`,
    { method: 'POST' }
  );
}