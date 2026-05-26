import { httpRequest } from '../../shared/api/httpClient';
import type { CurrentUser } from '../auth/authApi';
import type { StudentExamSession } from '../examTaking/types';

export type StudentExamClass = {
  test_class_id: number;
  exam_submission_id?: number | null;
  test_class_name: string;
  start_date?: string | null;
  end_date?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  duration?: number | null;
  room?: string | null;
  is_open?: boolean;
  class_name?: string | null;
  subject_name?: string | null;
  subject_code?: string | null;
  slot_name?: string | null;
  seat_number?: string | number | null;
  status?: string | null;
  total_score?: number | null;
  started_at?: string | null;
  submitted_at?: string | null;
};

export type DashboardData =
  | { ok: true; user: CurrentUser; exams: StudentExamClass[] }
  | { ok: false; error: string };

const studentRoles = new Set(['STUDENT', 'SV', 'SINHVIEN']);

export function hasStudentRole(user: CurrentUser): boolean {
  return user.roles.some((role) => studentRoles.has(String(role).toUpperCase()));
}

export async function loadDashboardData(): Promise<DashboardData> {
  const userResponse = await httpRequest<CurrentUser>('/auth/me');
  if (!userResponse.ok) {
    return { ok: false, error: userResponse.error.message };
  }

  if (!hasStudentRole(userResponse.data)) {
    return { ok: true, user: userResponse.data, exams: [] };
  }

  const examResponse = await httpRequest<{ items: StudentExamSession[] }>('/exam-sessions');
  if (!examResponse.ok) {
    return { ok: false, error: examResponse.error.message };
  }

  return {
    ok: true,
    user: userResponse.data,
    exams: examResponse.data.items.map((exam) => ({
      test_class_id: exam.exam_session_id,
      exam_submission_id: exam.exam_submission_id,
      test_class_name: exam.sitting_name || exam.exam_name || exam.session_code || `Ca thi #${exam.exam_session_id}`,
      start_date: exam.scheduled_start_at,
      end_date: exam.scheduled_end_at,
      start_time: exam.scheduled_start_at,
      end_time: exam.scheduled_end_at,
      duration: null,
      room: exam.room_code || exam.room_name,
      is_open: !exam.sealed_at && !['ENDED', 'EXPIRED', 'FORCE_CLOSED', 'VOIDED'].includes(String(exam.session_status || '').toUpperCase()),
      class_name: exam.sitting_name,
      subject_name: exam.course_name,
      subject_code: exam.course_code,
      slot_name: exam.session_code,
      seat_number: exam.seat_no,
      status: exam.submission_status || exam.session_status || exam.assignment_status,
      started_at: exam.started_at,
      submitted_at: exam.submitted_at,
    })),
  };
}
