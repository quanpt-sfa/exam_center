import { beforeEach, describe, expect, test, vi } from 'vitest';
import { httpRequest } from '../../../shared/api/httpClient';
import {
  buildClassSectionCreatePayload,
  buildCourseCreatePayload,
  buildDepartmentCreatePayload,
  createClassSectionFromForm,
  createCourseFromForm,
  createDepartment,
  deactivateDepartment,
  listDepartments,
  updateCourseFromForm,
} from './academicApi';

vi.mock('../../../shared/api/httpClient', () => ({
  httpRequest: vi.fn(),
}));

const mockedHttpRequest = vi.mocked(httpRequest);

describe('academicApi', () => {
  beforeEach(() => {
    mockedHttpRequest.mockReset();
    mockedHttpRequest.mockResolvedValue({ ok: true, success: true, data: { items: [] }, error: null, message: null });
  });

  test('listDepartments uses the canonical list endpoint with default pagination', async () => {
    await listDepartments();
    expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/departments?page=1&page_size=20');
  });

  test('listDepartments forwards query params when provided', async () => {
    await listDepartments({ query: 'tai chinh', status: 'ACTIVE', page: 2, page_size: 50 });
    expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/departments?page=2&page_size=50&query=tai+chinh&status=ACTIVE');
  });

  test('createDepartment uses the canonical create endpoint', async () => {
    await createDepartment({ department_code: 'SFA', department_name: 'Khoa Tài chính', status: 'ACTIVE' });
    expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/departments', {
      method: 'POST',
      body: JSON.stringify({ department_code: 'SFA', department_name: 'Khoa Tài chính', status: 'ACTIVE' }),
    });
  });

  test('course payload trims strings and omits invalid optional numbers', () => {
    expect(
      buildCourseCreatePayload({
        department_id: ' 3 ',
        course_code: ' ACC102 ',
        course_name: ' Kế toán quản trị ',
        course_type: ' Core ',
        credit: 'abc',
        status: '',
      })
    ).toEqual({
      department_id: 3,
      course_code: 'ACC102',
      course_name: 'Kế toán quản trị',
      course_type: 'Core',
      credit: undefined,
      status: 'ACTIVE',
    });
  });

  test('required academic fields stay required instead of becoming empty strings', () => {
    expect(
      buildDepartmentCreatePayload({
        department_code: '   ',
        department_name: ' Khoa CNTT ',
        parent_department_id: '',
        status: '',
      })
    ).toEqual({
      department_code: undefined,
      department_name: 'Khoa CNTT',
      parent_department_id: undefined,
      status: 'ACTIVE',
    });
  });

  test('createCourseFromForm posts the normalized payload to the current endpoint', async () => {
    await createCourseFromForm({
      department_id: '3',
      course_code: ' ACC102 ',
      course_name: ' Kế toán quản trị ',
      course_type: '',
      credit: '4',
      status: '',
    });

    expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/courses', {
      method: 'POST',
      body: JSON.stringify({
        department_id: 3,
        course_code: 'ACC102',
        course_name: 'Kế toán quản trị',
        course_type: undefined,
        credit: 4,
        status: 'ACTIVE',
      }),
    });
  });

  test('class section payload omits invalid optional numeric fields instead of submitting NaN', () => {
    expect(
      buildClassSectionCreatePayload({
        course_id: '5',
        term_id: '7',
        class_code: ' ACC101-01 ',
        class_name: ' Lớp 1 ',
        capacity: 'abc',
        delivery_mode: ' OFFLINE ',
        status: '',
        offering_code: ' ACC101-2026A ',
      })
    ).toEqual({
      course_id: 5,
      term_id: 7,
      class_code: 'ACC101-01',
      class_name: 'Lớp 1',
      capacity: undefined,
      delivery_mode: 'OFFLINE',
      status: 'PLANNED',
      offering_code: 'ACC101-2026A',
    });
  });

  test('createClassSectionFromForm posts the normalized payload to the current endpoint', async () => {
    await createClassSectionFromForm({
      course_id: '5',
      term_id: '7',
      class_code: ' ACC101-01 ',
      class_name: ' Lớp 1 ',
      capacity: '',
      delivery_mode: '',
      status: '',
      offering_code: '',
    });

    expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/class-sections', {
      method: 'POST',
      body: JSON.stringify({
        course_id: 5,
        term_id: 7,
        class_code: 'ACC101-01',
        class_name: 'Lớp 1',
        capacity: undefined,
        delivery_mode: undefined,
        status: 'PLANNED',
        offering_code: undefined,
      }),
    });
  });

  test('updateCourseFromForm uses PATCH on the canonical update endpoint', async () => {
    await updateCourseFromForm(5, {
      department_id: '3',
      course_code: ' ACC102 ',
      course_name: ' Kế toán quản trị ',
      course_type: '',
      credit: '4',
      status: 'INACTIVE',
    });

    expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/courses/5', {
      method: 'PATCH',
      body: JSON.stringify({
        department_id: 3,
        course_code: 'ACC102',
        course_name: 'Kế toán quản trị',
        course_type: undefined,
        credit: 4,
        status: 'INACTIVE',
      }),
    });
  });

  test('deactivateDepartment uses the canonical deactivate endpoint', async () => {
    await deactivateDepartment(3, { reason: 'Ngưng sử dụng' });
    expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/departments/3/deactivate', {
      method: 'POST',
      body: JSON.stringify({ reason: 'Ngưng sử dụng' }),
    });
  });
});