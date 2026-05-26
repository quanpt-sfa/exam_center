import { httpRequest } from '../../shared/api/httpClient';
import type { DeactivatePayload, PaginatedListResponse, MasterDataListQuery } from '../masterData/api/contracts';
import { buildQueryString, normalizeListQuery, normalizePaginatedListEnvelope } from '../masterData/api/contracts';
import {
  readCsvTokens,
  readOptionalInteger,
  readOptionalTrimmedString,
  readRequiredTrimmedString,
} from '../masterData/api/formCoercion';

type FormValues = Record<string, string>;

export type RoomDto = {
  room_id: number;
  room_code: string;
  room_name: string;
  building?: string | null;
  floor_no?: string | null;
  capacity?: number | null;
  room_type: string;
  status: string;
};

export type StationDto = {
  station_id: number;
  room_id: number;
  room_code?: string | null;
  station_code: string;
  seat_no?: string | null;
  row_no?: string | null;
  column_no?: string | null;
  status: string;
  device_id?: number | null;
  device?: {
    device_id?: number | null;
    device_code?: string | null;
    asset_tag?: string | null;
  } | null;
};

export type DeviceDto = {
  device_id: number;
  device_code?: string | null;
  asset_tag?: string | null;
  device_name?: string | null;
  device_type: string;
  serial_no?: string | null;
  current_station_id?: number | null;
  current_station_code?: string | null;
  room_code?: string | null;
  status: string;
};

export type DeviceReadinessDto = {
  station_id: number;
  room_id: number;
  station_code: string;
  seat_no?: string | null;
  station_status?: string | null;
  device_id?: number | null;
  asset_tag?: string | null;
  device_name?: string | null;
  device_status?: string | null;
  latest_checkin_at?: string | null;
  latest_health_status?: string | null;
};

export type RoomCreatePayload = {
  room_code?: string;
  room_name?: string;
  building?: string;
  floor_no?: string;
  capacity?: number;
  room_type: string;
  status: string;
};

export type StationCreatePayload = {
  station_code?: string;
  seat_no?: string;
  row_no?: string;
  column_no?: string;
  status: string;
};

export type DeviceCreatePayload = {
  asset_tag?: string;
  device_name?: string;
  device_type: string;
  serial_no?: string;
  current_station_id?: number;
  status: string;
};

export type AssignDeviceToStationPayload = {
  station_id: number;
};

export type RetireDevicePayload = {
  reason: string;
};

export type BulkGenerateStationsPayload = {
  row_labels?: string[];
  start_number: number;
  end_number: number;
  zero_pad: number;
  status: string;
};

export type FacilityListQuery = MasterDataListQuery & {
  room_type?: string;
  room_id?: number;
};

function listPath(path: string, query?: FacilityListQuery, defaults?: { page: number; page_size: number }) {
  const pagination = normalizeListQuery(query, defaults);
  return `${path}${buildQueryString({ ...pagination, ...query })}`;
}

export function listRooms(query?: FacilityListQuery) {
  return httpRequest<PaginatedListResponse<RoomDto>>(listPath('/master-data/rooms', query)).then(normalizePaginatedListEnvelope);
}

