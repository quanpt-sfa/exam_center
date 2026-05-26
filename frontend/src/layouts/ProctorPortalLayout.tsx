import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import type { CurrentUser } from '../features/auth/authApi';
import { Topbar } from '../app/Topbar';

type ProctorPortalLayoutProps = {
  user: CurrentUser | null;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  onLogout: () => void;
  children: React.ReactNode;
};

export function ProctorPortalLayout({ user, theme, onToggleTheme, onLogout, children }: ProctorPortalLayoutProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div className="app-shell">
      {/* Proctor Specific Sidebar */}
      <aside className={`sidebar${sidebarCollapsed ? ' collapsed' : ''}`} aria-label="Điều hướng giám thị">
        <a className="sidebar__brand" href="/dashboard">
          <span className="sidebar__brand-icon">ES</span>
          <span className="sidebar__brand-text">Invigilator</span>
        </a>

        <nav className="sidebar__nav">
          <span className="sidebar__section-label">Lịch gác thi</span>
          <NavLink
            to="/proctor/sittings"
            data-label="Ca thi gác"
            className={({ isActive }) => `sidebar__link${isActive ? ' active' : ''}`}
          >
            <span className="sidebar__link-icon" aria-hidden="true">📅</span>
            <span className="sidebar__link-label">Ca thi của tôi</span>
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

      <div className={`app-main${sidebarCollapsed ? ' sidebar-collapsed' : ''}`}>
        <Topbar
          user={user}
          theme={theme}
          onToggleSidebar={() => setSidebarCollapsed((c) => !c)}
          onToggleTheme={onToggleTheme}
          onLogout={onLogout}
        />
        <main className="main-content">
          {children}
        </main>
      </div>
    </div>
  );
}
