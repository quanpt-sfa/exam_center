import { useState } from 'react';
import { AdminSurfaceHeader } from '../components/AdminSurfaceHeader';
import { MasterDataShell } from '../components/MasterDataShell';
import { academicMasterDataEntities } from '../registry/masterDataEntities';
import type { MasterDataEntityKey } from '../types';

export function AcademicMasterDataPage() {
  const [activeKey, setActiveKey] = useState<MasterDataEntityKey>('departments');

  return (
    <div className="master-data-page">
      <AdminSurfaceHeader
        eyebrow="Master data / học thuật"
        title="Danh mục học thuật"
        description="Quản lý khoa, chương trình, môn học, lớp học phần và dữ liệu ghi danh đang phục vụ thiết lập thi."
      />
      <MasterDataShell entities={academicMasterDataEntities} activeKey={activeKey} onActiveKeyChange={setActiveKey} />
    </div>
  );
}
