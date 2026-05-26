import { httpRequest } from '../../../shared/api/httpClient';
import type { DeactivatePayload, PaginatedListResponse, MasterDataListQuery, MasterDataRow } from './contracts';
import { buildQueryString, normalizeListQuery, normalizePaginatedListEnvelope } from './contracts';
import {
  readOptionalInteger,
  readOptionalNumber,
  readOptionalTrimmedString,
  readRequiredTrimmedString,
} from './formCoercion';

type FormValues = Record<string, string>;

export type DepartmentDto = {
  department_id: number;
  department_code: string;
  department_name: string;
  parent_department_id?: number | null;
  status: string;
};

export type ProgramDto = {
  program_id: number;
  program_code: string;
  program_name: string;
  program_level?: string | null;
  department_id?: number | null;
  department_code?: string | null;
  status?: string | null;
};

export type CourseDto = {
  course_id: number;
  department_id: number;
  department_code?: string | null;
  course_code: string;
  course_name: string;
  course_type?: string | null;
  credit?: number | null;
  status: string;
};

export type AcademicTermSummaryDto = {
  term_id: number;
  term_code?: string | null;
  term_name?: string | null;
};

export type ClassSectionDto = {
  class_section_id: number;
  course_id: number;
  term_id: number;
  class_code: string;
  class_name: string;
  capacity?: number | null;
  delivery_mode?: string | null;
  status: string;
  offering_code?: string | null;
  course?: Pick<CourseDto, 'course_id' | 'course_code' | 'course_name'> | null;
  term?: AcademicTermSummaryDto | null;
};

export type EnrollmentDto = {
  enrollment_id: number;
  class_section_id?: number | null;
  student_id?: number | null;
  class_code?: string | null;
  student_code?: string | null;
  full_name?: string | null;
  enrollment_status?: string | null;
};

export type AssessmentTypeDto = {
  assessment_type_id: number;
  type_code: string;
  type_name: string;
  description?: string | null;
  is_active: boolean;
};

export type DepartmentCreatePayload = {
  department_code?: string;
  department_name?: string;
  parent_department_id?: number;
  status: string;
};

export type CourseCreatePayload = {
  department_id?: number;
  course_code?: string;
  course_name?: string;
  course_type?: string;
  credit?: number;
  status: string;
};

export type ClassSectionCreatePayload = {
  course_id?: number;
  term_id?: number;
  class_code?: string;
  class_name?: string;
  capacity?: number;
  delivery_mode?: string;
  status: string;
  offering_code?: string;
};

export type AcademicListQuery = MasterDataListQuery & {
  department_id?: number;
  course_id?: number;
  term_id?: number;
  is_active?: boolean;
};

function listPath(path: string, query?: AcademicListQuery, defaults?: { page: number; page_size: number }) {
  const pagination = normalizeListQuery(query, defaults);
  return `${path}${buildQueryString({ ...pagination, ...query })}`;
}

export function listDepartments(query?: AcademicListQuery) {
  return httpRequest<PaginatedListResponse<DepartmentDto>>(listPath('/master-data/departments', query)).then(normalizePaginatedListEnvelope);
}

