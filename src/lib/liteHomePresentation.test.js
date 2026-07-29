import { describe, expect, it } from 'vitest';
import {
  buildLiteHomeOverview,
  homeServicePresentation,
  homeStatusTone,
} from './liteHomePresentation.js';

describe('Lite Home presentation model', () => {
  it('replaces technical service names with user-facing language', () => {
    expect(homeServicePresentation({ name: 'Command Bus', status: 'healthy' })).toMatchObject({
      label: 'Task delivery',
      statusLabel: 'Ready',
      summary: 'Background tasks can be delivered safely.',
    });
    expect(homeServicePresentation({ name: 'Worker Execution', status: 'degraded' }).label).toBe('Background operations');
    expect(homeServicePresentation({ name: 'Policy & Compliance', status: 'healthy' }).label).toBe('Protection rules');
  });

  it('uses saved state truthfully without enabling browser authority', () => {
    const overview = buildLiteHomeOverview({ overall: 'healthy', services: [] }, {
      savedStateOnly: true,
      backendReachable: false,
    });
    expect(overview.heroTitle).toContain('saved information');
    expect(overview.nextAction.screen).toBe('home');
    expect(overview.nextAction.detail).toContain('Actions stay protected');
  });

  it('prioritizes safety and remote access using bounded current summaries', () => {
    const safety = buildLiteHomeOverview({
      overall: 'degraded',
      summary: { apps_available: 1, devices_known: 2, security_findings: 3, remote_access_ready: true },
      services: [{ name: 'Security', status: 'degraded' }],
    });
    expect(safety.nextAction).toMatchObject({ screen: 'security', label: 'Review Safety' });
    expect(safety.stats.find((item) => item.key === 'safety')?.value).toBe(3);

    const access = buildLiteHomeOverview({
      overall: 'healthy',
      summary: { apps_available: 1, devices_known: 2, security_findings: 0, remote_access_ready: false },
      services: [],
    });
    expect(access.nextAction.screen).toBe('devices');
    expect(access.nextAction.title).toContain('remote access');
  });

  it('normalizes service tones and current resource thresholds deterministically', () => {
    expect(homeStatusTone('healthy')).toBe('ready');
    expect(homeStatusTone('degraded')).toBe('review');
    expect(homeStatusTone('failed')).toBe('danger');

    const overview = buildLiteHomeOverview({
      telemetry: { cpu_usage_percent: 94, cpu_temp_c: 60, free_space_mb: 400, memory_usage_mb: 256 },
    });

    expect(overview.resources.map((item) => item.key)).toEqual([
      'device-health',
      'storage',
      'database',
      'activity',
    ]);
    expect(overview.resources.find((item) => item.key === 'device-health')).toMatchObject({
      value: 'Not available',
      tone: 'neutral',
    });
    expect(overview.resources.find((item) => item.key === 'storage')).toMatchObject({
      value: '400 MB',
      tone: 'danger',
    });
  });
  it('uses per-card semantic fallbacks without hiding valid telemetry', () => {
    const overview = buildLiteHomeOverview({
      summary: {
        device_health_attention: 0,
        device_health_attention_current: true,
        device_health_summary: { by_status: { healthy: 1 } },
      },
      telemetry: { free_space_mb: 135569, cpu_usage_percent: 0, cpu_temp_c: 35.2, memory_usage_mb: 4054 },
      system_current_state: {
        activity_summary: { status: 'unknown', summary: 'Activity state is not available.' },
      },
    });

    expect(overview.resources.find((item) => item.key === 'device-health')).toMatchObject({ value: 'Healthy', tone: 'ready' });
    expect(overview.resources.find((item) => item.key === 'storage')).toMatchObject({ value: '135569 MB', tone: 'ready' });
    expect(overview.resources.find((item) => item.key === 'database')).toMatchObject({ value: 'Not available' });
    expect(overview.resources.find((item) => item.key === 'activity')).toMatchObject({ value: 'Not available' });
  });

});
