import { Link } from 'react-router-dom';
import { CompactPage } from '../../shared/components/compact/CompactPage';
import { CompactSurface } from '../../shared/components/compact/CompactSurface';
import { AdminSurfaceHeader } from './components/AdminSurfaceHeader';

const landingCards = [
  {
    title: 'Học thuật',
    description: 'Danh mục khoa, chương trình, môn học, lớp học phần và ghi danh.',
    path: '/admin/master-data/academic',
  },
  {
    title: 'Con người',
    description: 'Hồ sơ sinh viên và giảng viên dùng chung toàn hệ thống.',
    path: '/admin/master-data/people',
  },
  {
    title: 'Cơ sở vật chất',
    description: 'Phòng thi, máy trạm, thiết bị và trạng thái sẵn sàng.',
    path: '/admin/facility',
  },
  {
    title: 'Import Center',
    description: 'Tải mẫu import, upload file và theo dõi tiến độ xử lý job.',
    path: '/admin/imports',
  },
];

export function MasterDataLandingPage() {
  return (
    <CompactPage className="master-data-page">
      <AdminSurfaceHeader
        eyebrow="Master data"
        title="Trung tâm dữ liệu nền"
        description="Chọn đúng surface để quản trị danh mục học thuật, hồ sơ người dùng, cơ sở vật chất hoặc import dữ liệu hàng loạt."
      />

      <section className="master-data-landing-grid" aria-label="Master data surfaces">
        {landingCards.map((card) => (
          <CompactSurface
            key={card.path}
            className="admin-module-card master-data-landing-card master-data-landing-card--compact"
            title={card.title}
            tight
          >
            <p>{card.description}</p>
            <Link className="primary-button compact-button" to={card.path}>
              Mở surface
            </Link>
          </CompactSurface>
        ))}
      </section>
    </CompactPage>
  );
}
