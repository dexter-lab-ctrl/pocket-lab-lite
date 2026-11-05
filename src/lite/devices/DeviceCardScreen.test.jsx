// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import DeviceCard from './DeviceCard.jsx';

afterEach(cleanup);

describe('Azure Horizon native device library card — authored, not executed', () => {
  it('shows one Manage entry without flooding the card with remote access, technical or restart controls', () => {
    const open = vi.fn();
    const { container } = render(<DeviceCard
      device={{ id: 'phone', name: 'Studio phone', role: 'mobile', status: 'online', connection: 'online',
        remote_access: { ready: false, status: 'remote_access_not_ready' } }}
      onOpenDetails={open}
    />);
    expect(screen.getByText('Studio phone')).toBeTruthy();
    expect(container.querySelector('.lite-device-library-identity')).toBeTruthy();
    expect(screen.queryByText('Remote access')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Restart agent' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Manage Studio phone' }));
    expect(open).toHaveBeenCalledOnce();
  });

  it('keeps agent-stopped attention visible while deferring execution to Manage', () => {
    const open = vi.fn();
    render(<DeviceCard
      device={{ id: 'phone', name: 'Studio phone', role: 'mobile', status: 'agent_stopped',
        restart_agent_assessment: { allowed: true, command_deliverable: true } }}
      onRestartAgent={vi.fn()} onOpenDetails={open}
    />);
    expect(screen.getByText(/Agent stopped|Not confirmed/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Restart agent' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Manage Studio phone' }));
    expect(open).toHaveBeenCalledOnce();
  });

  it('does not present saved information as confirmed connectivity or enable server removal', () => {
    const { container, rerender } = render(<DeviceCard
      device={{ id: 'phone', name: 'Studio phone', role: 'mobile', status: 'online', connection: 'online' }}
      savedStateOnly onOpenDetails={vi.fn()}
    />);
    expect(screen.getByText('Saved · connection not confirmed')).toBeTruthy();
    expect(container.querySelector('[data-connection-state="stale"]')).toBeTruthy();
    rerender(<DeviceCard
      device={{ id: 'server', name: 'Pocket Lab Server', role: 'server_host', status: 'online',
        connection: 'online', protected_server_host: true }} onOpenDetails={vi.fn()} onRemoveDevice={vi.fn()}
    />);
    expect(screen.getAllByText('Protected server host')).toHaveLength(2);
    expect(screen.queryByRole('button', { name: /Remove device/i })).toBeNull();
    expect(screen.getByRole('button', { name: 'Manage Pocket Lab Server' })).toBeTruthy();
  });

  it('keeps long names in one accessible identity and maintains the existing Manage affordance', () => {
    const name = 'Secondary laboratory phone with a considerably long human friendly name';
    render(<DeviceCard device={{ id: 'long', name, status: 'waiting', role: 'compute' }} onOpenDetails={vi.fn()} />);
    expect(screen.getByRole('heading', { name })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Manage ' + name })).toBeTruthy();
  });
});
