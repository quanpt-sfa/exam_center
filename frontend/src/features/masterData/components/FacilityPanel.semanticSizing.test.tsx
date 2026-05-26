import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, test, vi } from 'vitest';
import { FacilityPanel } from './FacilityPanel';

function renderPanel(activeKey: 'stations' | 'devices' | 'device-readiness') {
  return render(
    <FacilityPanel
      activeKey={activeKey}
      selectedRoomId={1}
      roomItems={[{ room_id: 1, room_code: 'D13', room_name: 'Phòng D13' }]}
      bulkPattern="grid"
      bulkRows="A,B,C"
      bulkStart="1"
      bulkEnd="6"
      bulkZeroPad="0"
      bulkPreview="A1, A2"
      deviceAssignDeviceId=""
      deviceAssignStationId=""
      retireDeviceId=""
      onRoomChange={vi.fn()}
      onBulkPatternChange={vi.fn()}
      onBulkRowsChange={vi.fn()}
      onBulkStartChange={vi.fn()}
      onBulkEndChange={vi.fn()}
      onBulkZeroPadChange={vi.fn()}
      onBulkGenerateStations={vi.fn()}
      bulkGenerating={false}
      onDeviceAssignDeviceIdChange={vi.fn()}
      onDeviceAssignStationIdChange={vi.fn()}
      onAssignDeviceToStation={vi.fn()}
      assigningDevice={false}
      onRetireDeviceIdChange={vi.fn()}
      onRetireDevice={vi.fn()}
      retiringDevice={false}
    />
  );
}

describe('FacilityPanel semantic sizing alignment', () => {
  test('stations custom bulk form fields expose semantic sizing attributes', () => {
    renderPanel('stations');

    const patternField = screen.getByLabelText('Dạng tạo').closest('div');
    expect(patternField).toHaveClass('master-data-field', 'field-span-sm');
    expect(patternField).toHaveAttribute('data-field-kind', 'select');
    expect(patternField).toHaveAttribute('data-field-size', 'sm');
    expect(patternField).toHaveAttribute('data-grid-span', '3');

    const startField = screen.getByLabelText('Số bắt đầu').closest('div');
    const startInput = screen.getByLabelText('Số bắt đầu');
    expect(startField).toHaveClass('master-data-field', 'field-span-xs');
    expect(startField).toHaveAttribute('data-field-kind', 'numeric');
    expect(startField).toHaveAttribute('data-grid-span', '2');
    expect(startInput).toHaveClass('master-data-control', 'master-data-control--xs');
  });

  test('device action custom fields keep label/id associations and semantic sizing', () => {
    renderPanel('devices');

    const assignDeviceInput = screen.getByLabelText('ID thiết bị');
    const assignDeviceLabel = screen.getByText('ID thiết bị').closest('label');
    expect(assignDeviceInput).toHaveAttribute('id', 'facility-assign-device-id');
    expect(assignDeviceLabel).toHaveAttribute('for', 'facility-assign-device-id');

    const assignStationInput = screen.getByLabelText('ID vị trí máy');
    expect(assignStationInput).toHaveAttribute('id', 'facility-assign-station-id');

    const retireInput = screen.getByLabelText('ID thiết bị ngừng sử dụng');
    expect(retireInput).toHaveAttribute('id', 'facility-retire-device-id');

    const wrapper = assignDeviceInput.closest('div');
    expect(wrapper).toHaveClass('master-data-field', 'field-span-sm');
    expect(wrapper).toHaveAttribute('data-field-kind', 'id');
    expect(wrapper).toHaveAttribute('data-field-size', 'sm');
    expect(assignDeviceInput).toHaveClass('master-data-control', 'master-data-control--sm');
  });

  test('device form DOM order is stable and compact action buttons remain reachable', () => {
    renderPanel('devices');

    const deviceSurface = screen.getByText('Thao tác thiết bị').closest('.compact-surface') as HTMLElement;
    const inputs = within(deviceSurface).getAllByRole('textbox');
    expect(inputs.map((input) => input.getAttribute('id'))).toEqual([
      'facility-assign-device-id',
      'facility-assign-station-id',
      'facility-retire-device-id',
    ]);

    const assignWrapperBefore = inputs[0].closest('div')?.className;
    fireEvent.change(inputs[0], { target: { value: '7' } });
    fireEvent.change(inputs[1], { target: { value: '11' } });
    const assignWrapperAfter = screen.getByLabelText('ID thiết bị').closest('div')?.className;
    expect(assignWrapperAfter).toBe(assignWrapperBefore);

    const assignButton = within(deviceSurface).getByRole('button', { name: 'Gán vào vị trí' });
    const retireButton = within(deviceSurface).getByRole('button', { name: 'Ngừng sử dụng' });
    expect(assignButton).toBeEnabled();
    expect(retireButton).toBeEnabled();
  });
});
