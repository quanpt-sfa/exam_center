import { httpRequest } from '../../shared/api/httpClient';

export type CurrentUser = {
  user_id: number;
  username?: string | null;
  email?: string | null;
  display_name?: string | null;
  roles: string[];
  permissions?: string[];
  active?: boolean;
};

export const MASTER_DATA_ACCESS_PERMISSIONS = [
  'master_data:read',
  'master_data:write',
  'master_data:import',
  'master_data:publish',
  'facility:read',
  'facility:write',
] as const;

function normalizeValue(value: string): string {
  return value.trim().toUpperCase();
}

function normalizePermission(value: string): string {
  return value.trim().toLowerCase();
}

export function hasRole(user: CurrentUser, roles: readonly string[]): boolean {
  const allowedRoles = new Set(roles.map(normalizeValue));
  return user.roles.some((role) => allowedRoles.has(normalizeValue(role)));
}

export function hasAnyPermission(user: CurrentUser, permissions: readonly string[]): boolean {
  if (hasRole(user, ['ADMIN'])) {
    return true;
  }

  const allowedPermissions = new Set(permissions.map(normalizePermission));
  return (user.permissions || []).some((permission) => allowedPermissions.has(normalizePermission(permission)));
}

export function canAccessMasterData(user: CurrentUser): boolean {
  return hasAnyPermission(user, MASTER_DATA_ACCESS_PERMISSIONS);
}

export type LoginResult = {
  access_token: string;
  refresh_token: string;
  user: CurrentUser;
};

export function login(identifier: string, password: string) {
  return httpRequest<LoginResult>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ identifier: identifier.trim(), password }),
  });
}

export function getCurrentUser() {
  return httpRequest<CurrentUser>('/auth/me');
}

export function restoreSession() {
  return getCurrentUser();
}

export function logout(refreshToken: string | null) {
  return httpRequest('/auth/logout', {
    method: 'POST',
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export type ChangePasswordResult = {
  status: string;
};

export function changePassword(currentPassword: string, newPassword: string) {
  return httpRequest<ChangePasswordResult>('/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
}
