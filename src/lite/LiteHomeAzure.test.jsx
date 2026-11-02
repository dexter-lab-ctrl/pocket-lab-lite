// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';

vi.mock('./LiteReleaseUpdateCard.jsx', () => ({ default: () => <p>Update details</p> }));
vi.mock('../hooks/useLiteQuery.js', () => ({ useLiteQuery: ({ path }) => ({
  data: path === '/api/lite/system/activity-summary' ? {
    summary: 'Latest workspace activity', counts_available: true,
    recent_events: [{ domain: 'devices', label: 'Device restart', status: 'succeeded',
      occurred_at_epoch_ms: 1780000000000 }],
    active_operations: 0, queued_operations: 0, recent_completed: 1, attention_required: 0,
  } : null,
}) }));
vi.mock('../lib/liteApi.js', () => ({ liteApi: {
  homeActivityCursor: vi.fn(async () => ({ changed_since_review: false })),
  reviewHomeActivityCursor: vi.fn(async () => ({ changed_since_review: false })),
} }));
import HomeScreen from './LiteHome.jsx';

afterEach(cleanup);
const status = {
  overall: 'healthy',
  summary: { apps_available: 1, devices_known: 1, security_findings: 0, remote_access_ready: true },
  services: [
    { name: 'App Catalog', status: 'healthy' },
    { name: 'Device Fleet', status: 'healthy' },
    { name: 'Security', status: 'healthy' },
    { name: 'Recovery', status: 'healthy' },
  ],
};

describe('Azure Horizon Home preserves existing authority and actions', () => {
  it('keeps four backend-derived overview areas and on-demand activity history', () => {
    const onNavigate = vi.fn();
    render(<HomeScreen status={status} onNavigate={onNavigate} refresh={vi.fn()} />);
    expect(document.querySelector('[data-azure-horizon-home="true"]')).toBeTruthy();
    for (const title of ['Apps','Devices','Safety','Backups']) {
      expect(screen.getByRole('button', { name: 'Open ' + title })).toBeTruthy();
    }
    fireEvent.click(screen.getByRole('button', { name: 'Open Backups' }));
    expect(onNavigate).toHaveBeenCalledWith('recovery');
    fireEvent.click(screen.getByRole('button', { name: /View all activity/i }));
    const activityDialog = screen.getByRole('dialog', { name: 'Recent activity' });
    expect(activityDialog).toBeTruthy();
    fireEvent.click(within(activityDialog).getByRole('button', { name: 'Recent' }));
    expect(within(activityDialog).getByText('Device restart')).toBeTruthy();
  });

  it('retains Overview, Service health, Updates and Diagnostics in one details panel', () => {
    render(<HomeScreen status={status} refresh={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Workspace details' }));
    const dialog = screen.getByRole('dialog', { name: 'Workspace details' });
    const tabs = within(dialog).getByRole('navigation', { name: 'Workspace details sections' });
    for (const section of ['Overview','Service health','Updates','Diagnostics']) {
      fireEvent.click(within(tabs).getByRole('button', { name: section }));
      expect(within(tabs).getByRole('button', { name: section }).getAttribute('aria-current')).toBe('page');
    }
  });

  it('reuses the shared three-point mobile snap sheet for both Home detail panels', () => {
    const originalWidth = window.innerWidth;
    const originalMatchMedia = window.matchMedia;
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 390 });
    window.matchMedia = vi.fn((query) => ({
      matches: query === '(min-width: 701px)' ? false : false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));

    try {
      render(<HomeScreen status={status} refresh={vi.fn()} />);
      fireEvent.click(screen.getByRole('button', { name: 'Workspace details' }));
      let dialog = screen.getByRole('dialog', { name: 'Workspace details' });
      expect(dialog.getAttribute('data-home-panel-layout')).toBe('mobile-sheet');
      expect(dialog.getAttribute('data-lite-sheet-snap')).toBe('medium');
      fireEvent.click(within(dialog).getByRole('button', { name: 'Compact', exact: true }));
      expect(dialog.getAttribute('data-lite-sheet-snap')).toBe('compact');
      fireEvent.click(within(dialog).getByRole('button', { name: 'Expand', exact: true }));
      fireEvent.click(within(dialog).getByRole('button', { name: 'Expand', exact: true }));
      expect(dialog.getAttribute('data-lite-sheet-snap')).toBe('expanded');
      fireEvent.click(within(dialog).getByRole('button', { name: 'Close Home details' }));
      fireEvent.click(screen.getByRole('button', { name: /View all activity/i }));
      dialog = screen.getByRole('dialog', { name: 'Recent activity' });
      expect(dialog.getAttribute('data-home-panel-layout')).toBe('mobile-sheet');
      expect(dialog.getAttribute('data-lite-sheet-snap')).toBe('medium');
      fireEvent.click(within(dialog).getByRole('button', { name: 'Compact', exact: true }));
      expect(dialog.getAttribute('data-lite-sheet-snap')).toBe('compact');
      fireEvent.click(within(dialog).getByRole('button', { name: 'Close Home details' }));
      fireEvent.click(screen.getByRole('button', { name: 'Workspace details' }));
      expect(screen.getByRole('dialog', { name: 'Workspace details' }).getAttribute('data-lite-sheet-snap')).toBe('medium');
    } finally {
      Object.defineProperty(window, 'innerWidth', { configurable: true, value: originalWidth });
      window.matchMedia = originalMatchMedia;
    }
  });

  it('never converts saved or unreachable information into a live operational claim', () => {
    render(<HomeScreen status={status} savedStateOnly backendReachable={false} refresh={vi.fn()} />);
    expect(screen.getAllByText(/Saved information|Saved/i).length).toBeGreaterThan(0);
    expect(screen.queryByText('Your workspace is flowing smoothly')).toBeNull();
    expect(screen.getByRole('button', { name: 'Workspace details' })).toBeTruthy();
  });
});
