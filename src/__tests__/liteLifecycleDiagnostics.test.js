import { beforeEach, describe, expect, test } from 'vitest';
import {
  reconcileLiteLifecycle,
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

  test('redacts secret-shaped diagnostic values', () => {
    reconcileLiteLifecycle({ backendRunId: 'token=super-secret-value', backendRevision: 'Bearer hidden-value' });
    const snapshot = snapshotLiteLifecycleDiagnostics();
    expect(JSON.stringify(snapshot)).not.toContain('super-secret-value');
    expect(JSON.stringify(snapshot)).not.toContain('hidden-value');
  });
});