export function createDepartment(payload: DepartmentCreatePayload) {
  return httpRequest<DepartmentDto>('/master-data/departments', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateDepartment(departmentId: number, payload: DepartmentCreatePayload) {
  return httpRequest<DepartmentDto>(`/master-data/departments/${departmentId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function deactivateDepartment(departmentId: number, payload: DeactivatePayload) {
  return httpRequest<DepartmentDto>(`/master-data/departments/${departmentId}/deactivate`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listPrograms(query?: AcademicListQuery) {
  return httpRequest<PaginatedListResponse<ProgramDto>>(listPath('/master-data/programs', query)).then(normalizePaginatedListEnvelope);
}

export function listCourses(query?: AcademicListQuery) {
  return httpRequest<PaginatedListResponse<CourseDto>>(listPath('/master-data/courses', query)).then(normalizePaginatedListEnvelope);
}

export function createCourse(payload: CourseCreatePayload) {
  return httpRequest<CourseDto>('/master-data/courses', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateCourse(courseId: number, payload: CourseCreatePayload) {
  return httpRequest<CourseDto>(`/master-data/courses/${courseId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function deactivateCourse(courseId: number, payload: DeactivatePayload) {
  return httpRequest<CourseDto>(`/master-data/courses/${courseId}/deactivate`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listClassSections(query?: AcademicListQuery) {
  return httpRequest<PaginatedListResponse<ClassSectionDto>>(listPath('/master-data/class-sections', query)).then(normalizePaginatedListEnvelope);
}

export function createClassSection(payload: ClassSectionCreatePayload) {
  return httpRequest<ClassSectionDto>('/master-data/class-sections', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateClassSection(classSectionId: number, payload: ClassSectionCreatePayload) {
  return httpRequest<ClassSectionDto>(`/master-data/class-sections/${classSectionId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function deactivateClassSection(classSectionId: number, payload: DeactivatePayload) {
  return httpRequest<ClassSectionDto>(`/master-data/class-sections/${classSectionId}/deactivate`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listEnrollments(query?: AcademicListQuery) {
  return httpRequest<PaginatedListResponse<EnrollmentDto>>(listPath('/master-data/enrollments', query)).then(normalizePaginatedListEnvelope);
}

export function listAssessmentTypes(query?: AcademicListQuery) {
  return httpRequest<PaginatedListResponse<AssessmentTypeDto>>(listPath('/master-data/assessment-types', query)).then(normalizePaginatedListEnvelope);
}

export function buildDepartmentCreatePayload(form: FormValues): DepartmentCreatePayload {
  return {
    department_code: readRequiredTrimmedString(form, 'department_code'),
    department_name: readRequiredTrimmedString(form, 'department_name'),
    parent_department_id: readOptionalInteger(form, 'parent_department_id'),
    status: readOptionalTrimmedString(form, 'status') ?? 'ACTIVE',
  };
}

export function buildCourseCreatePayload(form: FormValues): CourseCreatePayload {
  return {
    department_id: readOptionalInteger(form, 'department_id'),
    course_code: readRequiredTrimmedString(form, 'course_code'),
    course_name: readRequiredTrimmedString(form, 'course_name'),
    course_type: readOptionalTrimmedString(form, 'course_type'),
    credit: readOptionalNumber(form, 'credit'),
    status: readOptionalTrimmedString(form, 'status') ?? 'ACTIVE',
  };
}

export function buildClassSectionCreatePayload(form: FormValues): ClassSectionCreatePayload {
  return {
    course_id: readOptionalInteger(form, 'course_id'),
    term_id: readOptionalInteger(form, 'term_id'),
    class_code: readRequiredTrimmedString(form, 'class_code'),
    class_name: readRequiredTrimmedString(form, 'class_name'),
    capacity: readOptionalInteger(form, 'capacity'),
    delivery_mode: readOptionalTrimmedString(form, 'delivery_mode'),
    status: readOptionalTrimmedString(form, 'status') ?? 'PLANNED',
    offering_code: readOptionalTrimmedString(form, 'offering_code'),
  };
}

export function createDepartmentFromForm(form: FormValues) {
  return createDepartment(buildDepartmentCreatePayload(form));
}

export function updateDepartmentFromForm(departmentId: number, form: FormValues) {
  return updateDepartment(departmentId, buildDepartmentCreatePayload(form));
}

export function createCourseFromForm(form: FormValues) {
  return createCourse(buildCourseCreatePayload(form));
}

export function updateCourseFromForm(courseId: number, form: FormValues) {
  return updateCourse(courseId, buildCourseCreatePayload(form));
}

export function createClassSectionFromForm(form: FormValues) {
  return createClassSection(buildClassSectionCreatePayload(form));
}

export function updateClassSectionFromForm(classSectionId: number, form: FormValues) {
  return updateClassSection(classSectionId, buildClassSectionCreatePayload(form));
}

export function asAcademicRows<T extends MasterDataRow>(items: T[]): MasterDataRow[] {
  return items;
}