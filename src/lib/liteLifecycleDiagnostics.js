const STORAGE_KEY = 'pocketlab_lite_lifecycle_diagnostics_v1';
const MAX_TEXT = 160;

function nowIso() {
  return new Date().toISOString();
}

function randomId() {
  try {
    return globalThis.crypto?.randomUUID?.() || `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  } catch {
    return `session-${Date.now()}`;
  }
}

const state = {
  frontend_session_id: randomId(),
  captured_at: nowIso(),
  visibility_state: typeof document === 'undefined' ? 'unknown' : document.visibilityState,
  online_state: typeof navigator === 'undefined' ? true : navigator.onLine !== false,
  active_event_source_count: 0,
  active_poll_timer_count: 0,
  visibility_listener_count: 0,
  online_listener_count: 0,
  offline_listener_count: 0,
  reconnect_attempt_count: 0,
  backend_reconciliation_count: 0,
  cached_run_id: '',
  backend_run_id: '',
  cached_revision: '',
  backend_revision: '',
  write_actions_blocked: false,
  duplicate_submission_count: 0,
  last_sse_opened_at: '',
  last_sse_closed_at: '',
  last_poll_started_at: '',
  last_poll_stopped_at: '',
  last_backend_reconciled_at: '',
};

function boundedCount(value) {
  const number = Number(value || 0);
  return Number.isFinite(number) ? Math.max(0, Math.min(100000, Math.trunc(number))) : 0;
}

function safeText(value) {
  return String(value || '').replace(/(bearer\s+|token=|password=|secret=|api[_-]?key=)[^\s&]+/gi, '$1[hidden]').slice(0, MAX_TEXT);
}

function persist() {
  state.captured_at = nowIso();
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshotLiteLifecycleDiagnostics()));
  } catch {
    // Diagnostics are best effort and never affect the product flow.
  }
  try {
    window.__POCKETLAB_LITE_LIFECYCLE_DIAGNOSTICS__ = {
      snapshot: snapshotLiteLifecycleDiagnostics,
    };
  } catch {
    // Harmless fallback for hardened browsers.
  }
}

export function snapshotLiteLifecycleDiagnostics() {
  return {
    ...state,
    active_event_source_count: boundedCount(state.active_event_source_count),
    active_poll_timer_count: boundedCount(state.active_poll_timer_count),
    visibility_listener_count: boundedCount(state.visibility_listener_count),
    online_listener_count: boundedCount(state.online_listener_count),
    offline_listener_count: boundedCount(state.offline_listener_count),
    reconnect_attempt_count: boundedCount(state.reconnect_attempt_count),
    backend_reconciliation_count: boundedCount(state.backend_reconciliation_count),
    duplicate_submission_count: boundedCount(state.duplicate_submission_count),
    cached_run_id: safeText(state.cached_run_id),
    backend_run_id: safeText(state.backend_run_id),
    cached_revision: safeText(state.cached_revision),
    backend_revision: safeText(state.backend_revision),
    sanitized: true,
  };
}

export function updateLiteLifecycleEnvironment({ visibilityState, onlineState } = {}) {
  if (visibilityState !== undefined) state.visibility_state = safeText(visibilityState || 'unknown');
  if (onlineState !== undefined) {
    state.online_state = Boolean(onlineState);
    if (!state.online_state) state.write_actions_blocked = true;
  }
  persist();
}

export function trackLiteLifecycleListener(kind, delta) {
  const key = `${safeText(kind)}_listener_count`;
  if (!Object.prototype.hasOwnProperty.call(state, key)) return;
  state[key] = Math.max(0, boundedCount(state[key]) + Number(delta || 0));
  persist();
}

export function trackLiteLifecycleEventSource(open) {
  state.active_event_source_count = Math.max(0, boundedCount(state.active_event_source_count) + (open ? 1 : -1));
  if (open) {
    state.last_sse_opened_at = nowIso();
    state.reconnect_attempt_count = boundedCount(state.reconnect_attempt_count) + 1;
  } else {
    state.last_sse_closed_at = nowIso();
  }
  persist();
}

export function trackLiteLifecyclePollTimer(open) {
  state.active_poll_timer_count = Math.max(0, boundedCount(state.active_poll_timer_count) + (open ? 1 : -1));
  if (open) state.last_poll_started_at = nowIso();
  else state.last_poll_stopped_at = nowIso();
  persist();
}

export function reconcileLiteLifecycle({ cachedRunId = '', backendRunId = '', cachedRevision = '', backendRevision = '', writeActionsBlocked = false } = {}) {
  state.cached_run_id = safeText(cachedRunId);
  state.backend_run_id = safeText(backendRunId);
  state.cached_revision = safeText(cachedRevision);
  state.backend_revision = safeText(backendRevision);
  state.write_actions_blocked = Boolean(writeActionsBlocked);
  state.backend_reconciliation_count = boundedCount(state.backend_reconciliation_count) + 1;
  state.last_backend_reconciled_at = nowIso();
  persist();
}

export function reconcileLiteSecurityProgress({ cachedProgress = {}, backendProgress = {}, writeActionsBlocked = false } = {}) {
  const backendRunId = safeText(backendProgress?.run_id || '');
  const backendRevision = safeText(
    backendProgress?.revision
      || backendProgress?.progress_revision
      || backendProgress?.run_revision
      || backendProgress?.sqlite_revision
      || '',
  );
  if (!backendRunId || !backendRevision) return false;

  reconcileLiteLifecycle({
    cachedRunId: cachedProgress?.run_id || '',
    backendRunId,
    cachedRevision: cachedProgress?.revision || cachedProgress?.progress_revision || cachedProgress?.run_revision || '',
    backendRevision,
    writeActionsBlocked,
  });
  return true;
}

export function recordLiteDuplicateSubmission() {
  state.duplicate_submission_count = boundedCount(state.duplicate_submission_count) + 1;
  persist();
}

export function resetLiteLifecycleDiagnosticsForTest() {
  Object.assign(state, {
    frontend_session_id: randomId(),
    captured_at: nowIso(),
    visibility_state: 'visible',
    online_state: true,
    active_event_source_count: 0,
    active_poll_timer_count: 0,
    visibility_listener_count: 0,
    online_listener_count: 0,
    offline_listener_count: 0,
    reconnect_attempt_count: 0,
    backend_reconciliation_count: 0,
    cached_run_id: '',
    backend_run_id: '',
    cached_revision: '',
    backend_revision: '',
    write_actions_blocked: false,
    duplicate_submission_count: 0,
    last_sse_opened_at: '',
    last_sse_closed_at: '',
    last_poll_started_at: '',
    last_poll_stopped_at: '',
    last_backend_reconciled_at: '',
  });
  persist();
}

export async function publishLiteLifecycleDiagnostics(liteApi) {
  if (!liteApi?.lifecycleDiagnosticsChallenge || !liteApi?.recordLifecycleDiagnostics) return { accepted: false };
  try {
    const challenge = await liteApi.lifecycleDiagnosticsChallenge();
    if (!challenge?.active || !challenge?.challenge_id) return { accepted: false };
    return await liteApi.recordLifecycleDiagnostics(challenge.challenge_id, snapshotLiteLifecycleDiagnostics());
  } catch {
    return { accepted: false };
  }
}

persist();
