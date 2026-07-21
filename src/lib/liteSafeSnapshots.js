import {
  LITE_SECURITY_PROFILE_IDS,
  LITE_SECURITY_PROFILE_RETENTION_POLICY,
  selectSecurityHistorySnapshotView,
  selectSecurityProfileSnapshotViews,
  selectSecurityScreenSnapshotView,
} from './liteViewModels.js';
import {
  checkLiteOfflineDbAvailability,
  estimateLiteCacheHealth,
  getLiteOfflineCacheHealth,
  markLiteBackendReachable,
  markLiteBackendUnreachable,
  markLiteSnapshotRejected,
  normalizeOfflineEndpoint,
  pruneExpiredOfflineSnapshots,
  readOfflineSafeSnapshot,
  setOfflineCacheMeta,
  writeOfflineSafeSnapshot,
} from './liteOfflineDb.js';

const SNAPSHOT_PREFIX = 'pocketlab:lite:safe-snapshot:';
export const SAFE_LITE_GET_ENDPOINTS = new Set([
  '/api/lite/status',
  '/api/lite/catalog',
  '/api/lite/apps/photoprism/actions',
  '/api/lite/fleet',
  '/api/lite/security',
  '/api/lite/security/summary',
  '/api/lite/security/profiles/quick',
  '/api/lite/security/profiles/full',
  '/api/lite/security/profiles/app',
  '/api/lite/security/profiles/app/photoprism',
  '/api/lite/security/history/index',
  '/api/lite/recovery',
  '/api/lite/recovery/summary',
  '/api/lite/recovery/details',
]);

export const LITE_SNAPSHOT_TTL_MS = {
  '/api/lite/status': 5 * 60 * 1000,
  '/api/lite/fleet': 3 * 60 * 1000,
  '/api/lite/catalog': 8 * 60 * 1000,
  '/api/lite/apps/photoprism/actions': 8 * 60 * 1000,
  '/api/lite/security': 20 * 60 * 1000,
  '/api/lite/security/summary': 20 * 60 * 1000,
  '/api/lite/security/profiles/quick': 60 * 60 * 1000,
  '/api/lite/security/profiles/full': 60 * 60 * 1000,
  '/api/lite/security/profiles/app': 60 * 60 * 1000,
  '/api/lite/security/profiles/app/photoprism': 60 * 60 * 1000,
  '/api/lite/security/history/index': 60 * 60 * 1000,
  '/api/lite/recovery': 20 * 60 * 1000,
  '/api/lite/recovery/summary': 20 * 60 * 1000,
  '/api/lite/recovery/details': 20 * 60 * 1000,
};

const DEFAULT_TTL_MS = 10 * 60 * 1000;
const SCHEMA_VERSION = 1;
const REDACTION_VERSION = 1;
const UNSAFE_KEY_PATTERN = /token|secret|password|credential|api[_-]?key|apikey|hash|private[_-]?key|invite[_-]?token|bootstrap|command[_-]?payload|raw[_-]?log|raw[_-]?logs|evidence[_-]?path|private[_-]?path|restic[_-]?password|vault|unseal|bearer|authorization|nats[_-]?(password|credential|credentials|token|secret|url)/i;
const UNSAFE_VALUE_PATTERN = /(bearer\s+[^\s]+|token=|password=|api[_-]?key=|secret=|authorization:\s*bearer|nats:\/\/[^\s/]+:[^\s@]+@|-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----)/i;
const MAX_ARRAY_ITEMS = 80;
const MAX_STRING_LENGTH = 1200;
const MAX_SCAN_DEPTH = 8;
const inMemorySnapshots = new Map();
const SECURITY_SNAPSHOT_ENDPOINT = '/api/lite/security';
const SECURITY_SUMMARY_SNAPSHOT_ENDPOINT = '/api/lite/security/summary';
const SECURITY_SNAPSHOT_ENDPOINTS = new Set([SECURITY_SNAPSHOT_ENDPOINT, SECURITY_SUMMARY_SNAPSHOT_ENDPOINT]);
const SECURITY_HISTORY_SNAPSHOT_ENDPOINT = '/api/lite/security/history/index';
const SECURITY_DEFAULT_APP_ID = 'photoprism';
const SECURITY_APP_SNAPSHOT_PATH_PATTERN = /^\/api\/lite\/security\/profiles\/app\/[a-z0-9][a-z0-9_-]{0,79}$/;
const SECURITY_PROFILE_SNAPSHOT_ENDPOINTS = LITE_SECURITY_PROFILE_IDS.reduce((items, profile) => {
  items[profile] = `/api/lite/security/profiles/${profile}`;
  return items;
}, {});

