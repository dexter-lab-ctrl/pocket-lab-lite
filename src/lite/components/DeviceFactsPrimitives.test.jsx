/* @vitest-environment jsdom */
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import {
  CapabilityList,
  FreshnessIndicator,
  ResourceMetric,
  RuntimeServiceList,
  SoftwarePosture,
} from './DeviceFactsPrimitives.jsx';

afterEach(cleanup);

describe('Device Facts shared UI primitives', () => {
  it('renders unavailable resource state without fabricating a numeric value', () => {
    render(<ResourceMetric item={{ label: 'Temperature', status: 'unsupported', value: 'Unsupported', summary: 'No CPU thermal provider.' }} variant="detailed" />);
    expect(screen.getByText('Temperature')).toBeTruthy();
    expect(screen.getAllByText('Unsupported').length).toBeGreaterThan(0);
    expect(screen.queryByText(/0 °C|0%|0 MB/)).toBeNull();
  });

  it('renders a meter only when the caller provides a bounded percentage', () => {
    const { rerender } = render(<ResourceMetric item={{ label: 'Memory', status: 'available', value: '2 GB free / 4 GB', meterPercent: 50 }} variant="detailed" />);
    expect(screen.getByRole('progressbar', { name: 'Memory usage' }).getAttribute('aria-valuenow')).toBe('50');
    rerender(<ResourceMetric item={{ label: 'Temperature', status: 'available', value: '42 °C', meterPercent: null }} variant="detailed" />);
    expect(screen.queryByRole('progressbar')).toBeNull();
  });

  it('renders a semantic resource reading, supporting value, and truthful zero meter', () => {
    render(<ResourceMetric item={{
      label: 'Pocket Lab CPU',
      status: 'healthy',
      statusLabel: 'Healthy',
      primaryValue: '0%',
      secondaryValue: '4 Pocket Lab service processes',
      meterPercent: 0,
      meterTone: 'healthy',
      meterLabel: 'Pocket Lab CPU usage',
    }} variant="detailed" />);
    expect(screen.getByText('Healthy')).toBeTruthy();
    expect(screen.getByText('0%')).toBeTruthy();
    expect(screen.getByText('4 Pocket Lab service processes')).toBeTruthy();
    const meter = screen.getByRole('progressbar', { name: 'Pocket Lab CPU usage' });
    expect(meter.getAttribute('aria-valuenow')).toBe('0');
    expect(meter.className).toContain('is-zero');
  });

  it('renders a temperature meter when a caller provides the bounded display-scale percentage', () => {
    render(<ResourceMetric item={{
      label: 'Temperature',
      status: 'healthy',
      statusLabel: 'Healthy',
      primaryValue: '40 °C',
      secondaryValue: 'Current thermal reading',
      meterPercent: 50,
      meterTone: 'healthy',
      meterLabel: 'Temperature on a 0 to 80 °C display scale',
    }} variant="detailed" />);
    expect(screen.getByText('40 °C')).toBeTruthy();
    expect(screen.getByText('Current thermal reading')).toBeTruthy();
    expect(screen.getByRole('progressbar', { name: 'Temperature on a 0 to 80 °C display scale' }).getAttribute('aria-valuenow')).toBe('50');
  });

  it('renders freshness as text instead of color-only state', () => {
    render(<FreshnessIndicator freshness="stale" observedAt="2026-09-05T12:00:00Z" />);
    expect(screen.getByText(/Stale/)).toBeTruthy();
    expect(screen.getByText(/2026-09-05T12:00:00Z/)).toBeTruthy();
  });

  it('renders unknown future capabilities dynamically', () => {
    render(<CapabilityList capabilities={[{
      id: 'future_accelerator', label: 'Future Accelerator', category: 'custom',
      status: 'verification_pending', reason_code: 'advertised_not_runtime_verified',
      source: 'agent_advertisement', advertised: true,
    }]} />);
    expect(screen.getByText('Future Accelerator')).toBeTruthy();
    expect(screen.getByText('Verification Pending')).toBeTruthy();
  });

  it('renders only reported runtime services and preserves stale semantics', () => {
    const { rerender } = render(<RuntimeServiceList services={[{
      service_id: 'future-sidecar', label: 'Future Sidecar', manager: 'custom', category: 'service',
      state: 'online', freshness: 'stale', reported_at: '2026-09-05T10:00:00Z',
    }]} />);
    expect(screen.getByText('Future Sidecar')).toBeTruthy();
    expect(screen.getByText(/Last reported Online/)).toBeTruthy();
    rerender(<RuntimeServiceList services={[]} />);
    expect(screen.getByText(/have not been reported/i)).toBeTruthy();
    expect(screen.queryByText('Future Sidecar')).toBeNull();
  });

  it('renders agent and supervisor software posture independently', () => {
    render(<SoftwarePosture
      posture={{ status: 'outdated' }}
      facts={{ software: {
        node_agent: { version: '2.4.0', freshness: 'current' },
        supervisor: { version: '2.5.0', freshness: 'current' },
      } }}
    />);
    expect(screen.getByText('Update available')).toBeTruthy();
    expect(screen.getByText(/2.4.0/)).toBeTruthy();
    expect(screen.getByText(/2.5.0/)).toBeTruthy();
  });

  it('uses backend software parts when device facts do not include versions', () => {
    render(<SoftwarePosture
      posture={{
        status: 'unknown',
        summary: 'Software version evidence is available but compatibility is unknown.',
        parts: {
          node_agent: { version: '2.4.0', status: 'unknown', source: 'runtime_heartbeat' },
          supervisor: { version: '2.5.0', status: 'current', source: 'sqlite_supervisor_evidence' },
        },
      }}
    />);
    expect(screen.getByText('Versions reported')).toBeTruthy();
    expect(screen.getByText('Compatibility not classified')).toBeTruthy();
    expect(screen.getByText(/2.4.0/)).toBeTruthy();
    expect(screen.getByText(/2.5.0/)).toBeTruthy();
  });
});
