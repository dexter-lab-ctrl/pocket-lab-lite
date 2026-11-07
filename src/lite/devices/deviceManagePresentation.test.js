// AUTHORED — NOT EXECUTED — UNVALIDATED
import { describe, expect, it } from 'vitest';
import {
  deviceManageSections, groupDeviceServices, deviceEventDate, deviceEventIcon,
} from './deviceManagePresentation.js';

describe('Devices native Manage presentation contract', () => {
  it('preserves protected server host boundaries', () => {
    const groups = deviceManageSections(true);
    const ids = groups.flatMap((g) => g.sections.map((section) => section.id));
    expect(ids).toEqual(['overview', 'connection', 'health', 'services', 'history', 'technical']);
    expect(ids).not.toContain('roles');
    expect(ids).not.toContain('backup');
  });

  it('exposes peer-only management without hiding common sections', () => {
    const ids = deviceManageSections(false).flatMap((g) => g.sections.map((s) => s.id));
    expect(ids).toEqual(['overview', 'connection', 'health', 'roles', 'services', 'backup', 'history', 'technical']);
  });

  it('groups every reported service without changing operational truth or order within its group', () => {
    const services = [
      { service_id: 'pocket-api', state: 'online', freshness: 'stale' },
      { service_id: 'tailscale', state: 'offline', freshness: 'current' },
      { service_id: 'pocketlab-agent-supervisor', state: 'online', freshness: 'current' },
      { service_id: 'pocketlab-app-photoprism', state: 'unknown' },
      { service_id: 'experimental-service', state: 'unavailable' },
    ];
    const grouped = groupDeviceServices(services);
    expect(grouped.map((g) => g.label)).toEqual(['Pocket Lab core', 'Connectivity', 'Recovery', 'Hosted apps', 'Other services']);
    expect(grouped.flatMap((g) => g.services)).toHaveLength(services.length);
    expect(grouped.find((g) => g.label === 'Pocket Lab core').services[0].freshness).toBe('stale');
    expect(grouped.find((g) => g.label === 'Connectivity').services[0].state).toBe('offline');
  });

  it('does not invent missing timestamps or event states', () => {
    expect(deviceEventDate('')).toBe('');
    expect(deviceEventDate('invalid')).toBe('');
    expect(deviceEventIcon('device_online')).toBe('online');
    expect(deviceEventIcon('device_offline')).toBe('alert');
    expect(deviceEventIcon('supervisor_recovery')).toBe('recover');
    expect(deviceEventIcon('unknown_event')).toBe('activity');
  });
});
