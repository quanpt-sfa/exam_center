import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, test } from 'vitest';
import { CompactActionGroup, IconActionButton, RowActionGroup, ToolbarActionGroup } from './IconActionButton';

describe('IconActionButton', () => {
  test('supports icon-only button with accessible name and tooltip metadata', () => {
    render(<IconActionButton icon="refresh" label="Tải lại" onClick={() => {}} />);

    const button = screen.getByRole('button', { name: 'Tải lại' });
    expect(button).toHaveClass('compact-icon-action');
    expect(button).toHaveAttribute('title', 'Tải lại');
  });

  test('supports icon link actions with explicit label when needed', () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <IconActionButton icon="view" label="Xem chi tiết" to="/details/10" showLabel={true} />
      </MemoryRouter>
    );

    const link = screen.getByRole('link', { name: 'Xem chi tiết' });
    expect(link).toHaveAttribute('href', '/details/10');
    expect(link).toHaveTextContent('Xem chi tiết');
  });

  test('group mode icon forces icon-only rendering for all child action buttons', () => {
    render(
      <CompactActionGroup mode="icon">
        <IconActionButton icon="refresh" label="Tải lại" showLabel={true} onClick={() => {}} />
      </CompactActionGroup>
    );

    const group = screen.getByRole('button', { name: 'Tải lại' }).closest('[data-action-group="true"]');
    expect(group).toHaveAttribute('data-action-mode', 'icon');
    expect(screen.queryByText('Tải lại')).not.toBeInTheDocument();
  });

  test('group mode iconText forces icon+text rendering for all child action buttons', () => {
    render(
      <CompactActionGroup mode="iconText">
        <IconActionButton icon="refresh" label="Tải lại" onClick={() => {}} />
      </CompactActionGroup>
    );

    expect(screen.getByText('Tải lại')).toBeInTheDocument();
  });

  test('row and toolbar groups default to icon mode', () => {
    render(
      <>
        <RowActionGroup>
          <IconActionButton icon="edit" label="Sửa" onClick={() => {}} />
        </RowActionGroup>
        <ToolbarActionGroup>
          <IconActionButton icon="refresh" label="Làm mới" onClick={() => {}} />
        </ToolbarActionGroup>
      </>
    );

    const groups = document.querySelectorAll('[data-action-group="true"]');
    expect(groups).toHaveLength(2);
    groups.forEach((group) => {
      expect(group).toHaveAttribute('data-action-mode', 'icon');
    });
  });
});
