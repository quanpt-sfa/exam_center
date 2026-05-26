import { getProctorRoomReadiness, getProctorRoomRoster } from './api/proctorApi';

export type {
  ProctorAssignedRoom as ProctorRoom,
  ProctorIncident,
  ProctorIncidentCreatePayload,
  ProctorIncidentUpdatePayload,
  ProctorRoomReadinessCheck as ProctorReadinessItem,
  ProctorRoomRosterItem,
  StaleSessionRevokeResult as RevokeStaleSessionResult,
} from './api/contracts';

export {
  createProctorIncident,
  revokeStudentStaleSession as revokeProctorStudentStaleSession,
  listMySittingRooms as loadMySittingRooms,
} from './api/proctorApi';

export async function loadProctorRoster(examSittingRoomId: number) {
  const response = await getProctorRoomRoster(examSittingRoomId);
  return response.items;
}

export async function loadProctorReadiness(examSittingRoomId: number) {
  const response = await getProctorRoomReadiness(examSittingRoomId);
  return response.items;
}

