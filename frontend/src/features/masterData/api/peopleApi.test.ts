import { beforeEach, describe, expect, test, vi } from 'vitest';
import { httpRequest } from '../../../shared/api/httpClient';
import {
  buildInstructorCreatePayload,
  buildStudentCreatePayload,
  createInstructorFromForm,
  createStudentFromForm,
  deactivateStudent,
  listInstructors,
  listStudents,
  updateInstructorFromForm,
} from './peopleApi';

vi.mock('../../../shared/api/httpClient', () => ({
  httpRequest: vi.fn(),
}));

const mockedHttpRequest = vi.mocked(httpRequest);

describe('peopleApi', () => {
  beforeEach(() => {
    mockedHttpRequest.mockReset();
    mockedHttpRequest.mockResolvedValue({ ok: true, success: true, data: { items: [] }, error: null, message: null });
  });

  test('listStudents and listInstructors use the canonical endpoints', async () => {
    await listStudents();
    await listInstructors();

    expect(mockedHttpRequest).toHaveBeenNthCalledWith(1, '/master-data/students?page=1&page_size=20');
    expect(mockedHttpRequest).toHaveBeenNthCalledWith(2, '/master-data/instructors?page=1&page_size=20');
  });

  test('listStudents forwards query and status filters', async () => {
    await listStudents({ query: 'sv002', status: 'ACTIVE', page: 3, page_size: 10 });
    expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/students?page=3&page_size=10&query=sv002&status=ACTIVE');
  });

  test('student payload trims strings and omits empty optional numbers', () => {
    expect(
      buildStudentCreatePayload({
        full_name: ' Nguyễn Văn B ',
        student_code: ' SV002 ',
        date_of_birth: ' 2004-03-01 ',
        gender_code: ' MALE ',
        program_id: '',
        cohort: ' K18 ',
        entry_year: 'abc',
        student_status: '',
      })
    ).toEqual({
      full_name: 'Nguyễn Văn B',
      student_code: 'SV002',
      date_of_birth: '2004-03-01',
      gender_code: 'MALE',
      program_id: undefined,
      cohort: 'K18',
      entry_year: undefined,
      student_status: 'ACTIVE',
    });
  });

  test('required people fields stay required instead of becoming empty strings', () => {
    expect(
      buildInstructorCreatePayload({
        full_name: ' ',
        instructor_code: ' GV001 ',
        date_of_birth: '',
        gender_code: '',
        department_id: '',
        instructor_status: '',
      })
    ).toEqual({
      full_name: undefined,
      instructor_code: 'GV001',
      date_of_birth: undefined,
      gender_code: undefined,
      department_id: undefined,
      instructor_status: 'ACTIVE',
    });
  });

  test('createStudentFromForm posts normalized payload to the current endpoint', async () => {
    await createStudentFromForm({
      full_name: ' Nguyễn Văn B ',
      student_code: ' SV002 ',
      date_of_birth: '',
      gender_code: '',
      program_id: '',
      cohort: '',
      entry_year: '',
      student_status: '',
    });

    expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/students', {
      method: 'POST',
      body: JSON.stringify({
        full_name: 'Nguyễn Văn B',
        student_code: 'SV002',
        date_of_birth: undefined,
        gender_code: undefined,
        program_id: undefined,
        cohort: undefined,
        entry_year: undefined,
        student_status: 'ACTIVE',
      }),
    });
  });

  test('createInstructorFromForm posts normalized payload to the current endpoint', async () => {
    await createInstructorFromForm({
      full_name: ' Phạm Quang Huy ',
      instructor_code: ' GV001 ',
      date_of_birth: '',
      gender_code: '',
      department_id: '3',
      instructor_status: '',
    });

    expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/instructors', {
      method: 'POST',
      body: JSON.stringify({
        full_name: 'Phạm Quang Huy',
        instructor_code: 'GV001',
        date_of_birth: undefined,
        gender_code: undefined,
        department_id: 3,
        instructor_status: 'ACTIVE',
      }),
    });
  });

  test('updateInstructorFromForm uses PATCH on the canonical update endpoint', async () => {
    await updateInstructorFromForm(8, {
      full_name: ' Phạm Quang Huy ',
      instructor_code: ' GV001 ',
      date_of_birth: '',
      gender_code: '',
      department_id: '3',
      instructor_status: 'INACTIVE',
    });

    expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/instructors/8', {
      method: 'PATCH',
      body: JSON.stringify({
        full_name: 'Phạm Quang Huy',
        instructor_code: 'GV001',
        date_of_birth: undefined,
        gender_code: undefined,
        department_id: 3,
        instructor_status: 'INACTIVE',
      }),
    });
  });

  test('deactivateStudent uses the canonical deactivate endpoint', async () => {
    await deactivateStudent(4, { reason: 'Ngưng sử dụng' });
    expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/students/4/deactivate', {
      method: 'POST',
      body: JSON.stringify({ reason: 'Ngưng sử dụng' }),
    });
  });
});