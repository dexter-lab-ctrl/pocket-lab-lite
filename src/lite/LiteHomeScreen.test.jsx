// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('./LiteReleaseUpdateCard.jsx', () => ({ default: () => <p>Update information</p> }));
vi.mock('../hooks/useLiteQuery.js', () => ({ useLiteQuery: () => ({ data: null }) }));
import HomeScreen, { homeCommandHeroPresentation } from './LiteHome.jsx';

afterEach(cleanup);

const readyStatus = {
  overall: 'healthy',
  summary: { apps_available: 2, devices_known: 2, security_findings: 0, remote_access_ready: true },
  services: [
    { name: 'App Catalog', status: 'healthy' },
    { name: 'Device Fleet', status: 'healthy' },
    { name: 'Security', status: 'healthy' },
    { name: 'Recovery', status: 'healthy' },
    { name: 'Remote Access', status: 'healthy' },
  ],
};

describe('Azure Horizon Command Home — authored, qualification deferred', () => {
  it('renders a truthful ready hero and exactly four accessible destinations', () => {
    const onNavigate = vi.fn();
    render(<HomeScreen status={readyStatus} onNavigate={onNavigate} refresh={vi.fn()} />);
    expect(screen.getByRole('heading', { name: 'Everything is running smoothly' })).toBeTruthy();
    expect(document.querySelector('[data-home-hero-state="ready"]')).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Your workspace' })).toBeTruthy();
    expect(document.querySelectorAll('.lite-home-overview-grid > button')).toHaveLength(4);
    for (const title of ['Apps', 'Devices', 'Safety', 'Backups']) {
      expect(screen.getByRole('button', { name: 'Open ' + title })).toBeTruthy();
    }
    fireEvent.click(screen.getByRole('button', { name: 'Open Backups' }));
    expect(onNavigate).toHaveBeenCalledWith('recovery');
    expect(screen.queryByRole('heading', { name: 'Needs your attention' })).toBeNull();
  });

  it('prioritizes confirmed attention and navigates to the reported domain', () => {
    const navigate = vi.fn();
    const status = { ...readyStatus, overall: 'degraded',
      summary: { ...readyStatus.summary, security_findings: 1 },
      services: readyStatus.services.map((item) => item.name === 'Security'
        ? { ...item, status: 'degraded' } : item) };
    render(<HomeScreen status={status} refresh={vi.fn()} onNavigate={navigate} />);
    expect(document.querySelector('[data-home-hero-state="attention"]')).toBeTruthy();
    expect(screen.getByText('Needs your attention')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Review Safety' }));
    expect(navigate).toHaveBeenCalledWith('security');
  });

  it('shows the grouped index, a focused detail, then returns with Back', () => {
    render(<HomeScreen status={readyStatus} refresh={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Workspace details' }));
    const panel = screen.getByRole('dialog', { name: 'Workspace details' });
    const nav = within(panel).getByRole('navigation', { name: 'Workspace details sections' });
    expect(within(nav).getByText('Maintenance')).toBeTruthy();
    expect(within(nav).getByText('Workspace')).toBeTruthy();
    for (const label of ['Overview', 'Service health', 'Updates', 'Diagnostics']) {
      expect(within(nav).getByRole('button', { name: label })).toBeTruthy();
    }
    fireEvent.click(within(nav).getByRole('button', { name: 'Service health' }));
    expect(panel.querySelector('[data-home-settings-view="section"]')).toBeTruthy();
    expect(within(panel).getByRole('heading', { name: 'Service health' })).toBeTruthy();
    fireEvent.click(within(panel).getByRole('button', { name: /All workspace details sections/i }));
    expect(panel.querySelector('[data-home-settings-view="index"]')).toBeTruthy();
  });

  it('never treats saved, unavailable, partial or unknown information as current health', () => {
    const overview = { overallTone: 'ready', services: [{ key: 'security', tone: 'ready' }] };
    expect(homeCommandHeroPresentation({ overview, saved: true }).state).toBe('saved');
    expect(homeCommandHeroPresentation({ overview, reachable: false }).state).toBe('offline');
    expect(homeCommandHeroPresentation({ overview, partial: true }).state).toBe('partial');
    expect(homeCommandHeroPresentation({ overview: { overallTone: 'unknown', services: [] } }).state).toBe('unknown');
    expect(homeCommandHeroPresentation({ overview: { overallTone: 'unknown', services: [] }, loading: true }).state).toBe('loading');
    expect(homeCommandHeroPresentation({ overview, refreshing: true }).state).toBe('checking');
    expect(homeCommandHeroPresentation({ overview, running: true }).state).toBe('running');
  });

  it('preserves activity/history entry without fabricating events in an unavailable snapshot', () => {
    render(<HomeScreen status={readyStatus} savedStateOnly backendReachable={false} refresh={vi.fn()} />);
    expect(document.querySelector('[data-home-hero-state="offline"]')).toBeTruthy();
    expect(screen.getByText(/Live activity is unavailable/i)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /View all activity/i }));
    const panel = screen.getByRole('dialog', { name: 'Recent activity' });
    fireEvent.click(within(panel).getByRole('button', { name: 'History' }));
    expect(within(panel).getByText(/Reconnect to confirm a new review position/i)).toBeTruthy();
  });
});
