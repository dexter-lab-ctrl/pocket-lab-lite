import { describe, expect, it } from 'vitest';
import {
  canonicalDevicePresentation,
  deviceCapabilitySummary,
  canRestartDeviceAgent,
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

describe('guarded recovery and capability presentation', () => {
  it('does not allow restart for an offline device even with stale supervisor evidence', () => {
    expect(canRestartDeviceAgent({
      id: 'phone-offline',
      role: 'app_host',
      connection: 'offline',
      agent_process_status: 'unknown',
      supervisor_status_freshness: 'saved',
      restart_agent_assessment: { allowed: false, reason_code: 'device_unreachable' },
    })).toBe(false);
  });

  it('allows restart only when the backend assessment explicitly allows it', () => {
    expect(canRestartDeviceAgent({
      id: 'phone-online',
      role: 'app_host',
      connection: 'online',
      restart_agent_assessment: { allowed: true, reason_code: 'allowed' },
    })).toBe(true);
  });
});