export function createRoom(payload: RoomCreatePayload) {
  return httpRequest<RoomDto>('/master-data/rooms', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateRoom(roomId: number, payload: RoomCreatePayload) {
  return httpRequest<RoomDto>(`/master-data/rooms/${roomId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function deactivateRoom(roomId: number, payload: DeactivatePayload) {
  return httpRequest<RoomDto>(`/master-data/rooms/${roomId}/deactivate`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listRoomStations(roomId: number, query?: FacilityListQuery) {
  return httpRequest<PaginatedListResponse<StationDto>>(listPath(`/master-data/rooms/${roomId}/stations`, query, { page: 1, page_size: 200 })).then(normalizePaginatedListEnvelope);
}

export function createRoomStation(roomId: number, payload: StationCreatePayload) {
  return httpRequest<StationDto>(`/master-data/rooms/${roomId}/stations`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateStation(stationId: number, payload: StationCreatePayload & { room_id?: number }) {
  return httpRequest<StationDto>(`/master-data/stations/${stationId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function deactivateStation(stationId: number, payload: DeactivatePayload) {
  return httpRequest<StationDto>(`/master-data/stations/${stationId}/deactivate`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function bulkGenerateStations(roomId: number, payload: BulkGenerateStationsPayload) {
  return httpRequest<{ created_count?: number; items?: StationDto[] }>(`/master-data/rooms/${roomId}/stations/bulk-generate`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listDevices(query?: FacilityListQuery) {
  return httpRequest<PaginatedListResponse<DeviceDto>>(listPath('/master-data/devices', query)).then(normalizePaginatedListEnvelope);
}

export function createDevice(payload: DeviceCreatePayload) {
  return httpRequest<DeviceDto>('/master-data/devices', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateDevice(deviceId: number, payload: DeviceCreatePayload) {
  return httpRequest<DeviceDto>(`/master-data/devices/${deviceId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function assignDeviceToStation(deviceId: number, payload: AssignDeviceToStationPayload) {
  return httpRequest<DeviceDto>(`/master-data/devices/${deviceId}/assign-station`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function retireDevice(deviceId: number, payload: RetireDevicePayload) {
  return httpRequest<DeviceDto>(`/master-data/devices/${deviceId}/retire`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function deactivateDevice(deviceId: number, payload: DeactivatePayload) {
  return httpRequest<DeviceDto>(`/master-data/devices/${deviceId}/deactivate`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function loadRoomStationReadiness(roomId: number) {
  return httpRequest<{ items: DeviceReadinessDto[] }>(`/master-data/rooms/${roomId}/station-readiness`);
}

export function buildRoomCreatePayload(form: FormValues): RoomCreatePayload {
  return {
    room_code: readRequiredTrimmedString(form, 'room_code'),
    room_name: readRequiredTrimmedString(form, 'room_name'),
    building: readOptionalTrimmedString(form, 'building'),
    floor_no: readOptionalTrimmedString(form, 'floor_no'),
    capacity: readOptionalInteger(form, 'capacity'),
    room_type: readOptionalTrimmedString(form, 'room_type') ?? 'LAB',
    status: readOptionalTrimmedString(form, 'status') ?? 'ACTIVE',
  };
}

export function buildStationCreatePayload(form: FormValues): StationCreatePayload {
  return {
    station_code: readRequiredTrimmedString(form, 'station_code'),
    seat_no: readOptionalTrimmedString(form, 'seat_no'),
    row_no: readOptionalTrimmedString(form, 'row_no'),
    column_no: readOptionalTrimmedString(form, 'column_no'),
    status: readOptionalTrimmedString(form, 'status') ?? 'ACTIVE',
  };
}

export function buildDeviceCreatePayload(form: FormValues): DeviceCreatePayload {
  return {
    asset_tag: readRequiredTrimmedString(form, 'asset_tag'),
    device_name: readOptionalTrimmedString(form, 'device_name'),
    device_type: readOptionalTrimmedString(form, 'device_type') ?? 'LAB_PC',
    serial_no: readOptionalTrimmedString(form, 'serial_no'),
    current_station_id: readOptionalInteger(form, 'current_station_id'),
    status: readOptionalTrimmedString(form, 'status') ?? 'ACTIVE',
  };
}

export function buildBulkGenerateStationsPayload(input: {
  pattern: 'grid' | 'numeric';
  rows: string;
  start: string;
  end: string;
  zeroPad: string;
}): BulkGenerateStationsPayload | null {
  const startNumber = Number(input.start);
  const endNumber = Number(input.end);
  const zeroPad = Number(input.zeroPad || '0');
  if (!Number.isInteger(startNumber) || !Number.isInteger(endNumber) || !Number.isInteger(zeroPad) || endNumber < startNumber) {
    return null;
  }

  return {
    row_labels: input.pattern === 'grid' ? readCsvTokens(input.rows).map((item) => item.toUpperCase()) : undefined,
    start_number: startNumber,
    end_number: endNumber,
    zero_pad: zeroPad,
    status: 'ACTIVE',
  };
}

export function createRoomFromForm(form: FormValues) {
  return createRoom(buildRoomCreatePayload(form));
}

export function updateRoomFromForm(roomId: number, form: FormValues) {
  return updateRoom(roomId, buildRoomCreatePayload(form));
}

export function createRoomStationFromForm(roomId: number, form: FormValues) {
  return createRoomStation(roomId, buildStationCreatePayload(form));
}

export function updateStationFromForm(stationId: number, form: FormValues) {
  return updateStation(stationId, buildStationCreatePayload(form));
}

export function createDeviceFromForm(form: FormValues) {
  return createDevice(buildDeviceCreatePayload(form));
}

export function updateDeviceFromForm(deviceId: number, form: FormValues) {
  return updateDevice(deviceId, buildDeviceCreatePayload(form));
}