function securityProfileSnapshotEndpoint(profile = 'quick', appId = '') {
  const normalizedProfile = LITE_SECURITY_PROFILE_IDS.includes(String(profile || '').toLowerCase()) ? String(profile || '').toLowerCase() : 'quick';
  if (normalizedProfile !== 'app') return SECURITY_PROFILE_SNAPSHOT_ENDPOINTS[normalizedProfile];
  const safeAppId = String(appId || SECURITY_DEFAULT_APP_ID).toLowerCase().replace(/[^a-z0-9_-]+/g, '').slice(0, 80);
  return `/api/lite/security/profiles/app/${safeAppId || SECURITY_DEFAULT_APP_ID}`;
}
export const LITE_SECURITY_SCAN_BROADCAST_CHANNEL = 'pocketlab-lite-security-scan-sync';
export const LITE_SECURITY_SCAN_COMPLETED_EVENT = 'security:scan-completed';
let hydrationStarted = false;
let pruneStarted = false;
let securityBroadcastChannel = null;

function canUseStorage() {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

function canUseBroadcastChannel() {
  return typeof window !== 'undefined' && typeof window.BroadcastChannel !== 'undefined';
}

function getSecurityBroadcastChannel() {
  if (!canUseBroadcastChannel()) return null;
  if (securityBroadcastChannel) return securityBroadcastChannel;
  try {
    securityBroadcastChannel = new window.BroadcastChannel(LITE_SECURITY_SCAN_BROADCAST_CHANNEL);
    return securityBroadcastChannel;
  } catch {
    return null;
  }
}

function isTerminalSecuritySnapshot(payload = {}) {
  const status = String(payload?.status || payload?.latest_run?.status || '').toLowerCase().replace(/[\s-]+/g, '_');
  return ['succeeded', 'success', 'completed', 'complete', 'done', 'failed', 'failure', 'error', 'blocked', 'review', 'needs_attention'].includes(status);
}

function sanitizeSecurityScanCompletedPayload(profile = 'quick', payload = {}, source = 'liteSafeSnapshots') {
  const latest = payload?.latest_run || {};
  const completedAt = payload?.completed_at || latest.completed_at || payload?.updated_at || payload?.freshness?.checked_at || nowIso();
  return {
    type: LITE_SECURITY_SCAN_COMPLETED_EVENT,
    profile,
    run_id: payload?.run_id || latest.run_id || '',
    completed_at: completedAt,
    status: payload?.status || latest.status || 'completed',
    source,
  };
}

export function broadcastLiteSecurityScanCompleted(profile = 'quick', payload = {}, { source = 'liteSafeSnapshots', requireTerminal = true } = {}) {
  if (requireTerminal && !isTerminalSecuritySnapshot(payload)) return null;
  const detail = sanitizeSecurityScanCompletedPayload(profile, payload, source);
  try { getSecurityBroadcastChannel()?.postMessage(detail); } catch { /* best effort cross-tab sync */ }
  try { window.dispatchEvent(new CustomEvent(LITE_SECURITY_SCAN_COMPLETED_EVENT, { detail })); } catch { /* best effort same-tab sync */ }
  return detail;
}

function postSecurityScanCompleted(profile = 'quick', payload = {}) {
  return broadcastLiteSecurityScanCompleted(profile, payload, { source: 'liteSafeSnapshots', requireTerminal: true });
}

export function subscribeLiteSecurityScanCompleted(callback) {
  if (typeof callback !== 'function' || typeof window === 'undefined') return () => {};
  const channel = getSecurityBroadcastChannel();
  const onWindowEvent = (event) => callback(event.detail || {});
  const onChannelMessage = (event) => callback(event.data || {});
  window.addEventListener(LITE_SECURITY_SCAN_COMPLETED_EVENT, onWindowEvent);
  if (channel) channel.addEventListener('message', onChannelMessage);
  return () => {
    window.removeEventListener(LITE_SECURITY_SCAN_COMPLETED_EVENT, onWindowEvent);
    if (channel) channel.removeEventListener('message', onChannelMessage);
  };
}

export function normalizeLiteSnapshotPath(path = '') {
  try {
    const url = new URL(path, typeof window !== 'undefined' ? window.location.origin : 'http://127.0.0.1');
    if (url.pathname === '/api/lite/security/profiles/app' && url.searchParams.get('app_id')) {
      return securityProfileSnapshotEndpoint('app', url.searchParams.get('app_id'));
    }
  } catch {
    // Fall through to the shared endpoint normalizer.
  }
  return normalizeOfflineEndpoint(path);
}

export function isSafeLiteSnapshotPath(path = '') {
  const normalized = normalizeLiteSnapshotPath(path);
  return SAFE_LITE_GET_ENDPOINTS.has(normalized) || SECURITY_APP_SNAPSHOT_PATH_PATTERN.test(normalized);
}

export function ttlForLiteSnapshotPath(path = '') {
  const normalized = normalizeLiteSnapshotPath(path);
  if (SECURITY_APP_SNAPSHOT_PATH_PATTERN.test(normalized)) return LITE_SNAPSHOT_TTL_MS['/api/lite/security/profiles/app'];
  return LITE_SNAPSHOT_TTL_MS[normalized] || DEFAULT_TTL_MS;
}

function nowIso() {
  return new Date().toISOString();
}

function addMsIso(value, ms) {
  const start = value ? new Date(value).getTime() : Date.now();
  const safeStart = Number.isFinite(start) ? start : Date.now();
  return new Date(safeStart + ms).toISOString();
}

function isExpiredAt(value) {
  if (!value) return false;
  const timestamp = new Date(value).getTime();
  return Number.isFinite(timestamp) && timestamp < Date.now();
}

function storageKey(path = '') {
  return `${SNAPSHOT_PREFIX}${normalizeLiteSnapshotPath(path)}`;
}

function stripSnapshotMeta(data) {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return data;
  const { __liteSnapshot: _snapshot, ...rest } = data;
  return rest;
}

function safeApproximateSize(payload) {
  try {
    return new Blob([JSON.stringify(payload ?? null)]).size;
  } catch {
    try {
      return JSON.stringify(payload ?? null).length;
    } catch {
      return 0;
    }
  }
}

export function findUnsafeLiteSnapshotContent(value, depth = 0, trail = 'payload') {
  if (value == null) return null;
  if (depth > MAX_SCAN_DEPTH) return null;
  if (typeof value === 'string') {
    if (UNSAFE_VALUE_PATTERN.test(value)) return `${trail}:unsafe_value`;
    return null;
  }
  if (typeof value === 'number' || typeof value === 'boolean') return null;
  if (Array.isArray(value)) {
    const limit = Math.min(value.length, MAX_ARRAY_ITEMS);
    for (let index = 0; index < limit; index += 1) {
      const reason = findUnsafeLiteSnapshotContent(value[index], depth + 1, `${trail}[${index}]`);
      if (reason) return reason;
    }
    return null;
  }
  if (typeof value === 'object') {
    for (const [key, entry] of Object.entries(value)) {
      const safeKey = String(key || '');
      if (safeKey.startsWith('__lite')) continue;
      if (UNSAFE_KEY_PATTERN.test(safeKey)) return `${trail}.${safeKey}:unsafe_key`;
      const reason = findUnsafeLiteSnapshotContent(entry, depth + 1, `${trail}.${safeKey}`);
      if (reason) return reason;
    }
  }
  return null;
}

export function isLiteSnapshotPayloadSafe(value) {
  return !findUnsafeLiteSnapshotContent(value);
}

export function sanitizeLiteSnapshot(value, depth = 0) {
  if (value == null) return value;
  if (depth > MAX_SCAN_DEPTH) return '[hidden]';
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

function toSnapshotRecord(path = '', data, overrides = {}) {
  const normalizedPath = normalizeLiteSnapshotPath(path);
  const checkedAt = overrides.checkedAt || nowIso();
  const savedAt = overrides.savedAt || checkedAt;
  const expiresAt = overrides.expiresAt || addMsIso(savedAt, ttlForLiteSnapshotPath(normalizedPath));
  const payload = sanitizeLiteSnapshot(stripSnapshotMeta(data));
  return {
    key: normalizedPath,
    endpoint: normalizedPath,
    payload,
    checked_at: checkedAt,
    saved_at: savedAt,
    expires_at: expiresAt,
    schema_version: SCHEMA_VERSION,
    redaction_version: REDACTION_VERSION,
    source: overrides.source || 'network',
    payload_kind: overrides.payloadKind || 'lite-safe-read',
    status: overrides.status || 'saved',
    approximate_size_bytes: safeApproximateSize(payload),
  };
}

function withMeta(data, meta) {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return data;
  const expiresAt = meta.expiresAt || meta.expires_at || null;
  const expired = Boolean(meta.expired || meta.isExpired || isExpiredAt(expiresAt));
  return {
    ...data,
    __liteSnapshot: {
      source: meta.source,
      path: normalizeLiteSnapshotPath(meta.path || meta.endpoint),
      cached: meta.source === 'cache',
      stale: Boolean(meta.stale || meta.source === 'cache'),
      expired,
      isExpired: expired,
      refreshing: Boolean(meta.refreshing),
      checkedAt: meta.checkedAt || meta.checked_at || null,
      savedAt: meta.savedAt || meta.saved_at || null,
      expiresAt,
      schemaVersion: meta.schemaVersion || meta.schema_version || SCHEMA_VERSION,
      redactionVersion: meta.redactionVersion || meta.redaction_version || REDACTION_VERSION,
      payloadKind: meta.payloadKind || meta.payload_kind || 'lite-safe-read',
      status: meta.status || 'saved',
      approximateSizeBytes: meta.approximateSizeBytes || meta.approximate_size_bytes || null,
      cacheAvailable: getLiteOfflineCacheHealth().cacheAvailable,
      error: meta.error || null,
    },
  };
}

function parseStoredSnapshot(path = '', raw) {
  if (!raw) return null;
  try {
    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw;
    const payload = parsed?.payload || parsed?.data;
    if (!payload) return null;
    const record = {
      endpoint: parsed.endpoint || parsed.path || path,
      payload,
      checked_at: parsed.checked_at || parsed.checkedAt || parsed.savedAt || parsed.saved_at || null,
      saved_at: parsed.saved_at || parsed.savedAt || null,
      expires_at: parsed.expires_at || parsed.expiresAt || null,
      source: 'cache',
      payload_kind: parsed.payload_kind || parsed.payloadKind || 'lite-safe-read',
      status: parsed.status || 'saved',
      schema_version: parsed.schema_version || parsed.version || SCHEMA_VERSION,
      redaction_version: parsed.redaction_version || REDACTION_VERSION,
      approximate_size_bytes: parsed.approximate_size_bytes || parsed.approximateSizeBytes || null,
    };
    return withMeta(record.payload, { ...record, path: record.endpoint, source: 'cache' });
  } catch {
    return null;
  }
}

function readLocalStorageSnapshot(path = '') {
  if (!canUseStorage()) return null;
  try {
    return parseStoredSnapshot(path, window.localStorage.getItem(storageKey(path)));
  } catch {
    return null;
  }
}

function pruneLocalStorageSecuritySnapshots() {
  if (!canUseStorage()) return;
  try {
    const keys = Object.keys(window.localStorage).filter((key) => key.startsWith(`${SNAPSHOT_PREFIX}/api/lite/security`));
    const profileKeys = keys.filter((key) => key.includes('/profiles/'));
    const historyKeys = keys.filter((key) => key.endsWith('/history/index'));
    const grouped = profileKeys.reduce((groups, key) => {
      const profile = key.split('/').pop() || 'quick';
      groups[profile] = groups[profile] || [];
      groups[profile].push(key);
      return groups;
    }, {});
    Object.values(grouped).forEach((items) => {
      items
        .map((key) => ({ key, parsed: parseStoredSnapshot(key.replace(SNAPSHOT_PREFIX, ''), window.localStorage.getItem(key)) }))
        .sort((left, right) => String(right.parsed?.__liteSnapshot?.savedAt || '').localeCompare(String(left.parsed?.__liteSnapshot?.savedAt || '')))
        .slice(LITE_SECURITY_PROFILE_RETENTION_POLICY.profileSnapshotLimit || 3)
        .forEach((item) => window.localStorage.removeItem(item.key));
    });
    historyKeys.slice(1).forEach((key) => window.localStorage.removeItem(key));
  } catch {
    // Best effort localStorage mirror cleanup only.
  }
}

function writeLocalStorageSnapshot(path = '', record) {
  if (!canUseStorage()) return;
  try {
    window.localStorage.setItem(storageKey(path), JSON.stringify({
      version: SCHEMA_VERSION,
      path: normalizeLiteSnapshotPath(path),
      endpoint: record.endpoint,
      savedAt: record.saved_at,
      checkedAt: record.checked_at,
      expiresAt: record.expires_at,
      status: record.status,
      payloadKind: record.payload_kind,
      approximateSizeBytes: record.approximate_size_bytes,
      data: record.payload,
    }));
    if (normalizeLiteSnapshotPath(path).startsWith('/api/lite/security')) pruneLocalStorageSecuritySnapshots();
  } catch {
    // localStorage is a best-effort mirror so startup can remain instant.
  }
}


function commitLiteSnapshotRecord(path = '', record) {
  const normalizedPath = normalizeLiteSnapshotPath(path);
  inMemorySnapshots.set(normalizedPath, record);
  writeLocalStorageSnapshot(normalizedPath, record);
  writeOfflineSafeSnapshot({
    endpoint: normalizedPath,
    payload: record.payload,
    checkedAt: record.checked_at,
    savedAt: record.saved_at,
    expiresAt: record.expires_at,
    status: record.status,
    source: record.source,
    payloadKind: record.payload_kind,
  });
}

function readSnapshotPayloadWithoutMeta(path = '') {
  const normalizedPath = normalizeLiteSnapshotPath(path);
  const memory = inMemorySnapshots.get(normalizedPath);
  if (memory?.payload) return memory.payload;
  return stripSnapshotMeta(readLocalStorageSnapshot(normalizedPath));
}

function writeSecurityProfileSnapshots(sourcePath = '', payload = null, sourceRecord = null) {
  if (!SECURITY_SNAPSHOT_ENDPOINTS.has(normalizeLiteSnapshotPath(sourcePath)) || !payload || typeof payload !== 'object') return;
  try {
    const screenSnapshot = selectSecurityScreenSnapshotView(payload);
    const profiles = selectSecurityProfileSnapshotViews(screenSnapshot);
    LITE_SECURITY_PROFILE_IDS.forEach((profile) => {
      const profilePayload = profiles[profile];
      if (!profilePayload || typeof profilePayload !== 'object') return;
      const endpoint = securityProfileSnapshotEndpoint(profile, profilePayload.app_id);
      const unsafeReason = findUnsafeLiteSnapshotContent(profilePayload);
      if (unsafeReason) {
        markLiteSnapshotRejected(endpoint, unsafeReason);
        return;
      }
      const record = toSnapshotRecord(endpoint, profilePayload, {
        checkedAt: sourceRecord?.checked_at,
        savedAt: sourceRecord?.saved_at,
        source: 'network',
        payloadKind: 'lite-security-profile-summary',
      });
      commitLiteSnapshotRecord(endpoint, record);
      postSecurityScanCompleted(profile, record.payload);
    });

    const historyPayload = selectSecurityHistorySnapshotView(screenSnapshot);
    const unsafeHistoryReason = findUnsafeLiteSnapshotContent(historyPayload);
    if (unsafeHistoryReason) {
      markLiteSnapshotRejected(SECURITY_HISTORY_SNAPSHOT_ENDPOINT, unsafeHistoryReason);
      return;
    }
    const historyRecord = toSnapshotRecord(SECURITY_HISTORY_SNAPSHOT_ENDPOINT, historyPayload, {
      checkedAt: sourceRecord?.checked_at,
      savedAt: sourceRecord?.saved_at,
      source: 'network',
      payloadKind: 'lite-security-history-index',
    });
    commitLiteSnapshotRecord(SECURITY_HISTORY_SNAPSHOT_ENDPOINT, historyRecord);
  } catch (error) {
    markLiteSnapshotRejected(SECURITY_SNAPSHOT_ENDPOINT, error?.message || 'security_profile_snapshot_failed');
  }
}

function readSecurityCompositeSnapshot(requestPath = SECURITY_SUMMARY_SNAPSHOT_ENDPOINT) {
  const securityProfiles = {};
  const profileLatest = {};
  let newestTimestamp = 0;
  let newestProfile = '';

  LITE_SECURITY_PROFILE_IDS.forEach((profile) => {
    const endpoint = profile === 'app' ? securityProfileSnapshotEndpoint('app', SECURITY_DEFAULT_APP_ID) : SECURITY_PROFILE_SNAPSHOT_ENDPOINTS[profile];
    const payload = readSnapshotPayloadWithoutMeta(endpoint) || (profile === 'app' ? readSnapshotPayloadWithoutMeta(SECURITY_PROFILE_SNAPSHOT_ENDPOINTS.app) : null);
    if (!payload || typeof payload !== 'object') return;
    securityProfiles[profile] = payload;
    if (payload.latest_run || payload.run_id || payload.completed_at) profileLatest[profile] = payload.latest_run || payload;
    const timestamp = Date.parse(payload.completed_at || payload.updated_at || payload.started_at || '') || 0;
    if (timestamp >= newestTimestamp) {
      newestTimestamp = timestamp;
      newestProfile = profile;
    }
  });

  const historyPayload = readSnapshotPayloadWithoutMeta(SECURITY_HISTORY_SNAPSHOT_ENDPOINT) || {};
  if (!Object.keys(securityProfiles).length && !Array.isArray(historyPayload.history)) return null;

  const latest = newestProfile ? securityProfiles[newestProfile] : null;
  const savedAt = latest?.updated_at || latest?.completed_at || historyPayload.updated_at || nowIso();
  const composite = {
    view_model: 'security-screen-snapshot-v1',
    version: 'profile-aware-snapshot',
    status: latest?.status || 'saved',
    summary: latest?.summary || 'Saved Security state is available.',
    score: latest?.score || 0,
    scan_profile: newestProfile || 'quick',
    app_id: latest?.app_id || '',
    app_label: latest?.app_label || '',
    checked_at: savedAt,
    updated_at: savedAt,
    last_run: latest?.latest_run || null,
    security_summary: latest ? {
      status: latest.status,
      summary: latest.summary,
      score: latest.score,
      app_id: latest.app_id,
      app_label: latest.app_label,
      items_to_review: latest.items_to_review,
      evidence_count: latest.evidence_summary?.evidence_count || latest.evidence_refs?.length || 0,
      checked_at: latest.completed_at || latest.updated_at,
      updated_at: latest.updated_at || latest.completed_at,
    } : {},
    profile_latest: profileLatest,
    profile_freshness: LITE_SECURITY_PROFILE_IDS.reduce((items, profile) => { items[profile] = securityProfiles[profile]?.freshness || { profile, label: 'No saved check yet', empty_label: 'No saved check yet', has_run: false, is_saved: true }; return items; }, {}),
    security_profiles: securityProfiles,
    history_summary: Array.isArray(historyPayload.history) ? historyPayload.history : [],
    history: Array.isArray(historyPayload.history) ? historyPayload.history : [],
    evidence_summary: latest?.evidence_summary || {},
    security_history_snapshot: historyPayload,
    live: false,
    saved_snapshot: true,
    offline_details: {
      visible: true,
      title: 'Showing saved Security details',
      summary: 'Reconnect to run a new check or refresh live evidence. Saved details remain read-only.',
      write_actions_disabled: true,
      run_buttons_label: 'Reconnect to run checks',
    },
    sanitized: true,
  };
  return withMeta(composite, {
    source: 'cache',
    path: requestPath,
    stale: true,
    savedAt,
    checkedAt: savedAt,
    expiresAt: addMsIso(savedAt, ttlForLiteSnapshotPath(requestPath)),
    payloadKind: 'lite-security-composite-profile-summary',
    status: 'saved',
  });
}

function rememberSnapshot(path = '', record) {
  const normalizedPath = normalizeLiteSnapshotPath(path);
  inMemorySnapshots.set(normalizedPath, record);
  return withMeta(record.payload, { ...record, path: normalizedPath, source: 'cache' });
}

function rememberDexieRecord(record) {
  if (!record?.endpoint || !record?.payload) return null;
  const normalizedPath = normalizeLiteSnapshotPath(record.endpoint);
  const normalized = {
    ...record,
    endpoint: normalizedPath,
    source: 'cache',
  };
  inMemorySnapshots.set(normalizedPath, normalized);
  writeLocalStorageSnapshot(normalizedPath, normalized);
  return withMeta(normalized.payload, { ...normalized, path: normalizedPath, source: 'cache' });
}

export function hydrateLiteSnapshotsFromDexie() {
  if (hydrationStarted) return;
  hydrationStarted = true;
  checkLiteOfflineDbAvailability().then((available) => {
    if (!available) return;
    SAFE_LITE_GET_ENDPOINTS.forEach((endpoint) => {
      readOfflineSafeSnapshot(endpoint).then((record) => {
        if (record) rememberDexieRecord(record);
      });
    });
  });
}

export function pruneLiteSnapshots() {
  if (pruneStarted) return;
  pruneStarted = true;
  pruneExpiredOfflineSnapshots().finally(() => {
    pruneStarted = false;
  });
}

export function readLiteSnapshot(path = '') {
  const normalizedPath = normalizeLiteSnapshotPath(path);
  if (!isSafeLiteSnapshotPath(normalizedPath)) return null;
  const memory = inMemorySnapshots.get(normalizedPath);
  if (memory) return withMeta(memory.payload, { ...memory, path: normalizedPath, source: 'cache' });
  const local = readLocalStorageSnapshot(normalizedPath);
  if (local) return local;
  if (SECURITY_SNAPSHOT_ENDPOINTS.has(normalizedPath)) {
    const securityComposite = readSecurityCompositeSnapshot(normalizedPath);
    if (securityComposite) return securityComposite;
  }
  hydrateLiteSnapshotsFromDexie();
  return null;
}

export async function readLiteSnapshotAsync(path = '') {
  const normalizedPath = normalizeLiteSnapshotPath(path);
  if (!isSafeLiteSnapshotPath(normalizedPath)) return null;
  const syncSnapshot = readLiteSnapshot(normalizedPath);
  if (syncSnapshot) return syncSnapshot;
  const record = await readOfflineSafeSnapshot(normalizedPath);
  if (!record) return null;
  return rememberDexieRecord(record);
}

export function liteSecurityProfileSnapshotPath(profile = 'quick', appId = '') {
  return securityProfileSnapshotEndpoint(profile, appId);
}

export function liteSecurityHistorySnapshotPath() {
  return SECURITY_HISTORY_SNAPSHOT_ENDPOINT;
}

export function writeLiteSnapshot(path = '', data) {
  const normalizedPath = normalizeLiteSnapshotPath(path);
  if (!isSafeLiteSnapshotPath(normalizedPath) || !data || typeof data !== 'object') return { stored: false, reason: 'unsafe_path_or_payload' };
  const payload = stripSnapshotMeta(data);
  const unsafeReason = findUnsafeLiteSnapshotContent(payload);
  if (unsafeReason) {
    markLiteSnapshotRejected(normalizedPath, unsafeReason);
    return { stored: false, rejected: true, reason: unsafeReason };
  }
  const record = toSnapshotRecord(normalizedPath, payload);
  commitLiteSnapshotRecord(normalizedPath, record);
  writeSecurityProfileSnapshots(normalizedPath, record.payload, record);
  setOfflineCacheMeta('lastCacheWriteAt', record.saved_at);
  pruneLiteSnapshots();
  return { stored: true, savedAt: record.saved_at, expiresAt: record.expires_at };
}

export async function writeLiteSnapshotAsync(path = '', data) {
  const result = writeLiteSnapshot(path, data);
  return result;
}

export function attachFreshSnapshotMeta(path = '', data) {
  const timestamp = nowIso();
  markLiteBackendReachable();
  return withMeta(data, {
    source: 'network',
    path,
    stale: false,
    savedAt: timestamp,
    checkedAt: timestamp,
    expiresAt: addMsIso(timestamp, ttlForLiteSnapshotPath(path)),
    status: 'fresh',
  });
}

export function markLiteSnapshotBackendUnreachable() {
  markLiteBackendUnreachable();
}

export function getLiteSnapshotCacheHealth() {
  return getLiteOfflineCacheHealth();
}

export function refreshLiteSnapshotCacheHealth() {
  return estimateLiteCacheHealth();
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
  const expired = Boolean(meta.expired || meta.isExpired);
  if (meta.source === 'cache' || meta.cached || meta.stale) {
    return {
      title: expired ? 'Saved state expired' : 'Showing saved state',
      summary: expired
        ? 'Pocket Lab is not reachable. This saved state may be old.'
        : fallbackError || meta.error || 'Pocket Lab is not reachable. Saved state only.',
      detail,
      stale: true,
      expired,
      disabledReason: expired ? 'Saved state expired. Reconnect to continue.' : 'Saved state only. Reconnect to continue.',
    };
  }
  if (meta.refreshing) {
    return { title: 'Refreshing…', summary: 'Pocket Lab is checking for fresh state.', detail, stale: false, expired: false, disabledReason: '' };
  }
  return { title: 'Updated just now', summary: 'Pocket Lab is reachable.', detail, stale: false, expired: false, disabledReason: '' };
}

hydrateLiteSnapshotsFromDexie();
pruneLiteSnapshots();
