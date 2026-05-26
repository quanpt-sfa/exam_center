import { beforeEach, describe, expect, test, vi } from 'vitest';

vi.mock('../../../shared/api/httpClient', () => ({
  httpRequest: vi.fn(),
}));

import { httpRequest } from '../../../shared/api/httpClient';
import {
  createProctorIncident,
  getProctorRoomReadiness,
  getProctorRoomRoster,
  listProctorRoomIncidents,
  listMySittingRooms,
  revokeStudentStaleSession,
  updateProctorIncident,
} from './proctorApi';

const ok = <T,>(data: T) => ({ ok: true as const, success: true as const, data, error: null, message: null });
const err = (code: string, message: string) => ({ ok: false as const, success: false as const, data: null, error: { code, message, details: {} }, message: null });

describe('proctorApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('listMySittingRooms uses the real backend path and returns normalized items', async () => {
    vi.mocked(httpRequest).mockResolvedValue(
      ok({
        items: [
          {
            exam_sitting_id: 10,
            exam_sitting_room_id: 100,
            room_id: 1,
            room_code: 'D13',
            room_name: 'Phòng D13',
            sitting_code: 'S1',
            sitting_name: 'Ca sáng',
            sitting_status: 'OPEN',
            scheduled_start_at: '2026-05-21T08:00:00+07:00',
            scheduled_end_at: '2026-05-21T10:00:00+07:00',
            room_status: 'READY',
            capacity_allocated: 25,
            assigned_student_count: 20,
            assigned_station_count: 20,
          },
        ],
      })
    );

    await expect(listMySittingRooms()).resolves.toEqual([
      expect.objectContaining({ exam_sitting_room_id: 100, room_code: 'D13', room_status: 'READY' }),
    ]);
    expect(httpRequest).toHaveBeenCalledWith('/proctor/my-sitting-rooms');
  });

  test('getProctorRoomRoster uses the real backend path and preserves room-level context', async () => {
    vi.mocked(httpRequest).mockResolvedValue(
      ok({
        exam_sitting_id: 10,
        exam_sitting_room_id: 100,
        room_code: 'D13',
        items: [
          {
            exam_sitting_id: 10,
            exam_sitting_room_id: 100,
            room_code: 'D13',
            exam_assignment_id: 555,
            station_id: 11,
            station_code: 'A1',
            student_id: 1001,
            student_code: 'SV001',
            full_name: 'Nguyen A',
            photo_ref: null,
            assignment_status: 'ASSIGNED',
            station_assignment_status: 'ASSIGNED',
            planned_device_id: 5,
            planned_device_asset_tag: 'PC-01',
            last_checkin_at: null,
            latest_health_status: 'READY',
            exam_session_id: 777,
            session_code: 'SESS-1',
            session_status: 'IN_PROGRESS',
            started_at: null,
            ended_at: null,
            last_seen_at: null,
            exam_submission_id: null,
            submission_status: null,
            submitted_at: null,
            sealed_at: null,
          },
        ],
      })
    );

    await expect(getProctorRoomRoster(100)).resolves.toEqual(
      expect.objectContaining({ exam_sitting_room_id: 100, room_code: 'D13', items: [expect.objectContaining({ student_code: 'SV001' })] })
    );
    expect(httpRequest).toHaveBeenCalledWith('/proctor/sitting-rooms/100/roster');
  });

  test('getProctorRoomReadiness uses the real backend path and normalizes readiness rows', async () => {
    vi.mocked(httpRequest).mockResolvedValue(
      ok({ exam_sitting_id: 10, exam_sitting_room_id: 100, room_code: 'D13', items: [{ station_code: 'A1', asset_tag: 'PC-01', health_status: 'READY', mismatch: false, last_checkin_at: null }] })
    );

    await expect(getProctorRoomReadiness(100)).resolves.toEqual(
      expect.objectContaining({ items: [expect.objectContaining({ station_code: 'A1', mismatch: false })] })
    );
    expect(httpRequest).toHaveBeenCalledWith('/proctor/sitting-rooms/100/readiness');
  });

  test('listProctorRoomIncidents uses the room-level backend path and normalizes items', async () => {
    vi.mocked(httpRequest).mockResolvedValue(
      ok({
        items: [
          {
            incident_id: 1,
            exam_sitting_id: 10,
            exam_sitting_room_id: 100,
            exam_assignment_id: 555,
            exam_session_id: null,
            station_id: 11,
            device_id: 5,
            incident_type: 'DEVICE_FAILURE',
            incident_status: 'OPEN',
            reported_by: 2,
            reported_at: '2026-05-21T10:00:00Z',
            resolved_by: null,
            resolved_at: null,
            updated_by: 7,
            updated_at: '2026-05-21T10:01:00Z',
            resolution_note: null,
            description: 'Mất mạng',
            metadata_json: { source: 'api' },
          },
        ],
      })
    );

    await expect(listProctorRoomIncidents(100)).resolves.toEqual([
      expect.objectContaining({
        incident_id: 1,
        exam_sitting_room_id: 100,
        metadata_json: { source: 'api' },
        updated_by: 7,
        updated_at: '2026-05-21T10:01:00Z',
        resolution_note: null,
      }),
    ]);
    expect(httpRequest).toHaveBeenCalledWith('/proctor/sitting-rooms/100/incidents');
  });

  test('listProctorRoomIncidents includes limit and offset query params when supplied', async () => {
    vi.mocked(httpRequest).mockResolvedValue(ok({ items: [] }));

    await expect(listProctorRoomIncidents(100, { limit: 25, offset: 50 })).resolves.toEqual([]);
    expect(httpRequest).toHaveBeenCalledWith('/proctor/sitting-rooms/100/incidents?limit=25&offset=50');
  });

  test('createProctorIncident uses the real backend path and body', async () => {
    vi.mocked(httpRequest).mockResolvedValue(
      ok({
        incident_id: 1,
        exam_sitting_id: 10,
        exam_sitting_room_id: 100,
        exam_assignment_id: null,
        exam_session_id: null,
        station_id: null,
        device_id: null,
        incident_type: 'DEVICE_FAILURE',
        incident_status: 'OPEN',
        reported_by: 2,
        reported_at: '2026-05-21T10:00:00Z',
        resolved_by: null,
        resolved_at: null,
        updated_by: null,
        updated_at: null,
        resolution_note: null,
        description: 'Mất mạng',
        metadata_json: {},
      })
    );

    await createProctorIncident(100, { incident_type: 'DEVICE_FAILURE', description: 'Mất mạng' });
    expect(httpRequest).toHaveBeenCalledWith(
      '/proctor/sitting-rooms/100/incidents',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ incident_type: 'DEVICE_FAILURE', description: 'Mất mạng' }) })
    );
  });

  test('updateProctorIncident sends resolution_note when provided and normalizes audit fields', async () => {
    vi.mocked(httpRequest).mockResolvedValue(
      ok({
        incident_id: 1,
        exam_sitting_id: 10,
        exam_sitting_room_id: 100,
        exam_assignment_id: null,
        exam_session_id: null,
        station_id: null,
        device_id: null,
        incident_type: 'DEVICE_FAILURE',
        incident_status: 'RESOLVED',
        reported_by: 2,
        reported_at: '2026-05-21T10:00:00Z',
        resolved_by: 2,
        resolved_at: '2026-05-21T10:05:00Z',
        updated_by: 2,
        updated_at: '2026-05-21T10:05:00Z',
        resolution_note: 'Đã thay nguồn điện',
        description: 'Đã xử lý',
        metadata_json: {},
      })
    );

    await expect(
      updateProctorIncident(1, { incident_status: 'RESOLVED', description: 'Đã xử lý', resolution_note: 'Đã thay nguồn điện' })
    ).resolves.toEqual(
      expect.objectContaining({
        incident_status: 'RESOLVED',
        updated_by: 2,
        updated_at: '2026-05-21T10:05:00Z',
        resolution_note: 'Đã thay nguồn điện',
      })
    );
    expect(httpRequest).toHaveBeenCalledWith(
      '/proctor/incidents/1',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ incident_status: 'RESOLVED', description: 'Đã xử lý', resolution_note: 'Đã thay nguồn điện' }),
      })
    );
  });

  test('updateProctorIncident does not send metadata_json for proctor payloads', async () => {
    vi.mocked(httpRequest).mockResolvedValue(
      ok({
        incident_id: 1,
        exam_sitting_id: 10,
        exam_sitting_room_id: 100,
        exam_assignment_id: null,
        exam_session_id: null,
        station_id: null,
        device_id: null,
        incident_type: 'DEVICE_FAILURE',
        incident_status: 'IN_PROGRESS',
        reported_by: 2,
        reported_at: '2026-05-21T10:00:00Z',
        resolved_by: null,
        resolved_at: null,
        updated_by: 2,
        updated_at: '2026-05-21T10:02:00Z',
        resolution_note: null,
        description: 'Đang xử lý',
        metadata_json: { preserved: true },
      })
    );

    await updateProctorIncident(
      1,
      {
        incident_status: 'IN_PROGRESS',
        description: 'Đang xử lý',
        metadata_json: { should_not_send: true },
      } as unknown as Parameters<typeof updateProctorIncident>[1]
    );

    expect(httpRequest).toHaveBeenCalledWith(
      '/proctor/incidents/1',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ incident_status: 'IN_PROGRESS', description: 'Đang xử lý' }),
      })
    );
  });

  test('revokeStudentStaleSession uses the real backend path and no fake fallback', async () => {
    vi.mocked(httpRequest).mockResolvedValue(ok({ status: 'revoked' }));

    await expect(revokeStudentStaleSession(100, 10)).resolves.toEqual({ status: 'revoked' });
    expect(httpRequest).toHaveBeenCalledWith(
      '/delivery/exam-sitting-rooms/100/students/10/revoke-stale-session',
      expect.objectContaining({ method: 'POST' })
    );
  });

  test('backend errors propagate and are not converted into fake success', async () => {
    vi.mocked(httpRequest).mockResolvedValue(err('permission_denied', 'Insufficient permissions'));

    await expect(listMySittingRooms()).rejects.toThrow('Insufficient permissions');
  });

  test('updateProctorIncident propagates backend validation errors', async () => {
    vi.mocked(httpRequest).mockResolvedValue(err('validation_error', 'Resolved incidents require non-empty resolution_note'));

    await expect(updateProctorIncident(1, { incident_status: 'RESOLVED' })).rejects.toThrow(
      'Resolved incidents require non-empty resolution_note'
    );
  });

  test('listProctorRoomIncidents propagates backend errors without fake fallback list', async () => {
    vi.mocked(httpRequest).mockResolvedValue(err('permission_denied', 'Không có quyền xem sự cố'));

    await expect(listProctorRoomIncidents(100)).rejects.toThrow('Không có quyền xem sự cố');
  });
});
