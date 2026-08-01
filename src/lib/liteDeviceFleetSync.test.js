import { describe, expect, it } from 'vitest';
import { selectLiteDeviceCard } from './liteViewModels.js';

describe('fleet device presentation parity', () => {
  it('uses canonical nested profile values and top-level compatibility fallbacks', () => {
    const nested = selectLiteDeviceCard({
      id: 'server', status: 'online', role: 'server_host',
      system_profile: { technical_model: 'SM-S911B', os_name: 'Android', os_version: '16', architecture_raw: 'arm64-v8a', architecture_family: 'arm64', runtime_type: 'termux' },
    });
    expect(nested.system_profile.technical_model).toBe('SM-S911B');
    expect(nested.system_profile.android_abi).toBe('arm64-v8a');

    const legacy = selectLiteDeviceCard({ id: 'legacy', status: 'online', architecture: 'arm64-v8a', architecture_family: 'arm64', runtime_type: 'termux' });
    expect(legacy.system_profile.android_abi).toBe('arm64-v8a');
    expect(legacy.system_profile.runtime_type).toBe('termux');
  });

  it('keeps proactive health as the authoritative badge state', () => {
    const card = selectLiteDeviceCard({ id: 'phone', status: 'online', proactive_health: { status: 'needs_attention', severity: 'medium', summary: 'Available memory is limited.', attention_count: 1 } });
    expect(card.health_status).toBe('needs_attention');
    expect(card.attention_count).toBe(1);
  });
});


it('preserves canonical capability and guarded-recovery fields in the device view model', () => {
  const card = selectLiteDeviceCard({
    id: 'phone-contract',
    status: 'online',
    capability_states: [
      { id: 'receive_commands', label: 'Receives commands', status: 'verified' },
      { id: 'host_apps', label: 'Can host apps', status: 'verification_pending' },
    ],
    restart_agent_assessment: {
      allowed: false,
      reason_code: 'agent_already_running',
      summary: 'The device agent is already reporting as running.',
      command_deliverable: true,
      supervisor_fresh: true,
      agent_state: 'online',
    },
    runtime_services: [
      { service_id: 'node_agent', label: 'Device agent', manager: 'pm2', state: 'online', freshness: 'fresh' },
      { service_id: 'agent_supervisor', label: 'Recovery supervisor', manager: 'pm2', state: 'healthy', freshness: 'fresh' },
    ],
  });

  expect(card.capability_states).toHaveLength(2);
  expect(card.capability_states[0].status).toBe('verified');
  expect(card.restart_agent_assessment.command_deliverable).toBe(true);
  expect(card.runtime_services.map((item) => item.service_id)).toEqual(['node_agent', 'agent_supervisor']);
});
