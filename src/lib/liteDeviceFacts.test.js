import { describe, expect, it } from 'vitest';
import {
  finiteDeviceFactNumber,
  normalizeDeviceFacts,
  resourceFactAvailabilityLabel,
  resourceFactValue,
} from './liteDeviceFacts.js';

describe('Lite shared device facts', () => {
  it('preserves a valid zero but never turns null into zero', () => {
    expect(finiteDeviceFactNumber(0)).toBe(0);
    expect(finiteDeviceFactNumber(null)).toBeNull();
    expect(finiteDeviceFactNumber(undefined)).toBeNull();
    expect(finiteDeviceFactNumber('')).toBeNull();
  });

  it('normalizes canonical resource observations once for Home and Devices', () => {
    const facts = normalizeDeviceFacts({
      schema_version: 1,
      resources: {
        memory: {
          status: 'available', collection_status: 'available', freshness: 'current',
          value: { total_mb: 4096, free_mb: 2048, used_mb: 2048 },
          source: 'server_central_telemetry', observed_at: '2026-09-05T12:00:00Z',
        },
        temperature: {
          status: 'unsupported', collection_status: 'unsupported', freshness: 'current',
          value: null, source: 'sysfs_thermal', reason_code: 'no_semantic_cpu_sensor',
        },
      },
    });
    expect(resourceFactValue(facts, 'memory', 'free_mb')).toBe(2048);
    expect(resourceFactValue(facts, 'temperature', 'celsius')).toBeNull();
    expect(resourceFactAvailabilityLabel(facts.resources.temperature)).toBe('Unsupported');
  });

  it('adapts mixed-version legacy telemetry through the same normalizer', () => {
    const facts = normalizeDeviceFacts({}, {
      telemetry: {
        sampled_at: '2026-09-05T12:00:00Z',
        cpu_usage_percent: 0,
        memory_total_mb: 2048,
        memory_free_mb: 1024,
      },
    });
    expect(resourceFactValue(facts, 'cpu_usage', 'usage_percent')).toBe(0);
    expect(resourceFactValue(facts, 'memory', 'free_mb')).toBe(1024);
  });

  it('does not fabricate resource values from unavailable observations', () => {
    const facts = normalizeDeviceFacts({
      resources: {
        storage: {
          status: 'permission_denied', collection_status: 'permission_denied', freshness: 'current',
          reason_code: 'statvfs_permission_denied', value: null,
        },
      },
    });
    expect(resourceFactValue(facts, 'storage', 'free_mb')).toBeNull();
    expect(resourceFactAvailabilityLabel(facts.resources.storage)).toBe('Permission denied');
  });
});

describe('Lite Device Facts future-safe evidence normalization', () => {
  it('keeps stale, unsupported, permission-denied and transient states distinct', async () => {
    const { normalizeDeviceFacts, resourceFactAvailabilityLabel } = await import('./liteDeviceFacts.js');
    const facts = normalizeDeviceFacts({ resources: {
      memory: { status: 'stale', collection_status: 'available', freshness: 'stale', observed_at: '2026-09-05T10:00:00Z', value: { total_mb: 100, free_mb: 20, used_mb: 80 } },
      storage: { status: 'permission_denied', collection_status: 'permission_denied', freshness: 'current', value: null },
      temperature: { status: 'unsupported', collection_status: 'unsupported', freshness: 'current', value: null },
      uptime: { status: 'transient_failure', collection_status: 'transient_failure', freshness: 'current', value: null },
    } });
    expect(resourceFactAvailabilityLabel(facts.resources.memory)).toBe('Stale');
    expect(resourceFactAvailabilityLabel(facts.resources.storage)).toBe('Permission denied');
    expect(resourceFactAvailabilityLabel(facts.resources.temperature)).toBe('Unsupported');
    expect(resourceFactAvailabilityLabel(facts.resources.uptime)).toBe('Temporarily unavailable');
  });

  it('normalizes future capabilities without allowing verified_at on pending evidence', async () => {
    const { normalizeCapabilityEvidence } = await import('./liteDeviceFacts.js');
    const rows = normalizeCapabilityEvidence([{
      id: 'future_accelerator', label: 'Future Accelerator', category: 'custom',
      status: 'verification_pending', verified_at: '2026-09-05T12:00:00Z',
      source: 'agent_advertisement', reason_code: 'advertised_not_runtime_verified', advertised: true,
    }]);
    expect(rows).toHaveLength(1);
    expect(rows[0].id).toBe('future_accelerator');
    expect(rows[0].status).toBe('verification_pending');
    expect(rows[0].verified_at).toBeNull();
  });

  it('drops secret-like runtime service metadata and de-duplicates service ids', async () => {
    const { normalizeRuntimeServices } = await import('./liteDeviceFacts.js');
    const rows = normalizeRuntimeServices([
      { service_id: 'future-sidecar', label: 'Future Sidecar', state: 'online', source: 'prepared_service_evidence' },
      { service_id: 'future-sidecar', label: 'Duplicate', state: 'offline' },
      { service_id: 'safe-service', label: '/root/private/token', state: 'online', source: 'Bearer secret' },
    ]);
    expect(rows.map((item) => item.service_id)).toEqual(['future-sidecar', 'safe-service']);
    expect(rows[1].label).not.toMatch(/root|token/i);
    expect(rows[1].source).not.toMatch(/bearer|secret/i);
  });

  it('renders software posture vocabulary consistently', async () => {
    const { softwarePostureLabel } = await import('./liteDeviceFacts.js');
    expect(softwarePostureLabel('current')).toBe('Current');
    expect(softwarePostureLabel('outdated')).toBe('Update available');
    expect(softwarePostureLabel('incompatible')).toBe('Incompatible');
    expect(softwarePostureLabel('stale')).toBe('Stale');
    expect(softwarePostureLabel('verification_pending')).toBe('Verification pending');
  });
});
