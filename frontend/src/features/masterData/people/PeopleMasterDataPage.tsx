import { useState } from 'react';
import { AdminSurfaceHeader } from '../components/AdminSurfaceHeader';
import { MasterDataShell } from '../components/MasterDataShell';
import { peopleMasterDataEntities } from '../registry/masterDataEntities';
import type { MasterDataEntityKey } from '../types';

export function PeopleMasterDataPage() {
  const [activeKey, setActiveKey] = useState<MasterDataEntityKey>('students');

  return (
    <div className="master-data-page">
      <AdminSurfaceHeader
        eyebrow="Master data / con người"
        title="Sinh viên và giảng viên"
        description="Duy trì hồ sơ người học và giảng viên làm nguồn dữ liệu cho phân quyền, lớp học và cấu hình thi."
      />
      <MasterDataShell entities={peopleMasterDataEntities} activeKey={activeKey} onActiveKeyChange={setActiveKey} />
    </div>
  );
}
