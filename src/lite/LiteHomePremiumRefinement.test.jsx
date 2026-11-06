// @vitest-environment jsdom
// P6 qualification asset — AUTHORED, NOT EXECUTED.
import React, { useRef, useState } from 'react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import HomeScreen, { homeWorkflowNodeStates } from './LiteHome.jsx';
import HomeGroupedSections from './components/HomeGroupedSections.jsx';
import HomeActivityDetails from './components/HomeActivityDetails.jsx';
import LiteNextSteps from './components/LiteNextSteps.jsx';
import { liteHapticTarget } from '../lib/liteGlobalHaptics.js';

vi.mock('./LiteReleaseUpdateCard.jsx', () => ({ default: () => <div>Update information</div> }));
vi.mock('../hooks/useLiteQuery.js', () => ({ useLiteQuery: () => ({ data: null }) }));
afterEach(cleanup);

const status = {
  overall: 'healthy',
  summary: { apps_available: 1, devices_known: 1, security_findings: 0 },
  services: [
    { name: 'App Catalog', status: 'healthy' },
    { name: 'Device Fleet', status: 'healthy' },
    { name: 'Security', status: 'healthy' },
    { name: 'Recovery', status: 'healthy' },
  ],
};

function NavigationFixture() {
  const [section, setSection] = useState(null);
  const navRef = useRef(null);
  const navigation = { navRef, reveal: vi.fn() };
  return <HomeGroupedSections title="Workspace details" section={section} onSectionChange={setSection}
    defaultSection="overview" navigation={navigation}
    groups={[{ label: 'Workspace', items: [
      { id: 'overview', label: 'Overview', description: 'Facts', icon: () => null },
      { id: 'service-health', label: 'Service health', description: 'Status', icon: () => null },
    ] }]}>
    <p>Selected {section || 'overview'}</p>
  </HomeGroupedSections>;
}

describe('Azure Horizon Home premium refinement P0–P6 (unqualified)', () => {
  it('preserves four destination cards and makes all delegated haptic targets native buttons', () => {
    const navigate = vi.fn();
    render(<HomeScreen status={status} onNavigate={navigate} refresh={vi.fn()} />);
    const destinations = document.querySelectorAll('[data-home-destination]');
    expect(destinations).toHaveLength(4);
    expect(Array.from(destinations, (item) => item.getAttribute('data-home-destination')))
      .toEqual(['catalog', 'devices', 'security', 'recovery']);
    for (const item of destinations) {
      expect(item.tagName).toBe('BUTTON');
      expect(liteHapticTarget({ target: item })).toBe(item);
    }
    fireEvent.click(screen.getByRole('button', { name: 'Open Devices' }));
    expect(navigate).toHaveBeenCalledWith('devices');
  });

  it('marks destination information as saved and does not imply verified live health', () => {
    render(<HomeScreen status={status} backendReachable={false} savedStateOnly refresh={vi.fn()} />);
    expect(document.querySelector('[data-home-hero-state="offline"]')).toBeInTheDocument();
    const tiles = document.querySelectorAll('[data-home-information="saved"]');
    expect(tiles).toHaveLength(4);
    expect(screen.queryByText('No urgent safety issues')).not.toBeInTheDocument();
  });

  it('renders backend-projected node statuses and never fabricates service connectivity', () => {
    expect(homeWorkflowNodeStates([{ key: 'device_fleet', tone: 'ready' }, { key: 'security', tone: 'danger' }])
      .map((node) => node.state)).toEqual(['ready', 'unknown', 'unknown', 'critical']);
  });

  it('uses a native chevron disclosure with an associated content list', () => {
    render(<LiteNextSteps title="Needs your attention" disclosureChevron initialCount={1}
      items={[
        { id: 'one', label: 'First reported item' },
        { id: 'two', label: 'Second reported item' },
      ]} />);
    const toggle = screen.getByRole('button', { name: 'Show all 2 items' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    const controlledList = document.getElementById(toggle.getAttribute('aria-controls'));
    expect(controlledList).toBeInTheDocument();
    expect(toggle.querySelector('.lite-shared-disclosure-chevron')).toBeInTheDocument();
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(within(controlledList).getAllByRole('listitem')).toHaveLength(2);
  });

  it('restores keyboard focus to the last selected section, rather than an unrelated first row', () => {
    render(<NavigationFixture />);
    fireEvent.click(screen.getByRole('button', { name: 'Service health' }));
    expect(screen.getByRole('region', { name: 'Service health' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'All workspace details sections' }));
    expect(screen.getByRole('button', { name: 'Service health' })).toHaveFocus();
  });

  it('keeps backend-unsupported device recovery actions out of the Home UI', () => {
    const navigate = vi.fn();
    const needsAttention = {
      ...status, overall: 'degraded',
      services: status.services.map((item) => item.name === 'Device Fleet'
        ? { ...item, status: 'degraded' } : item),
    };
    render(<HomeScreen status={needsAttention} refresh={vi.fn()} onNavigate={navigate} />);
    fireEvent.click(screen.getByRole('button', { name: /Review Devices/i }));
    expect(navigate).toHaveBeenCalledWith('devices');
    for (const forbidden of ['Restart agent', 'Restart Tailscale', 'Repair device', 'Remove stale device'])
      expect(screen.queryByRole('button', { name: forbidden })).not.toBeInTheDocument();
  });

  it('preserves an unconfirmed review cursor and labels a confirmed backend timestamp', () => {
    const { rerender } = render(<HomeActivityDetails
      activity={{ events: [], active: null, queued: null, completed: null, attention: null }}
      cursor={{ changed_since_review: true }} cursorBusy onMarkReviewed={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'History' }));
    expect(within(screen.getByLabelText('Personal activity review'))
      .getByRole('button', { name: /Saving review/i })).toBeDisabled();
    rerender(<HomeActivityDetails
      activity={{ events: [], active: null, queued: null, completed: null, attention: null }}
      cursor={{ changed_since_review: false, last_reviewed_at: '2026-11-06T09:00:00Z' }}
      onMarkReviewed={vi.fn()} />);
    expect(screen.getByRole('status')).toHaveTextContent('Review confirmed at');
  });
});
