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
