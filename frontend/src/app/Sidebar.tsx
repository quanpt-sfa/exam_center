import { NavLink } from 'react-router-dom';
import {
  canAccessMasterData,
  hasAnyPermission,
  hasRole,
  MASTER_DATA_ACCESS_PERMISSIONS,
  type CurrentUser,
} from '../features/auth/authApi';

type NavItem = {
  label: string;
  path: string;
  icon: string;
  roles?: string[];
  permissions?: string[];
};

const navItems: NavItem[] = [
  { label: 'Dashboard', path: '/dashboard', icon: 'D' },
  { label: 'Tài khoản', path: '/admin/accounts', icon: 'U', roles: ['ADMIN'] },
  { label: 'Master Data', path: '/admin/master-data', icon: 'M', permissions: [...MASTER_DATA_ACCESS_PERMISSIONS] },
  { label: 'Học thuật', path: '/admin/master-data/academic', icon: 'A', permissions: ['master_data:read', 'master_data:write', 'master_data:publish'] },
  { label: 'Con người', path: '/admin/master-data/people', icon: 'P', permissions: ['master_data:read', 'master_data:write', 'master_data:publish'] },
  { label: 'Cơ sở vật chất', path: '/admin/facility', icon: 'F', permissions: ['facility:read', 'facility:write', 'master_data:read', 'master_data:write'] },
  { label: 'Imports', path: '/admin/imports', icon: 'I', permissions: ['master_data:import', 'master_data:write', 'master_data:publish'] },
  { label: 'Thiết lập thi', path: '/admin/exam-setup', icon: 'E', roles: ['ADMIN'] },
  { label: 'Soạn đề', path: '/admin/exam-setup/authoring', icon: 'W', roles: ['ADMIN'] },
  { label: 'Ca thi', path: '/admin/exam-setup/delivery', icon: 'R', roles: ['ADMIN'] },
  { label: 'Bảng điểm', path: '/grading/gradebook', icon: 'G', roles: ['ADMIN', 'ACADEMIC_OFFICER', 'INSTRUCTOR'] },
  { label: 'Phòng giám thị', path: '/proctor/sittings', icon: 'S', roles: ['PROCTOR'] },
  { label: 'Cấu hình', path: '/admin/settings', icon: 'C', roles: ['ADMIN'] },
  { label: 'Lớp thi', path: '/exams', icon: 'X', roles: ['STUDENT', 'SV', 'SINHVIEN'] },
];

function normalizeRole(role: string) {
  return role.trim().toUpperCase();
}

function canSeeItem(item: NavItem, user: CurrentUser): boolean {
  if (item.path === '/admin/master-data') {
    return canAccessMasterData(user);
  }

  if (item.roles && !hasRole(user, item.roles)) {
    return false;
  }

  if (item.permissions && !hasAnyPermission(user, item.permissions)) {
    return false;
  }

  if (!item.roles && !item.permissions) {
    return true;
  }

  if (item.roles) {
    const userRoles = new Set(user.roles.map(normalizeRole));
    return item.roles.some((role) => userRoles.has(normalizeRole(role)));
  }

  return true;
}

type SidebarProps = {
  user: CurrentUser | null;
  collapsed: boolean;
  onToggle: () => void;
};

export function Sidebar({ user, collapsed, onToggle }: SidebarProps) {
  const visibleItems = user ? navItems.filter((item) => canSeeItem(item, user)) : [];

  return (
    <aside className={`sidebar${collapsed ? ' collapsed' : ''}`} aria-label="Điều hướng chính">
      <a className="sidebar__brand" href="/dashboard">
        <span className="sidebar__brand-icon">ES</span>
        <span className="sidebar__brand-text">Exam Sys</span>
      </a>

      <nav className="sidebar__nav">
        {visibleItems.length > 0 ? (
          <>
            <span className="sidebar__section-label">Menu</span>
            {visibleItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                data-label={item.label}
                className={({ isActive }) => `sidebar__link${isActive ? ' active' : ''}`}
              >
                <span className="sidebar__link-icon" aria-hidden="true">
                  {item.icon}
                </span>
                <span className="sidebar__link-label">{item.label}</span>
              </NavLink>
            ))}
          </>
        ) : null}
      </nav>

      <div className="sidebar__footer">
        <button
          type="button"
          className="sidebar__link"
          style={{ width: '100%', background: 'none', border: 'none', cursor: 'pointer', color: 'inherit' }}
          onClick={onToggle}
          aria-label={collapsed ? 'Mở rộng sidebar' : 'Thu gọn sidebar'}
          data-label={collapsed ? 'Mở rộng' : 'Thu gọn'}
          title={collapsed ? 'Mở rộng' : 'Thu gọn'}
        >
          <span className="sidebar__link-icon" aria-hidden="true">
            {collapsed ? '>' : '<'}
          </span>
          <span className="sidebar__link-label">{collapsed ? 'Mở rộng' : 'Thu gọn'}</span>
        </button>
      </div>
    </aside>
  );
}
