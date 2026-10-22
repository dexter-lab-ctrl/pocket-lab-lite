import { describe, expect, it } from 'vitest';
import { selectHomeActivityEvidence, formatActivityCount } from './homeActivityEvidence.js';

describe('Home activity projection', () => {
  it('does not invent unavailable history or represent missing counts as zero', () => {
    expect(selectHomeActivityEvidence({ history_available: false })).toBeNull();
    const view = selectHomeActivityEvidence({ history_available: true, counts_available: false });
    expect(view.active).toBeNull();
    expect(formatActivityCount(view.active)).toBe('Not available');
  });
  it('preserves exact counts beyond 9,999', () => {
    const view = selectHomeActivityEvidence({ history_available: true, counts_available: true,
      active_operations: 472, queued_operations: 52, recent_completed: 41, attention_required: 12054 });
    expect(view.attention).toBe(12054);
    expect(formatActivityCount(view.attention)).toBe(new Intl.NumberFormat().format(12054));
  });
  it.each([0, 1, 472, 9999, 10000, 99999, 1000000])('keeps valid count %s exact', (count) => {
    const view = selectHomeActivityEvidence({ history_available: true, counts_available: true,
      attention_required: count });
    expect(view.attention).toBe(count);
    expect(formatActivityCount(view.attention)).toBe(new Intl.NumberFormat().format(count));
  });
  it.each([null, undefined, -1, 1.5, '10000', 'not-a-count'])('does not turn invalid count %s into zero', (count) => {
    const view = selectHomeActivityEvidence({ history_available: true, counts_available: true,
      attention_required: count });
    expect(view.attention).toBeNull();
    expect(formatActivityCount(count)).toBe('Not available');
  });
  it('does not expose exact source counts when the projection is unavailable', () => {
    const view = selectHomeActivityEvidence({ history_available: true, counts_available: false,
      active_operations: 1000000, attention_required: 9999 });
    expect(view.active).toBeNull();
    expect(view.attention).toBeNull();
  });
  it('allow-lists labels, filters unrelated domains, and does not claim stale work is running', () => {
    const view = selectHomeActivityEvidence({ history_available: true, recent_events: [
      { domain: 'devices', status: 'running', is_fresh_running: false, occurred_at_epoch_ms: 1700000000000,
        label: 'internal.operation', token: 'never-display' },
      { domain: 'apps', status: 'succeeded', occurred_at_epoch_ms: 1700000000001,
        label: 'Media backup repair' },
      { domain: 'unknown', status: 'queued', occurred_at_epoch_ms: 1700000000002 },
    ] });
    expect(view.events).toHaveLength(2);
    expect(view.events[0].status).toBe('stale');
    expect(view.events[0].label).toBe('Device command');
    expect(view.events[1].label).toBe('Media backup repair');
    expect(JSON.stringify(view.events)).not.toContain('never-display');
    expect(JSON.stringify(view.events)).not.toContain('internal.operation');
  });
  it('keeps explicit recovered status out of running and attention lists', () => {
    const view = selectHomeActivityEvidence({ history_available: true, recent_events: [
      { domain: 'apps', status: 'recovered', occurred_at_epoch_ms: 1700000000000, needs_attention: false },
    ] });
    expect(view.events[0].statusLabel).toBe('Recovered');
    expect(view.events[0].needsAttention).toBe(false);
  });
  it('retains different bounded windows reported by the backend', () => {
    const view = selectHomeActivityEvidence({
      history_available: true, running_window_minutes: 45, history_window_days: 5,
    });
    expect(view.runningWindowMinutes).toBe(45);
    expect(view.historyWindowDays).toBe(5);
    const invalid = selectHomeActivityEvidence({
      history_available: true, running_window_minutes: '45', history_window_days: -7,
    });
    expect(invalid.runningWindowMinutes).toBeNull();
    expect(invalid.historyWindowDays).toBeNull();
  });
});
