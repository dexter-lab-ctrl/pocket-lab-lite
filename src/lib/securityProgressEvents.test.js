import { describe, expect, it } from 'vitest';
import { acceptSecurityProgressEvent } from './securityProgressEvents.js';

const event = (overrides = {}) => ({
  event_id: 10,
  run_id: 'security-one',
  status: 'running',
  percent: 40,
  updated_at_epoch_ms: 1000,
  active_scan: true,
  ...overrides,
});

describe('acceptSecurityProgressEvent', () => {
  it('accepts replayed missed events in order', () => {
    const first = acceptSecurityProgressEvent(null, event({ event_id: 11, replayed: true }));
    const second = acceptSecurityProgressEvent(first.value, event({ event_id: 12, percent: 60, replayed: true }));
    expect(first.accepted).toBe(true);
    expect(second.accepted).toBe(true);
    expect(second.value.percent).toBe(60);
  });

  it('rejects duplicate and lower event ids', () => {
    expect(acceptSecurityProgressEvent(event(), event()).reason).toBe('duplicate_event_id');
    expect(acceptSecurityProgressEvent(event(), event({ event_id: 9 })).reason).toBe('stale_event_id');
  });

  it('never regresses percent for one run', () => {
    const result = acceptSecurityProgressEvent(event({ percent: 70 }), event({ event_id: 11, percent: 20 }));
    expect(result.accepted).toBe(true);
    expect(result.value.percent).toBe(70);
  });

  it('rejects an older wrong-run event', () => {
    const result = acceptSecurityProgressEvent(
      event({ event_id: 20, run_id: 'security-new', updated_at_epoch_ms: 2000 }),
      event({ event_id: 19, run_id: 'security-old', updated_at_epoch_ms: 1000 }),
    );
    expect(result.reason).toBe('stale_event_id');
  });

  it('keeps terminal state above stale active state', () => {
    const done = event({ event_id: 20, status: 'succeeded', percent: 100, active_scan: false });
    const stale = event({ event_id: 21, status: 'running', percent: 90 });
    expect(acceptSecurityProgressEvent(done, stale).reason).toBe('terminal_outranks_active');
  });

  it('deduplicates completion transitions', () => {
    const done = event({ event_id: 20, status: 'succeeded', percent: 100, active_scan: false });
    const duplicate = event({ event_id: 21, status: 'completed', percent: 100, active_scan: false });
    const result = acceptSecurityProgressEvent(done, duplicate);
    expect(result.accepted).toBe(false);
    expect(result.duplicateCompletion).toBe(true);
  });

  it('lets persisted replay outrank cached wrong-run state', () => {
    const result = acceptSecurityProgressEvent(
      event({ event_id: 0, run_id: 'cached-run', updated_at_epoch_ms: 9000, source: 'saved_snapshot' }),
      event({ event_id: 21, run_id: 'replayed-run', updated_at_epoch_ms: 2000, status: 'succeeded', active_scan: false, replayed: true }),
    );
    expect(result.accepted).toBe(true);
    expect(result.value.run_id).toBe('replayed-run');
  });

  it('accepts a newer authoritative run', () => {
    const result = acceptSecurityProgressEvent(
      event({ event_id: 20, run_id: 'security-old', updated_at_epoch_ms: 1000 }),
      event({ event_id: 21, run_id: 'security-new', updated_at_epoch_ms: 2000, percent: 5 }),
    );
    expect(result.accepted).toBe(true);
    expect(result.value.run_id).toBe('security-new');
  });
});
