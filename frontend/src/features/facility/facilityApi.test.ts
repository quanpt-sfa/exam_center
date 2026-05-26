import { beforeEach, describe, expect, test, vi } from 'vitest';
import { httpRequest } from '../../shared/api/httpClient';
import {
  assignDeviceToStation,
  buildBulkGenerateStationsPayload,
  buildDeviceCreatePayload,
  buildRoomCreatePayload,
  buildStationCreatePayload,
  bulkGenerateStations,
  deactivateDevice,
  listDevices,
  listRoomStations,
  listRooms,
  loadRoomStationReadiness,
  retireDevice,
  updateRoomFromForm,
} from './facilityApi';

vi.mock('../../shared/api/httpClient', () => ({
  httpRequest: vi.fn(),
}));

const mockedHttpRequest = vi.mocked(httpRequest);

describe('facilityApi', () => {
  beforeEach(() => {
    mockedHttpRequest.mockReset();
    mockedHttpRequest.mockResolvedValue({ ok: true, success: true, data: { items: [] }, error: null, message: null });
  });

  test('list endpoints use the canonical facility URLs', async () => {
    await listRooms();
    await listRoomStations(31);
    await listDevices();
    await loadRoomStationReadiness(31);

    expect(mockedHttpRequest).toHaveBeenNthCalledWith(1, '/master-data/rooms?page=1&page_size=20');
    expect(mockedHttpRequest).toHaveBeenNthCalledWith(2, '/master-data/rooms/31/stations?page=1&page_size=200');
    expect(mockedHttpRequest).toHaveBeenNthCalledWith(3, '/master-data/devices?page=1&page_size=20');
    expect(mockedHttpRequest).toHaveBeenNthCalledWith(4, '/master-data/rooms/31/station-readiness');
  });

  test('listRooms forwards query and status filters', async () => {
    await listRooms({ query: 'D13', status: 'ACTIVE', page: 2, page_size: 50 });
    expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/rooms?page=2&page_size=50&query=D13&status=ACTIVE');
  });

  test('assign, retire, and bulk-generate use the canonical action URLs', async () => {
    await assignDeviceToStation(7, { station_id: 11 });
    await retireDevice(7, { reason: 'Ngưng sử dụng' });
    await bulkGenerateStations(31, {
      row_labels: ['A', 'B'],
      start_number: 1,
      end_number: 6,
      zero_pad: 0,
      status: 'ACTIVE',
    });

    expect(mockedHttpRequest).toHaveBeenNthCalledWith(1, '/master-data/devices/7/assign-station', {
      method: 'POST',
      body: JSON.stringify({ station_id: 11 }),
    });
    expect(mockedHttpRequest).toHaveBeenNthCalledWith(2, '/master-data/devices/7/retire', {
      method: 'POST',
      body: JSON.stringify({ reason: 'Ngưng sử dụng' }),
    });
    expect(mockedHttpRequest).toHaveBeenNthCalledWith(3, '/master-data/rooms/31/stations/bulk-generate', {
      method: 'POST',
      body: JSON.stringify({ row_labels: ['A', 'B'], start_number: 1, end_number: 6, zero_pad: 0, status: 'ACTIVE' }),
    });
  });

  test('room and device payloads trim strings and omit invalid optional numbers', () => {
    expect(
      buildRoomCreatePayload({
        room_code: ' LAB-A101 ',
        room_name: ' Phòng A101 ',
        building: ' A ',
        floor_no: ' 1 ',
        capacity: 'abc',
        room_type: '',
        status: '',
      })
    ).toEqual({
      room_code: 'LAB-A101',
      room_name: 'Phòng A101',
      building: 'A',
      floor_no: '1',
      capacity: undefined,
      room_type: 'LAB',
      status: 'ACTIVE',
    });

    expect(
      buildDeviceCreatePayload({
        asset_tag: ' PC-01 ',
        device_name: ' Máy 01 ',
        device_type: '',
        serial_no: ' SN001 ',
        current_station_id: '',
        status: '',
      })
    ).toEqual({
      asset_tag: 'PC-01',
      device_name: 'Máy 01',
      device_type: 'LAB_PC',
      serial_no: 'SN001',
      current_station_id: undefined,
      status: 'ACTIVE',
    });
  });

  test('station payload keeps required fields required and does not submit empty strings', () => {
    expect(
      buildStationCreatePayload({
        station_code: ' ',
        seat_no: ' A1 ',
        row_no: '',
        column_no: '',
        status: '',
      })
    ).toEqual({
      station_code: undefined,
      seat_no: 'A1',
      row_no: undefined,
      column_no: undefined,
      status: 'ACTIVE',
    });
  });

  test('bulk generator payload trims grid rows and rejects invalid number ranges', () => {
    expect(
      buildBulkGenerateStationsPayload({
        pattern: 'grid',
        rows: ' a, b , ,c ',
        start: '1',
        end: '6',
        zeroPad: '0',
      })
    ).toEqual({
      row_labels: ['A', 'B', 'C'],
      start_number: 1,
      end_number: 6,
      zero_pad: 0,
      status: 'ACTIVE',
    });

    expect(
      buildBulkGenerateStationsPayload({
        pattern: 'numeric',
        rows: '',
        start: '50',
        end: '1',
        zeroPad: '0',
      })
    ).toBeNull();
  });

  test('updateRoomFromForm uses PATCH on the canonical update endpoint', async () => {
    await updateRoomFromForm(31, {
      room_code: ' LAB-A101 ',
      room_name: ' Phòng A101 ',
      building: ' A ',
      floor_no: ' 1 ',
      capacity: '60',
      room_type: '',
      status: 'INACTIVE',
    });

    expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/rooms/31', {
      method: 'PATCH',
      body: JSON.stringify({
        room_code: 'LAB-A101',
        room_name: 'Phòng A101',
        building: 'A',
        floor_no: '1',
        capacity: 60,
        room_type: 'LAB',
        status: 'INACTIVE',
      }),
    });
  });

  test('deactivateDevice uses the canonical deactivate endpoint', async () => {
    await deactivateDevice(7, { reason: 'Ngưng sử dụng' });
    expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/devices/7/deactivate', {
      method: 'POST',
      body: JSON.stringify({ reason: 'Ngưng sử dụng' }),
    });
  });
});