import { describe, expect, it } from 'vitest';
import { deviceLibraryEntry, deviceLibrarySummary, filterDeviceLibrary } from './deviceLibraryPresentation.js';

const view = (device, saved = false, state = 'online', linkState = 'joined') =>
  deviceLibraryEntry(device, { saved, presentation: { state }, linkState });

describe('Azure Horizon Devices inventory presentation — AUTHORED NOT EXECUTED', () => {
  it('counts only confirmed projected connections and never infers success from PM2', () => {
    const entries = [
      view({ id: 'server', role: 'server_host', name: 'Server', protected_server_host: true }),
      view({ id: 'phone', role: 'compute', name: 'Phone', connection_truth: { state: 'online' } }),
      view({ id: 'stopped', name: 'Stopped', role: 'compute', agent: { status: 'online' },
        connection_truth: { state: 'offline' } }, false, 'offline', 'offline'),
    ];
    expect(deviceLibrarySummary(entries, { confirmed: true })).toMatchObject({
      total: 3, connected: 1, attention: 1,
    });
    expect(entries[2].connection.kind).not.toBe('connected');
    expect(entries[0].connection.kind).toBe('server');
  });

  it('marks stale and saved connectivity unconfirmed; does not fabricate zero attention', () => {
    const device = { id: 'phone', name: 'Phone', connection_truth: { state: 'online' },
      staleness_state: 'stale' };
    const entry = view(device, false, 'online', 'joined');
    expect(entry.connection.kind).toBe('stale');
    const saved = view({ id: 'phone', name: 'Phone' }, true, 'online', 'joined');
    expect(saved.connection.kind).toBe('stale');
    expect(deviceLibrarySummary([saved], { confirmed: false })).toEqual({
      total: null, connected: null, attention: null,
    });
  });

  it('prioritizes identity protection, explicit repair and reported health attention', () => {
    const blocked = view({ id: 'a', name: 'Blocked phone', identity: { status: 'join_blocked' } }, false, 'online', 'joined');
    expect(blocked.connection.kind).toBe('blocked');
    const repairing = view({ id: 'b', name: 'Recovering phone' }, false, 'repairing', 'repairing');
    expect(repairing.connection.kind).toBe('repairing');
    const health = view({ id: 'c', name: 'Health attention', proactive_health: {
      status: 'needs_attention', attention_current: true, attention_count: 1,
    } });
    expect(health.needsAttention).toBe(true);
  });

  it('filters without altering original objects or treating unknown as connected', () => {
    const entries = [
      view({ id: 'a', name: 'Kitchen tablet', role: 'compute', connection_truth: { state: 'online' } }),
      view({ id: 'b', name: 'Storage PC', role: 'storage' }, false, 'unknown', 'unknown'),
      view({ id: 'c', name: 'Other phone' }, false, 'offline', 'offline'),
    ];
    expect(filterDeviceLibrary(entries, { filter: 'all', query: 'storage' })).toEqual([entries[1].device]);
    expect(filterDeviceLibrary(entries, { filter: 'connected' })).toEqual([entries[0].device]);
    expect(filterDeviceLibrary(entries, { filter: 'attention' })).toEqual([entries[1].device, entries[2].device]);
  });

  it('handles an empty or missing fleet without inventing details', () => {
    expect(deviceLibrarySummary([], { confirmed: false }).total).toBeNull();
    expect(filterDeviceLibrary(null, { filter: 'connected' })).toEqual([]);
    expect(filterDeviceLibrary([], { query: 'anything' })).toEqual([]);
  });
});
