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
