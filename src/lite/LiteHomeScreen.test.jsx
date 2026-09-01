// @vitest-environment jsdom
import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('./LiteReleaseUpdateCard.jsx', () => ({ default: () => null }));

import HomeScreen from './LiteHome.jsx';

const readyStatus = {
  overall: 'healthy',
  summary: {
    apps_available: 2,
    devices_known: 2,
    security_findings: 0,
    remote_access_ready: true,
  },
  services: [
    { name: 'App Catalog', status: 'healthy' },
    { name: 'Device Fleet', status: 'healthy' },
    { name: 'Security', status: 'healthy' },
    { name: 'Remote Access', status: 'healthy' },
  ],
};

describe('HomeScreen operational story', () => {
  it('renders one calm ready story, compact key areas, and details on demand', () => {
    render(<HomeScreen status={readyStatus} refresh={vi.fn()} onNavigate={vi.fn()} lastUpdatedLabel="just now" />);

    expect(screen.getByText('Your Pocket Lab is ready')).toBeTruthy();
    expect(screen.getByText('No immediate follow-up is required.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Browse Apps' })).toBeNull();
    expect(screen.getByText('Apps')).toBeTruthy();
    expect(screen.queryByText('Device health')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Workspace details' }));
    expect(screen.getByRole('dialog', { name: 'Workspace details' })).toBeTruthy();
    expect(screen.getByText('Device health')).toBeTruthy();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog', { name: 'Workspace details' })).toBeNull();
  });

  it('prioritizes the supported safety action without implying total failure', () => {
    const onNavigate = vi.fn();
    render(<HomeScreen
      status={{
        ...readyStatus,
        overall: 'degraded',
        summary: { ...readyStatus.summary, security_findings: 1 },
        services: readyStatus.services.map((service) => service.name === 'Security' ? { ...service, status: 'degraded' } : service),
      }}
      refresh={vi.fn()}
      onNavigate={onNavigate}
    />);

    expect(screen.getByText('A few areas need your attention')).toBeTruthy();
    expect(screen.getByText('Pocket Lab is still usable. Review the recommended next step before making important changes.')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Review Safety' }));
    expect(onNavigate).toHaveBeenCalledWith('security');
  });
});
