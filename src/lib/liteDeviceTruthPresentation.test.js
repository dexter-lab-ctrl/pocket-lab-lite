import { describe, expect, it } from 'vitest';
import {
  canonicalDevicePresentation,
  deviceCapabilitySummary,
  deviceCommandDeliveryLabel,
  deviceRestartAssessment,
  deviceRuntimeServices,
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


  it('supports canonical backend capability vocabulary', () => {
    const summary = deviceCapabilitySummary({
      capability_states: [
        { id: 'host_apps', status: 'verified' },
        { id: 'receive_commands', status: 'verified' },
        { id: 'supervisor_recovery', status: 'verification_pending' },
        { id: 'backup_target', status: 'not_advertised', reason_code: 'capability_not_advertised' },
      ],
    });
    expect(summary).toMatchObject({ verified: 2, pending: 1, unavailable: 0, notAdvertised: 1 });
    expect(summary.label).toBe('2 verified · 1 pending');
  });

  it('falls back to normalized view-model capabilities', () => {
    const summary = deviceCapabilitySummary({
      capabilities: [
        { id: 'host_apps', status: 'verified' },
        { id: 'supervisor_recovery', status: 'verification_pending' },
      ],
    });
    expect(summary.label).toBe('1 verified · 1 pending');
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


describe('frontend guarded-recovery contract convergence', () => {
  const device = {
    restart_agent_assessment: {
      allowed: false,
      reason_code: 'agent_already_running',
      summary: 'The device agent is already reporting as running.',
      command_deliverable: true,
    },
    runtime_services: [
      { service_id: 'node_agent', state: 'online', freshness: 'fresh' },
      { service_id: 'agent_supervisor', state: 'healthy', freshness: 'fresh' },
    ],
    dependencies: { command_delivery_status: 'unknown' },
  };

  it('uses canonical runtime services and recovery assessment', () => {
    expect(deviceRuntimeServices(device)).toHaveLength(2);
    expect(deviceRestartAssessment(device)?.reason_code).toBe('agent_already_running');
  });

  it('prefers backend-owned command deliverability over legacy dependency state', () => {
    expect(deviceCommandDeliveryLabel(device)).toBe('Deliverable');
    expect(deviceCommandDeliveryLabel({
      restart_agent_assessment: { command_deliverable: false },
      dependencies: { command_delivery_status: 'deliverable' },
    })).toBe('Temporarily unreachable');
  });
});
