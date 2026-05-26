import { listAvailableExams, loadExamTakingPayload } from './api';
import type { ExamTakingPayload, StudentExamSession } from './types';

export type ExamListItem = StudentExamSession;
export type { ExamTakingPayload };

export async function listExams() {
  const response = await listAvailableExams();
  if (!response.ok) {
    return response;
  }

  return {
    ...response,
    data: response.data.items,
  };
}

export function getExamTakingPayload(id: string) {
  return loadExamTakingPayload(id);
}
