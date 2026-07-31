import { describe, expect, it } from 'vitest';
import {
  canonicalDevicePresentation,
  deviceCapabilitySummary,
  deviceLinkState,
} from '../lite/LiteUi.jsx';

describe('fleet truth presentation', () => {
  it('keeps a stale joined device offline even with a healthy supervisor', () => {
    const device = {
      role: 'compute',
      status: 'offline',
      connection: 'offline',
      connection_truth: { state: 'offline', source: 'heartbeat_timeout' },
      supervisor_status: 'healthy',
    };
    expect(canonicalDevicePresentation(device)).toEqual({ state: 'offline', label: 'Offline' });
    expect(deviceLinkState(device)).toBe('disconnected');
  });

  it('summarizes verified, pending and unavailable capabilities without counting unadvertised', () => {
    const summary = deviceCapabilitySummary({
      capability_states: [
        { id: 'receive_commands', status: 'ready' },
        { id: 'supervisor_recovery', status: 'ready' },
        { id: 'host_apps', status: 'available' },
        { id: 'remote_access', status: 'not_ready' },
        { id: 'backup_target', status: 'unknown', reason_code: 'capability_not_advertised' },
      ],
    });
    expect(summary).toMatchObject({ verified: 2, pending: 1, unavailable: 1, notAdvertised: 1 });
    expect(summary.label).toBe('2 verified · 1 pending · 1 unavailable');
  });
});
