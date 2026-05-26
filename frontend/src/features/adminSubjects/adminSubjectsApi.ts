import { httpRequest } from '../../shared/api/httpClient';

export type SubjectRow = {
  subject_id: number;
  subject_code: string;
  subject_name: string;
  credits?: number;
};

export function listAdminSubjects() {
  return httpRequest<SubjectRow[]>('/admin/subjects');
}
