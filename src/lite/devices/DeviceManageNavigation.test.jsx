// @vitest-environment jsdom
// AUTHORED — NOT EXECUTED — UNVALIDATED
import React from 'react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import DeviceManageNavigation from './DeviceManageNavigation.jsx';
import { LiteHistoryTimeline } from '../LiteUx.jsx';

afterEach(cleanup);

describe('Native Devices Manage navigation and history', () => {
  it('renders persistent desktop groups and exposes a single current section', () => {
    const onSelect = vi.fn();
    render(<DeviceManageNavigation activeArea="health" onSelect={onSelect} />);
    const nav = screen.getByRole('navigation', { name: 'Device management sections' });
    expect(within(nav).getByRole('button', { name: 'Health' })).toHaveAttribute('aria-current', 'page');
    expect(within(nav).getByRole('button', { name: 'Backup' })).toBeInTheDocument();
    fireEvent.click(within(nav).getByRole('button', { name: 'Services' }));
    expect(onSelect).toHaveBeenCalledWith('services');
  });

  it('keeps peer-only controls unavailable for protected server hosts', () => {
    render(<DeviceManageNavigation isProtectedServer mobile />);
    const nav = screen.getByRole('navigation', { name: 'Device management sections' });
    expect(within(nav).queryByRole('button', { name: 'Roles' })).not.toBeInTheDocument();
    expect(within(nav).queryByRole('button', { name: 'Backup' })).not.toBeInTheDocument();
    expect(within(nav).getByRole('button', { name: 'Health' }).querySelector('svg')).toBeTruthy();
  });

  it('reuses the shared history timeline with date groups and meaning-specific icons', () => {
    const { container } = render(<LiteHistoryTimeline variant="devices" items={[
      { id: 'online', state: 'device_online', eventKind: 'online', date: 'Nov 5, 2026', title: 'Device returned online', time: '11:08 AM' },
      { id: 'offline', state: 'offline', eventKind: 'alert', date: 'Nov 5, 2026', title: 'Connection lost', time: '11:07 AM' },
      { id: 'recovery', eventKind: 'recover', date: 'Nov 4, 2026', title: 'Recovery requested', summary: 'Server reported the action.' },
    ]} />);
    expect(container.querySelectorAll('.lite-device-event-date')).toHaveLength(2);
    expect(container.querySelectorAll('.lite-ux-history-marker svg')).toHaveLength(3);
    expect(screen.getByText('Connection lost')).toBeInTheDocument();
    expect(screen.getByText('Server reported the action.')).toBeInTheDocument();
  });
});
