// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../hooks/useLiteQuery.js', () => ({ useLiteQuery: vi.fn() }));

import { useLiteQuery } from '../hooks/useLiteQuery.js';
import SystemHealthOwnerControls from './components/SystemHealthOwnerControls.jsx';
import LiteSystemHealth, { SYSTEM_HEALTH_SUMMARY_QUERY_OPTIONS, SystemHealthIncidentCard, infrastructureValue, systemHealthPresentation } from './LiteSystemHealth.jsx';

afterEach(() => {
  cleanup();
  useLiteQuery.mockReset();
});

describe('System Health authoritative presentation', () => {
  it('never labels missing data healthy', () => {
    expect(systemHealthPresentation(undefined).state).toBe('unknown');
  });
  it('renders stale or offline data as saved', () => {
    expect(systemHealthPresentation({ status: 'healthy', freshness: 'stale' }).state).toBe('saved');
    expect(systemHealthPresentation({ status: 'healthy', freshness: 'current' }, true).state).toBe('saved');
  });
  it('keeps unavailable evidence distinct from saved information', () => {
    const result = systemHealthPresentation({ status: 'unknown', freshness: 'unavailable', summary: 'Health evidence is unavailable.' });
    expect(result.state).toBe('unknown');
    expect(result.title).toMatch(/needs confirmation/i);
  });
  it('uses observed unknown counts to avoid false green', () => {
    expect(systemHealthPresentation({ status: 'healthy', freshness: 'current', unknown_services: 2 }).state).toBe('unknown');
  });
  it('reports attention only when backend indicates a real problem', () => {
    expect(systemHealthPresentation({ status: 'attention', freshness: 'current', active_problems: 1 }).state).toBe('attention');
  });
  it('shows verified observations without claiming repair succeeded', () => {
    const result = systemHealthPresentation({ status: 'healthy', freshness: 'current', unknown_services: 0 });
    expect(result.state).toBe('ready');
    expect(result.title).toMatch(/observed/i);
  });

  it('revalidates a saved summary on mount and transitions saved to fresh evidence', () => {
    expect(SYSTEM_HEALTH_SUMMARY_QUERY_OPTIONS.refetchOnMount).toBe('always');

    const currentSummary = {
      status: 'attention', freshness: 'current', current_problems: 1,
      saved_problems: 0, healthy_services: 7, unknown_services: 0,
      summary: 'One current observation needs review.',
    };
    let savedOnly = true;
    useLiteQuery.mockImplementation(({ path }) => {
      if (path === '/api/lite/system-health/summary') {
        return {
          data: currentSummary,
          savedStateOnly: savedOnly,
          backendReachable: !savedOnly,
          refreshing: false,
          refresh: vi.fn(),
          error: null,
          cacheStatus: null,
        };
      }
      return {
        data: { items: [] }, loading: false, error: null,
        refreshing: false, refresh: vi.fn(), savedStateOnly: false,
        backendReachable: true, cacheStatus: null,
      };
    });

    const view = render(<LiteSystemHealth />);
    expect(document.querySelector('[data-health-overview="saved"]')).toBeTruthy();

    savedOnly = false;
    view.rerender(<LiteSystemHealth />);
    expect(document.querySelector('[data-health-overview="attention"]')).toBeTruthy();
  });

  it('transitions fresh evidence back to saved without presenting it as current', () => {
    const fresh = systemHealthPresentation({ status: 'attention', freshness: 'current', current_problems: 1 });
    const saved = systemHealthPresentation({ status: 'attention', freshness: 'current', current_problems: 1 }, true);
    expect(fresh.state).toBe('attention');
    expect(saved.state).toBe('saved');
  });

  it('exposes governed recovery only for a backend-eligible current incident', () => {
    const onRecover = vi.fn();
    const { rerender } = render(<SystemHealthIncidentCard
      incident={{ incident_id: 'health-current', source: 'nats', target_id: 'jetstream',
        generation: 1, evidence_freshness: 'current', concern_state: 'current_concern',
        repair_available: true, summary: 'Command connection needs attention.' }}
      onDiagnose={vi.fn()} onRecover={onRecover} />);
    fireEvent.click(document.querySelector('button:last-of-type'));
    expect(onRecover).toHaveBeenCalledTimes(1);
    rerender(<SystemHealthIncidentCard
      incident={{ incident_id: 'health-history', source: 'agent', target_id: 'retired',
        current_monitoring: false, membership_state: 'removed', concern_state: 'historical_record',
        repair_available: false }}
      onDiagnose={vi.fn()} onRecover={onRecover} />);
    expect(document.body.textContent).not.toMatch(/Review recovery/);
  });
});


describe('prepared infrastructure presentation', () => {
  it('does not promote stale or missing counts to current readiness', () => {
    expect(infrastructureValue({ status: 'healthy', freshness: 'stale' })).toMatch(/^Saved/);
    expect(infrastructureValue({ status: 'unknown', freshness: 'unknown' })).toBe('Not confirmed');
    expect(infrastructureValue({ count: 0, freshness: 'current' })).toBe('0');
    expect(infrastructureValue({ count: 0, freshness: 'current' }, true)).toBe('Saved · 0');
  });
});


describe('System Health owner controls', () => {
  const policy = { owner_controls_available: true, activation_policy: { preferences: { revision: 1, recovery_mode: 'monitor', resource_mode: 'balanced' } } };
  it('hides owner controls without backend eligibility or on saved state', () => {
    useLiteQuery.mockReturnValue({});
    const view = render(<SystemHealthOwnerControls section="policies" policy={{...policy, owner_controls_available:false}} readOnly={false} />);
    expect(view.queryByRole('region', { name: 'Owner controls' })).toBeNull();
    view.rerender(<SystemHealthOwnerControls section="policies" policy={policy} readOnly={true} />);
    expect(view.queryByRole('region', { name: 'Owner controls' })).toBeNull();
  });
  it('requires a separate confirmation and allows cancelling a preference review', () => {
    useLiteQuery.mockReturnValue({});
    const view = render(<SystemHealthOwnerControls section="policies" policy={policy} readOnly={false} />);
    expect(view.queryByRole('button', { name: 'Confirm', exact:true })).toBeNull();
    fireEvent.click(view.getByRole('button', { name: 'Prefer assisted recovery' }));
    expect(view.getByRole('button', { name: 'Confirm', exact:true })).toBeTruthy();
    fireEvent.click(view.getByRole('button', { name: 'Cancel', exact:true }));
    expect(view.queryByRole('button', { name: 'Confirm', exact:true })).toBeNull();
  });
});
