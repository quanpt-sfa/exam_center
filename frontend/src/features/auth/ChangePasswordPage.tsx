import { FormEvent, useState } from 'react';
import { Link } from 'react-router-dom';
import { changePassword } from './authApi';

export function ChangePasswordPage() {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);

    if (newPassword !== confirmPassword) {
      setError('Mật khẩu mới và xác nhận mật khẩu không khớp.');
      return;
    }

    setSubmitting(true);
    const response = await changePassword(currentPassword, newPassword);
    setSubmitting(false);

    if (!response.ok) {
      setError(response.error.message);
      return;
    }

    setCurrentPassword('');
    setNewPassword('');
    setConfirmPassword('');
    setMessage('Đã đổi mật khẩu thành công.');
  }

  return (
    <section className="card change-password-page">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Tài khoản</p>
          <h2>Đổi mật khẩu</h2>
          <p className="muted">Mật khẩu mới phải có ít nhất 8 ký tự.</p>
        </div>
        <Link to="/dashboard">Quay lại dashboard</Link>
      </div>

      <form className="account-form" onSubmit={handleSubmit}>
        <label htmlFor="current-password">
          Mật khẩu hiện tại
          <input
            id="current-password"
            type="password"
            value={currentPassword}
            autoComplete="current-password"
            required
            onChange={(event) => setCurrentPassword(event.target.value)}
          />
        </label>

        <label htmlFor="new-password">
          Mật khẩu mới
          <input
            id="new-password"
            type="password"
            value={newPassword}
            autoComplete="new-password"
            minLength={8}
            required
            onChange={(event) => setNewPassword(event.target.value)}
          />
        </label>

        <label htmlFor="confirm-password">
          Xác nhận mật khẩu mới
          <input
            id="confirm-password"
            type="password"
            value={confirmPassword}
            autoComplete="new-password"
            minLength={8}
            required
            onChange={(event) => setConfirmPassword(event.target.value)}
          />
        </label>

        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : null}
        {message ? <p className="success-message">{message}</p> : null}

        <div className="master-data-form-actions">
          <button className="primary-button" type="submit" disabled={submitting}>
            {submitting ? 'Đang đổi mật khẩu...' : 'Đổi mật khẩu'}
          </button>
        </div>
      </form>
    </section>
  );
}
