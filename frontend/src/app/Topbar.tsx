import { Link } from 'react-router-dom';
import type { CurrentUser } from '../features/auth/authApi';

function userInitials(user: CurrentUser): string {
  const name = user.display_name || user.username || user.email || '?';
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

type TopbarProps = {
  user: CurrentUser | null;
  theme: 'light' | 'dark';
  onToggleSidebar: () => void;
  onToggleTheme: () => void;
  onLogout: () => void;
};

export function Topbar({ user, theme, onToggleSidebar, onToggleTheme, onLogout }: TopbarProps) {
  return (
    <header className="topbar" role="banner">
      {/* Sidebar toggle */}
      <button
        type="button"
        className="topbar__toggle"
        onClick={onToggleSidebar}
        aria-label="Bật/tắt sidebar"
        title="Bật/tắt sidebar"
      >
        ☰
      </button>

      <span className="topbar__spacer" />

      {/* Actions */}
      <div className="topbar__actions">
        {user ? (
          <>
            <button
              type="button"
              className="topbar__action-link topbar__theme-toggle"
              onClick={onToggleTheme}
              aria-label={theme === 'light' ? 'Chuyển sang chế độ tối' : 'Chuyển sang chế độ sáng'}
              title={theme === 'light' ? 'Chuyển sang chế độ tối' : 'Chuyển sang chế độ sáng'}
            >
              {theme === 'light' ? '🌙' : '☀️'}
            </button>
            <Link to="/change-password" className="topbar__action-link">
              Đổi mật khẩu
            </Link>
            <button
              type="button"
              className="topbar__user-btn"
              onClick={onLogout}
              title="Đăng xuất"
            >
              <span className="topbar__user-avatar" aria-hidden="true">
                {userInitials(user)}
              </span>
              <span>{user.display_name || user.username || user.email}</span>
            </button>
          </>
        ) : null}
      </div>
    </header>
  );
}
