const SNAPSHOT_PREFIX = 'pocketlab:lite:safe-snapshot:';
const SAFE_LITE_GET_ENDPOINTS = new Set([
  '/api/lite/status',
  '/api/lite/catalog',
  '/api/lite/apps/photoprism/actions',
  '/api/lite/fleet',
  '/api/lite/security',
  '/api/lite/recovery',
]);

const UNSAFE_KEY_PATTERN = /token|secret|password|credential|api[_-]?key|nats|bootstrap|invite|raw|log|private[_-]?path|hash|signature|authorization/i;
const UNSAFE_VALUE_PATTERN = /(bearer\s+|nats:\/\/[^\s]+@|token=|password=|api[_-]?key=|secret=)/i;
const MAX_ARRAY_ITEMS = 80;
const MAX_STRING_LENGTH = 1200;

function canUseStorage() {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

export function normalizeLiteSnapshotPath(path = '') {
  try {
    const url = new URL(path, typeof window !== 'undefined' ? window.location.origin : 'http://127.0.0.1');
    return url.pathname;
  } catch {
    return String(path || '').split('?')[0];
  }
}

export function isSafeLiteSnapshotPath(path = '') {
  return SAFE_LITE_GET_ENDPOINTS.has(normalizeLiteSnapshotPath(path));
}

export function sanitizeLiteSnapshot(value, depth = 0) {
  if (value == null) return value;
  if (depth > 8) return '[hidden]';
  if (typeof value === 'string') {
    if (UNSAFE_VALUE_PATTERN.test(value)) return '[hidden]';
    return value.length > MAX_STRING_LENGTH ? `${value.slice(0, MAX_STRING_LENGTH)}…` : value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') return value;
  if (Array.isArray(value)) return value.slice(0, MAX_ARRAY_ITEMS).map((item) => sanitizeLiteSnapshot(item, depth + 1));
  if (typeof value === 'object') {
    return Object.entries(value).reduce((safe, [key, entry]) => {
      if (String(key || '').startsWith('__lite')) return safe;
      safe[key] = UNSAFE_KEY_PATTERN.test(String(key || '')) ? '[hidden]' : sanitizeLiteSnapshot(entry, depth + 1);
      return safe;
    }, {});
  }
  return undefined;
}

function storageKey(path = '') {
  return `${SNAPSHOT_PREFIX}${normalizeLiteSnapshotPath(path)}`;
}

function withMeta(data, meta) {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return data;
  return {
    ...data,
    __liteSnapshot: {
      source: meta.source,
      path: normalizeLiteSnapshotPath(meta.path),
      cached: meta.source === 'cache',
      stale: Boolean(meta.stale),
      refreshing: Boolean(meta.refreshing),
      checkedAt: meta.checkedAt || null,
      savedAt: meta.savedAt || null,
      error: meta.error || null,
    },
  };
}

export function readLiteSnapshot(path = '') {
  if (!isSafeLiteSnapshotPath(path) || !canUseStorage()) return null;
  try {
    const raw = window.localStorage.getItem(storageKey(path));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed?.data) return null;
    return withMeta(parsed.data, {
      source: 'cache', path, stale: true, savedAt: parsed.savedAt || null, checkedAt: parsed.checkedAt || parsed.savedAt || null,
    });
  } catch {
    return null;
  }
}

export function writeLiteSnapshot(path = '', data) {
  if (!isSafeLiteSnapshotPath(path) || !canUseStorage() || !data || typeof data !== 'object') return;
  try {
    const now = new Date().toISOString();
    window.localStorage.setItem(storageKey(path), JSON.stringify({
      version: 1,
      path: normalizeLiteSnapshotPath(path),
      savedAt: now,
      checkedAt: now,
      data: sanitizeLiteSnapshot(data),
    }));
  } catch {
    // localStorage can be unavailable or full; the app still works without snapshots.
  }
}

export function attachFreshSnapshotMeta(path = '', data) {
  return withMeta(data, { source: 'network', path, stale: false, savedAt: new Date().toISOString(), checkedAt: new Date().toISOString() });
}

export function snapshotAgeLabel(value) {
  if (!value) return 'Last checked earlier';
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return 'Last checked earlier';
  const minutes = Math.floor(Math.max(0, Date.now() - timestamp) / 60000);
  if (minutes < 1) return 'Last checked just now';
  if (minutes === 1) return 'Last checked 1 min ago';
  if (minutes < 60) return `Last checked ${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours === 1) return 'Last checked 1 hour ago';
  if (hours < 24) return `Last checked ${hours} hours ago`;
  return 'Last checked over a day ago';
}

export function describeLiteSnapshot(meta = null, fallbackError = '') {
  if (!meta) return null;
  const detail = snapshotAgeLabel(meta.checkedAt || meta.savedAt);
  if (meta.source === 'cache' || meta.cached || meta.stale) {
    return {
      title: 'Showing saved state',
      summary: fallbackError || meta.error || 'Pocket Lab is not reachable. Saved state only.',
      detail,
      stale: true,
      disabledReason: 'Saved state only. Reconnect to continue.',
    };
  }
  if (meta.refreshing) {
    return { title: 'Refreshing…', summary: 'Pocket Lab is checking for fresh state.', detail, stale: false, disabledReason: '' };
  }
  return { title: 'Live state', summary: 'Pocket Lab is reachable.', detail, stale: false, disabledReason: '' };
}
