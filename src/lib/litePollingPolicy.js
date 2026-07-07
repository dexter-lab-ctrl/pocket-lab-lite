export const LITE_CENTRAL_POLLING_POLICY = 'LITE_CENTRAL_POLLING_POLICY';

export const litePollingIntervals = Object.freeze({
  realtime: 2_000,
  active: 5_000,
  normal: 15_000,
  relaxed: 30_000,
  slow: 60_000,
  background: false,
  off: false,
});

const LIVE_LITE_STATUSES = new Set([
  'queued',
  'pending',
  'accepted',
  'running',
  'working',
  'executing',
  'waiting',
  'in_progress',
  'repairing',
  'joining',
]);

export function normalizeLitePollingStatus(value) {
  return String(value || '').toLowerCase().replace(/[\s-]+/g, '_');
}

export function isLiteLiveStatus(value) {
  return LIVE_LITE_STATUSES.has(normalizeLitePollingStatus(value));
}

export function isLiteDocumentVisible() {
  if (typeof document === 'undefined') return true;
  return document.visibilityState !== 'hidden';
}

export function hasLiteLiveOperation(value, depth = 0) {
  if (!value || depth > 4) return false;

  if (typeof value === 'string') return isLiteLiveStatus(value);
  if (typeof value !== 'object') return false;

  if (value.running === true || value.operation_running === true || value.in_progress === true) return true;
  if (isLiteLiveStatus(value.status) || isLiteLiveStatus(value.state) || isLiteLiveStatus(value.phase)) return true;
  if (value.progress && hasLiteLiveOperation(value.progress, depth + 1)) return true;

  if (Array.isArray(value)) {
    return value.some((item) => hasLiteLiveOperation(item, depth + 1));
  }

  const nestedKeys = ['actions', 'items', 'devices', 'services', 'operations', 'current_action', 'latest_operation'];
  return nestedKeys.some((key) => hasLiteLiveOperation(value[key], depth + 1));
}

export function litePollingIntervalForMode(mode = 'normal') {
  if (mode === 'realtime') return litePollingIntervals.realtime;
  if (mode === 'active') return litePollingIntervals.active;
  if (mode === 'relaxed') return litePollingIntervals.relaxed;
  if (mode === 'slow') return litePollingIntervals.slow;
  if (mode === 'off' || mode === false) return litePollingIntervals.off;
  return litePollingIntervals.normal;
}

export function liteVisiblePollingInterval({
  visible = true,
  live = false,
  active = false,
  relaxed = false,
  mode = 'normal',
  enabledWhenHidden = false,
} = {}) {
  if (!visible && !enabledWhenHidden) return litePollingIntervals.off;
  if (live) return litePollingIntervals.realtime;
  if (active) return litePollingIntervals.active;
  if (relaxed) return litePollingIntervals.relaxed;
  if (!visible) return litePollingIntervals.slow;
  return litePollingIntervalForMode(mode);
}

export function litePollingModeFromValue(mode = 'normal') {
  if (mode === false || mode === 'off') return 'off';
  if (mode === 'realtime') return 'realtime';
  if (mode === 'active') return 'active';
  if (mode === 'relaxed') return 'relaxed';
  if (mode === 'slow') return 'slow';
  return 'normal';
}

export function litePollingBackoffInterval({ failureCount = 0, error = null, savedState = false } = {}) {
  const count = Number(failureCount) || 0;
  if (!error && !savedState && count <= 0) return null;
  if (count <= 1) return litePollingIntervals.active;
  if (count <= 3) return litePollingIntervals.normal;
  if (count <= 6) return litePollingIntervals.relaxed;
  return litePollingIntervals.slow;
}

export function liteQueryPollingInterval({
  visible = true,
  live = false,
  active = false,
  relaxed = false,
  mode = 'normal',
  enabledWhenHidden = false,
  failureCount = 0,
  error = null,
  savedState = false,
} = {}) {
  if (!visible && !enabledWhenHidden) return litePollingIntervals.off;
  if (live) return litePollingIntervals.realtime;

  const backoff = litePollingBackoffInterval({ failureCount, error, savedState });
  if (backoff) return backoff;

  if (active) return litePollingIntervals.active;
  if (relaxed) return litePollingIntervals.relaxed;
  if (!visible) return litePollingIntervals.slow;
  return litePollingIntervalForMode(litePollingModeFromValue(mode));
}

