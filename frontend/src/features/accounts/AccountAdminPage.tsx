import { FormEvent, useEffect, useState } from 'react';
import { listUserAccounts, resetPasswordToUsername, type UserAccount } from './accountsApi';

function formatRoles(roles: string[]): string {
  return roles.length > 0 ? roles.join(', ') : '-';
}

function formatDate(value?: string | null): string {
  if (!value) {
    return '-';
  }
  return new Date(value).toLocaleString();
}

export function AccountAdminPage() {
  const [accounts, setAccounts] = useState<UserAccount[]>([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [resettingUserId, setResettingUserId] = useState<number | null>(null);

  async function loadAccounts(searchText = query) {
    setLoading(true);
    setError(null);
    const response = await listUserAccounts(searchText);
    setLoading(false);

    if (!response.ok) {
      setAccounts([]);
      setError(response.error.message);
      return;
    }

    setAccounts(response.data.items);
  }

  useEffect(() => {
    void loadAccounts('');
  }, []);

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    await loadAccounts(query);
  }

  async function handleReset(account: UserAccount) {
    const confirmed = window.confirm(
      `Reset password cho ${account.username}? Mat khau moi se bang ten tai khoan.`
    );
    if (!confirmed) {
      return;
    }

    setResettingUserId(account.user_id);
    setError(null);
    setMessage(null);
    const response = await resetPasswordToUsername(account.user_id);
    setResettingUserId(null);

    if (!response.ok) {
      setError(response.error.message);
      return;
    }

    setMessage(`Da reset password cho ${response.data.username}. Mat khau moi bang ten tai khoan.`);
    await loadAccounts(query);
  }

  return (
    <div className="account-admin-page">
      <section className="dashboard-hero">
        <div>
          <p className="eyebrow">Identity</p>
          <h2>Quan ly tai khoan</h2>
          <p>Admin reset mat khau ve dung ten tai khoan khi nguoi dung quen mat khau.</p>
        </div>
      </section>

      <section className="card">
        <form className="toolbar-form" onSubmit={handleSearch}>
          <label htmlFor="account-search">
            Tim tai khoan
            <input
              id="account-search"
              value={query}
              placeholder="username, email, ho ten"
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <button type="submit" disabled={loading}>
            Tim
          </button>
          <button type="button" disabled={loading} onClick={() => void loadAccounts(query)}>
            Tai lai
          </button>
        </form>

        {error ? <p className="form-error">{error}</p> : null}
        {message ? <p className="success-message">{message}</p> : null}

        <div className="master-data-table-wrap">
          {loading ? (
            <p className="muted">Dang tai tai khoan...</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Username</th>
                  <th>Email</th>
                  <th>Ho ten</th>
                  <th>Role</th>
                  <th>Trang thai</th>
                  <th>Lan dang nhap cuoi</th>
                  <th>Thao tac</th>
                </tr>
              </thead>
              <tbody>
                {accounts.length === 0 ? (
                  <tr>
                    <td colSpan={8}>Chua co tai khoan.</td>
                  </tr>
                ) : (
                  accounts.map((account) => (
                    <tr key={account.user_id}>
                      <td>{account.user_id}</td>
                      <td>{account.username}</td>
                      <td>{account.email_login || '-'}</td>
                      <td>{account.display_name || '-'}</td>
                      <td>{formatRoles(account.roles)}</td>
                      <td>{account.user_status}</td>
                      <td>{formatDate(account.last_login_at)}</td>
                      <td>
                        <button
                          type="button"
                          disabled={resettingUserId === account.user_id}
                          onClick={() => void handleReset(account)}
                        >
                          {resettingUserId === account.user_id ? 'Dang reset...' : 'Reset password'}
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  );
}
