import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, test, vi } from 'vitest';
import { Sidebar } from './Sidebar';

describe('Sidebar', () => {
  test('admin sees dashboard entry but no separate admin dashboard label', () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Sidebar
          user={{
            user_id: 1,
            username: 'admin',
            roles: ['ADMIN'],
            permissions: ['master_data:read'],
          }}
          collapsed={false}
          onToggle={vi.fn()}
        />
      </MemoryRouter>
    );

    expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveAttribute('href', '/dashboard');
    expect(screen.queryByRole('link', { name: 'Admin Dashboard' })).not.toBeInTheDocument();
  });

  test('hides master data navigation when user lacks permission', () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Sidebar
          user={{
            user_id: 10,
            username: 'gv01',
            roles: ['INSTRUCTOR'],
            permissions: ['grading.grade'],
          }}
          collapsed={false}
          onToggle={vi.fn()}
        />
      </MemoryRouter>
    );

    expect(screen.queryByRole('link', { name: /Master Data/i })).not.toBeInTheDocument();
  });

  test('shows master data navigation when user has facility permission', () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Sidebar
          user={{
            user_id: 11,
            username: 'staff01',
            roles: ['INSTRUCTOR'],
            permissions: ['facility:read'],
          }}
          collapsed={false}
          onToggle={vi.fn()}
        />
      </MemoryRouter>
    );

    expect(screen.getByRole('link', { name: /Master Data/i })).toHaveAttribute('href', '/admin/master-data');
    expect(screen.getByRole('link', { name: /Cơ sở vật chất/i })).toHaveAttribute('href', '/admin/facility');
  });
});