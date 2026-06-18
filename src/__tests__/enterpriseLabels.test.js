import { describe, expect, test } from 'vitest';
import { enterpriseDisplayText, enterpriseOperationLabel, enterpriseSubjectLabel, hasEnterpriseUiLeak } from '../lib/enterpriseLabels.js';
import { friendlyEvent } from '../lib/pocketLabEvents.js';

describe('enterprise-facing labels', () => {
  test('operation identifiers map to enterprise labels', () => {
    expect(enterpriseOperationLabel('git_sync')).toBe('Update Environment');
    expect(enterpriseOperationLabel('deploy_blueprint')).toBe('Install Service');
    expect(enterpriseOperationLabel('fleet_join')).toBe('Add Device to Fleet');
    expect(enterpriseOperationLabel('rotate_secret')).toBe('Rotate Credential');
  });

  test('display text sanitizes backend endpoints and event subjects', () => {
    const raw = 'git_sync via /ws/events and /api/events/recent on pocketlab.events.operation.started';
    const text = enterpriseDisplayText(raw);
    expect(text).toContain('Update Environment');
    expect(text).toContain('Live Activity Stream');
    expect(text).toContain('Recent Activity');
    expect(text).toContain('Operation Activity');
    expect(hasEnterpriseUiLeak(text)).toBe(false);
  });

  test('subject labels hide backend subject names', () => {
    expect(enterpriseSubjectLabel('pocketlab.events.fleet.node_seen')).toBe('Device Fleet Activity');
    expect(enterpriseSubjectLabel('pocketlab.audit.approval.created')).toBe('Audit Activity');
  });

  test('friendly event output does not expose raw operation ids in enterprise-facing mode', () => {
    const event = {
      subject: 'pocketlab.events.operation.succeeded',
      type: 'operation.succeeded',
      data: { operation: 'deploy_blueprint', job_id: 'job-1', status: 'succeeded' },
    };
    const label = friendlyEvent(event, false);
    const rendered = `${label.title} ${label.detail}`;
    expect(rendered).toContain('Install Service');
    expect(rendered).not.toMatch(/deploy_blueprint|pocketlab\.events|\/api\/events|\/ws\/events/i);
  });
});
