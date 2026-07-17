import { beforeEach, describe, expect, test } from 'vitest';
import {
  reconcileLiteLifecycle,
  reconcileLiteSecurityProgress,
  resetLiteLifecycleDiagnosticsForTest,
  snapshotLiteLifecycleDiagnostics,
  trackLiteLifecycleEventSource,
  trackLiteLifecycleListener,
  trackLiteLifecyclePollTimer,
  updateLiteLifecycleEnvironment,
} from '../lib/liteLifecycleDiagnostics.js';

describe('Lite lifecycle diagnostics', () => {
  beforeEach(() => resetLiteLifecycleDiagnosticsForTest());

  test('tracks cleanup without allowing negative or duplicate resources', () => {
    trackLiteLifecycleEventSource(true);
    trackLiteLifecycleEventSource(false);
    trackLiteLifecycleEventSource(false);
    trackLiteLifecyclePollTimer(true);
    trackLiteLifecyclePollTimer(false);
    trackLiteLifecycleListener('visibility', 1);
    trackLiteLifecycleListener('visibility', -1);
    const snapshot = snapshotLiteLifecycleDiagnostics();
    expect(snapshot.active_event_source_count).toBe(0);
    expect(snapshot.active_poll_timer_count).toBe(0);
    expect(snapshot.visibility_listener_count).toBe(0);
    expect(snapshot.sanitized).toBe(true);
  });

  test('offline saved state blocks writes until backend reconciliation', () => {
    updateLiteLifecycleEnvironment({ visibilityState: 'hidden', onlineState: false });
    expect(snapshotLiteLifecycleDiagnostics().write_actions_blocked).toBe(true);
    reconcileLiteLifecycle({ cachedRunId: 'cached', backendRunId: 'backend', cachedRevision: '1', backendRevision: '2', writeActionsBlocked: false });
    const snapshot = snapshotLiteLifecycleDiagnostics();
    expect(snapshot.write_actions_blocked).toBe(false);
    expect(snapshot.backend_run_id).toBe('backend');
    expect(snapshot.backend_reconciliation_count).toBe(1);
  });


  test('canonical security progress populates reconciliation diagnostics', () => {
    const accepted = reconcileLiteSecurityProgress({
      cachedProgress: { run_id: 'run-old', revision: 'rev-old' },
      backendProgress: { run_id: 'run-new', revision: 'rev-new', status: 'succeeded' },
    });
    const snapshot = snapshotLiteLifecycleDiagnostics();
    expect(accepted).toBe(true);
    expect(snapshot.cached_run_id).toBe('run-old');
    expect(snapshot.cached_revision).toBe('rev-old');
    expect(snapshot.backend_run_id).toBe('run-new');
    expect(snapshot.backend_revision).toBe('rev-new');
    expect(snapshot.backend_reconciliation_count).toBe(1);
    expect(snapshot.last_backend_reconciled_at).not.toBe('');
  });

  test('visibility-only or incomplete progress does not count as reconciliation', () => {
    updateLiteLifecycleEnvironment({ visibilityState: 'visible', onlineState: true });
    expect(reconcileLiteSecurityProgress({ backendProgress: { run_id: 'run-new' } })).toBe(false);
    const snapshot = snapshotLiteLifecycleDiagnostics();
    expect(snapshot.backend_run_id).toBe('');
    expect(snapshot.backend_revision).toBe('');
    expect(snapshot.backend_reconciliation_count).toBe(0);
  });

  test('redacts secret-shaped diagnostic values', () => {
    reconcileLiteLifecycle({ backendRunId: 'token=super-secret-value', backendRevision: 'Bearer hidden-value' });
    const snapshot = snapshotLiteLifecycleDiagnostics();
    expect(JSON.stringify(snapshot)).not.toContain('super-secret-value');
    expect(JSON.stringify(snapshot)).not.toContain('hidden-value');
  });
});
