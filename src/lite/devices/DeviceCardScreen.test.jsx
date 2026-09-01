// @vitest-environment jsdom
import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import DeviceCard from './DeviceCard.jsx';

describe('DeviceCard operational stories', () => {
  it('shows a connected device with independent remote-access attention and Manage', () => {
    render(<DeviceCard
      device={{ id: 'phone', name: 'Studio phone', role: 'mobile', status: 'online', connection: 'online', remote_access: { ready: false, status: 'remote_access_not_ready' } }}
      onOpenDetails={vi.fn()}
    />);

    expect(screen.getByText('Connected')).toBeTruthy();
    expect(screen.getByText('Remote access')).toBeTruthy();
    expect(screen.getByText('This is separate from the local Pocket Lab connection.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Restart agent' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Manage Studio phone' })).toBeTruthy();
  });

  it('only exposes prepared restart recovery as the primary action', () => {
    const restart = vi.fn();
    render(<DeviceCard
      device={{ id: 'phone', name: 'Studio phone', role: 'mobile', status: 'agent_stopped', restart_agent_assessment: { allowed: true, command_deliverable: true } }}
      onRestartAgent={restart}
      onOpenDetails={vi.fn()}
    />);

    expect(screen.getByText('Agent stopped')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Restart agent' }));
    expect(restart).toHaveBeenCalledOnce();
  });

  it('keeps saved and protected devices out of live or removal presentation', () => {
    const { container, rerender } = render(<DeviceCard
      device={{ id: 'phone', name: 'Studio phone', role: 'mobile', status: 'online', connection: 'online' }}
      savedStateOnly
      onOpenDetails={vi.fn()}
    />);
    expect(screen.getByText('Showing saved device information')).toBeTruthy();
    expect(container.querySelector('[data-connection-state="disconnected"]')).toBeTruthy();
    expect(container.querySelector('button[aria-label="Restart agent"]')).toBeNull();

    rerender(<DeviceCard
      device={{ id: 'server', name: 'Pocket Lab Server', role: 'server_host', status: 'online', connection: 'online', protected_server_host: true }}
      onOpenDetails={vi.fn()}
      onRemoveDevice={vi.fn()}
    />);
    expect(screen.getByText('Pocket Lab server')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /remove device/i })).toBeNull();
  });
});
