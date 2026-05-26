import { Link } from 'react-router-dom';
import type { CurrentUser } from '../features/auth/authApi';

type StudentPortalLayoutProps = {
  user: CurrentUser | null;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  onLogout: () => void;
  children: React.ReactNode;
};

export function StudentPortalLayout({ user, theme, onToggleTheme, onLogout, children }: StudentPortalLayoutProps) {
  return (
    <div className="app-shell" style={{ flexDirection: 'column' }}>
      {/* Student Portal Topbar (Wide layout, no sidebar toggle) */}
      <header className="topbar" style={{ left: 0, position: 'sticky' }} role="banner">
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)' }}>
          <span className="sidebar__brand-icon" style={{ background: 'var(--clr-primary-600)', color: '#fff', padding: 'var(--sp-1) var(--sp-2)', borderRadius: 'var(--radius-md)', fontWeight: 'var(--fw-bold)' }}>ES</span>
          <span style={{ fontWeight: 'var(--fw-semibold)', fontSize: 'var(--text-md)' }}>Cổng thông tin sinh viên</span>
        </div>

        <span className="topbar__spacer" />

        <div className="topbar__actions">
          <button
            type="button"
            className="topbar__action-link topbar__theme-toggle"
            onClick={onToggleTheme}
            aria-label="Đổi giao diện"
          >
            {theme === 'light' ? '🌙' : '☀️'}
          </button>
          <Link to="/change-password" className="topbar__action-link">
            Đổi mật khẩu
          </Link>
          {user && (
            <button
              type="button"
              className="topbar__user-btn"
              onClick={onLogout}
              title="Đăng xuất"
            >
              <span>{user.display_name || user.username}</span>
            </button>
          )}
        </div>
      </header>

      {/* Main content centered */}
      <main className="main-content" style={{ padding: 'var(--sp-6) var(--sp-4)', width: '100%', maxWidth: '1200px', margin: '0 auto' }}>
        {children}
      </main>
    </div>
  );
}
