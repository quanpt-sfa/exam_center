import { useState } from 'react';
import { NavLink, useParams, Link } from 'react-router-dom';
import type { CurrentUser } from '../features/auth/authApi';

type ProctorRoomLayoutProps = {
  user: CurrentUser | null;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  onLogout: () => void;
  children: React.ReactNode;
};

export function ProctorRoomLayout({ user, theme, onToggleTheme, onLogout, children }: ProctorRoomLayoutProps) {
  const { sittingId, roomId } = useParams<{ sittingId: string; roomId: string }>();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [helpRequested, setHelpRequested] = useState(false);

  const baseUrl = `/proctor/sittings/${sittingId}/rooms/${roomId}`;

  return (
    <div className="app-shell">
      {/* Room specific sidebar */}
      <aside className={`sidebar${sidebarCollapsed ? ' collapsed' : ''}`} aria-label="Giám thị phòng thi">
        <a className="sidebar__brand" href="/dashboard">
          <span className="sidebar__brand-icon">P</span>
          <span className="sidebar__brand-text">Phòng {roomId || '...'}</span>
        </a>

        <nav className="sidebar__nav">
          <span className="sidebar__section-label">Giám sát phòng</span>
          <NavLink
            to={baseUrl}
            end
            data-label="Tổng quan"
            className={({ isActive }) => `sidebar__link${isActive ? ' active' : ''}`}
          >
            <span className="sidebar__link-icon" aria-hidden="true">📊</span>
            <span className="sidebar__link-label">Tổng quan</span>
          </NavLink>

          <NavLink
            to={`${baseUrl}/attendance`}
            data-label="Điểm danh"
            className={({ isActive }) => `sidebar__link${isActive ? ' active' : ''}`}
          >
            <span className="sidebar__link-icon" aria-hidden="true">📋</span>
            <span className="sidebar__link-label">Điểm danh</span>
          </NavLink>

          <NavLink
            to={`${baseUrl}/live`}
            data-label="Giám sát trực tiếp"
            className={({ isActive }) => `sidebar__link${isActive ? ' active' : ''}`}
          >
            <span className="sidebar__link-icon" aria-hidden="true">📡</span>
            <span className="sidebar__link-label">Giám sát live</span>
          </NavLink>

          <NavLink
            to={`${baseUrl}/incidents`}
            data-label="Báo cáo sự cố"
            className={({ isActive }) => `sidebar__link${isActive ? ' active' : ''}`}
          >
            <span className="sidebar__link-icon" aria-hidden="true">⚠️</span>
            <span className="sidebar__link-label">Sự cố</span>
          </NavLink>

          <span className="sidebar__section-label">Kết thúc</span>
          <NavLink
            to={`${baseUrl}/close`}
            data-label="Đóng phòng thi"
            className={({ isActive }) => `sidebar__link sidebar__link--danger${isActive ? ' active' : ''}`}
            style={({ isActive }) => isActive ? {} : { color: 'var(--clr-danger)' }}
          >
            <span className="sidebar__link-icon" aria-hidden="true">🔒</span>
            <span className="sidebar__link-label">Đóng & Niêm phong</span>
          </NavLink>
        </nav>

        <div className="sidebar__footer">
          <button
            type="button"
            className="sidebar__link"
            style={{ width: '100%', background: 'none', border: 'none', cursor: 'pointer', color: 'inherit' }}
            onClick={() => setSidebarCollapsed((c) => !c)}
            aria-label={sidebarCollapsed ? 'Mở rộng sidebar' : 'Thu gọn sidebar'}
            data-label={sidebarCollapsed ? 'Mở rộng' : 'Thu gọn'}
          >
            <span className="sidebar__link-icon" aria-hidden="true">
              {sidebarCollapsed ? '→' : '←'}
            </span>
            <span className="sidebar__link-label">{sidebarCollapsed ? 'Mở rộng' : 'Thu gọn'}</span>
          </button>
        </div>
      </aside>

      {/* Main viewport with custom Room Topbar */}
      <div className={`app-main${sidebarCollapsed ? ' sidebar-collapsed' : ''}`}>
        <header className="topbar" role="banner">
          <button
            type="button"
            className="topbar__toggle"
            onClick={() => setSidebarCollapsed((c) => !c)}
            aria-label="Bật/tắt sidebar"
          >
            ☰
          </button>

          {/* Active room live KPIs */}
          <div className="topbar__room-info" style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-4)', marginLeft: 'var(--sp-2)' }}>
            <span style={{ fontWeight: 'var(--fw-semibold)', fontSize: 'var(--text-sm)' }}>
              Phòng: <span style={{ color: 'var(--clr-primary-600)' }}>{roomId}</span>
            </span>
            <span style={{ height: '14px', width: '1px', background: 'var(--clr-gray-300)' }} />
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
              Ca thi: {sittingId}
            </span>
          </div>

          <span className="topbar__spacer" />

          {/* Room actions */}
          <div className="topbar__actions">
            {/* Emergency help flag button */}
            <button
              type="button"
              className={`topbar__action-link ${helpRequested ? 'topbar__action-link--danger' : ''}`}
              style={helpRequested ? { background: 'var(--clr-danger-light)', color: 'var(--clr-danger)', borderColor: 'var(--clr-danger)' } : {}}
              onClick={() => setHelpRequested((h) => !h)}
              title="Yêu cầu hỗ trợ khẩn cấp từ kỹ thuật viên"
            >
              🚨 {helpRequested ? 'Đang gọi kỹ thuật...' : 'Gọi hỗ trợ'}
            </button>

            <button
              type="button"
              className="topbar__action-link topbar__theme-toggle"
              onClick={onToggleTheme}
              title="Đổi giao diện"
            >
              {theme === 'light' ? '🌙' : '☀️'}
            </button>

            <Link to="/change-password" className="topbar__action-link">
              Đổi mật khẩu
            </Link>

            {user && (
              <button type="button" className="topbar__user-btn" onClick={onLogout} title="Đăng xuất">
                <span>{user.display_name || user.username}</span>
              </button>
            )}
          </div>
        </header>

        <main className="main-content">
          {children}
        </main>
      </div>
    </div>
  );
}
