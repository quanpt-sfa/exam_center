import { httpRequest } from '../../../shared/api/httpClient';
import type { DeactivatePayload, PaginatedListResponse, MasterDataListQuery } from './contracts';
import { buildQueryString, normalizeListQuery, normalizePaginatedListEnvelope } from './contracts';
import {
  readOptionalInteger,
  readOptionalTrimmedString,
  readRequiredTrimmedString,
} from './formCoercion';

type FormValues = Record<string, string>;

export type StudentDto = {
  student_id: number;
  person_id?: number | null;
  student_code: string;
  full_name: string;
  date_of_birth?: string | null;
  gender_code?: string | null;
  program_id?: number | null;
  program_code?: string | null;
  cohort?: string | null;
  entry_year?: number | null;
  student_status: string;
};

export type InstructorDto = {
  instructor_id: number;
  person_id?: number | null;
  instructor_code: string;
  full_name: string;
  date_of_birth?: string | null;
  gender_code?: string | null;
  department_id?: number | null;
  department_code?: string | null;
  instructor_status: string;
};

export type PeopleListQuery = MasterDataListQuery & {
  program_id?: number;
  department_id?: number;
};

export type StudentCreatePayload = {
  full_name?: string;
  student_code?: string;
  date_of_birth?: string;
  gender_code?: string;
  program_id?: number;
  cohort?: string;
  entry_year?: number;
  student_status: string;
};

export type InstructorCreatePayload = {
  full_name?: string;
  instructor_code?: string;
  date_of_birth?: string;
  gender_code?: string;
  department_id?: number;
  instructor_status: string;
};

function listPath(path: string, query?: PeopleListQuery) {
  const pagination = normalizeListQuery(query);
  return `${path}${buildQueryString({ ...pagination, ...query })}`;
}

export function listStudents(query?: PeopleListQuery) {
  return httpRequest<PaginatedListResponse<StudentDto>>(listPath('/master-data/students', query)).then(normalizePaginatedListEnvelope);
}

export function createStudent(payload: StudentCreatePayload) {
  return httpRequest<StudentDto>('/master-data/students', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateStudent(studentId: number, payload: StudentCreatePayload) {
  return httpRequest<StudentDto>(`/master-data/students/${studentId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function deactivateStudent(studentId: number, payload: DeactivatePayload) {
  return httpRequest<StudentDto>(`/master-data/students/${studentId}/deactivate`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listInstructors(query?: PeopleListQuery) {
  return httpRequest<PaginatedListResponse<InstructorDto>>(listPath('/master-data/instructors', query)).then(normalizePaginatedListEnvelope);
}

export function createInstructor(payload: InstructorCreatePayload) {
  return httpRequest<InstructorDto>('/master-data/instructors', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateInstructor(instructorId: number, payload: InstructorCreatePayload) {
  return httpRequest<InstructorDto>(`/master-data/instructors/${instructorId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function deactivateInstructor(instructorId: number, payload: DeactivatePayload) {
  return httpRequest<InstructorDto>(`/master-data/instructors/${instructorId}/deactivate`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function buildStudentCreatePayload(form: FormValues): StudentCreatePayload {
  return {
    full_name: readRequiredTrimmedString(form, 'full_name'),
    student_code: readRequiredTrimmedString(form, 'student_code'),
    date_of_birth: readOptionalTrimmedString(form, 'date_of_birth'),
    gender_code: readOptionalTrimmedString(form, 'gender_code'),
    program_id: readOptionalInteger(form, 'program_id'),
    cohort: readOptionalTrimmedString(form, 'cohort'),
    entry_year: readOptionalInteger(form, 'entry_year'),
    student_status: readOptionalTrimmedString(form, 'student_status') ?? 'ACTIVE',
  };
}

export function buildInstructorCreatePayload(form: FormValues): InstructorCreatePayload {
  return {
    full_name: readRequiredTrimmedString(form, 'full_name'),
    instructor_code: readRequiredTrimmedString(form, 'instructor_code'),
    date_of_birth: readOptionalTrimmedString(form, 'date_of_birth'),
    gender_code: readOptionalTrimmedString(form, 'gender_code'),
    department_id: readOptionalInteger(form, 'department_id'),
    instructor_status: readOptionalTrimmedString(form, 'instructor_status') ?? 'ACTIVE',
  };
}

export function createStudentFromForm(form: FormValues) {
  return createStudent(buildStudentCreatePayload(form));
}

export function updateStudentFromForm(studentId: number, form: FormValues) {
  return updateStudent(studentId, buildStudentCreatePayload(form));
}

export function createInstructorFromForm(form: FormValues) {
  return createInstructor(buildInstructorCreatePayload(form));
}

export function updateInstructorFromForm(instructorId: number, form: FormValues) {
  return updateInstructor(instructorId, buildInstructorCreatePayload(form));
}