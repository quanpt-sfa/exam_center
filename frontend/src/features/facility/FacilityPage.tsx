import { useState } from 'react';
import { AdminSurfaceHeader } from '../masterData/components/AdminSurfaceHeader';
import { MasterDataShell } from '../masterData/components/MasterDataShell';
import { facilityMasterDataEntities } from '../masterData/registry/masterDataEntities';
import type { MasterDataEntityKey } from '../masterData/types';

export function FacilityPage() {
  const [activeKey, setActiveKey] = useState<MasterDataEntityKey>('rooms');

  return (
    <div className="master-data-page">
      <AdminSurfaceHeader
        eyebrow="Facility"
        title="Cơ sở vật chất phòng thi"
        description="Quản lý phòng thi, vị trí máy trạm, thiết bị và trạng thái readiness trước khi vận hành ca thi."
      />
      <MasterDataShell entities={facilityMasterDataEntities} activeKey={activeKey} onActiveKeyChange={setActiveKey} />
    </div>
  );
}
