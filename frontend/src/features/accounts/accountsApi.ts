import { httpRequest } from '../../shared/api/httpClient';

export type UserAccount = {
  user_id: number;
  person_id?: number | null;
  username: string;
  email_login?: string | null;
  display_name?: string | null;
  user_status: string;
  roles: string[];
  last_login_at?: string | null;
};

export type UserAccountListResponse = {
  items: UserAccount[];
  pagination?: {
    page: number;
    page_size: number;
    total_items?: number;
  };
};

export type ResetPasswordResponse = {
  user_id: number;
  username: string;
  password_reset: boolean;
  reset_policy: 'USERNAME';
};

export function listUserAccounts(query = '') {
  const params = new URLSearchParams({ page: '1', page_size: '50' });
  if (query.trim()) {
    params.set('query', query.trim());
  }
  return httpRequest<UserAccountListResponse>(`/identity/users?${params.toString()}`);
}

export function resetPasswordToUsername(userId: number) {
  return httpRequest<ResetPasswordResponse>(`/identity/users/${userId}/reset-password-to-username`, {
    method: 'POST',
  });
}
