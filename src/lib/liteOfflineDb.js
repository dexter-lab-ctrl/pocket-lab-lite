import Dexie from 'dexie';

export const LITE_OFFLINE_DB_NAME = 'pocketlab_lite_safe_snapshots';
export const LITE_OFFLINE_DB_VERSION = 1;
export const LITE_OFFLINE_SCHEMA_VERSION = 1;
export const LITE_OFFLINE_REDACTION_VERSION = 1;
export const LITE_OFFLINE_EVENT_LIMIT = 80;
export const LITE_OFFLINE_SNAPSHOT_LIMIT = 24;
export const LITE_OFFLINE_RETENTION_MS = 7 * 24 * 60 * 60 * 1000;
export const LITE_SECURITY_SNAPSHOT_RETENTION_POLICY = {
  profileSnapshotLimit: 3,
  profileHistoryLimit: 20,
  profileEvidenceLimit: 5,
  maxProfileSnapshotBytes: 48 * 1024,
  maxHistorySnapshotBytes: 96 * 1024,
  retentionMs: 14 * 24 * 60 * 60 * 1000,
};

let liteOfflineDb = null;
let liteOfflineDbAvailability = null;
let liteOfflineCacheHealth = {
  cacheAvailable: false,
  cacheError: '',
  lastCacheHitAt: null,
  lastCacheWriteAt: null,
  lastCacheRejectedAt: null,
  lastBackendReachableAt: null,
  lastBackendUnreachableAt: null,
};

function nowIso() {
  return new Date().toISOString();
}

function browserHasIndexedDb() {
  return typeof window !== 'undefined' && typeof indexedDB !== 'undefined';
}

function safeDetail(detail = '') {
  return String(detail || '').replace(/(bearer\s+|token=|password=|secret=|api[_-]?key=)[^\s&]+/gi, '$1[hidden]').slice(0, 240);
}

function updateHealth(next = {}) {
  liteOfflineCacheHealth = { ...liteOfflineCacheHealth, ...next };
  return { ...liteOfflineCacheHealth };
}

export function getLiteOfflineCacheHealth() {
  return { ...liteOfflineCacheHealth };
}

export function normalizeOfflineEndpoint(endpoint = '') {
  try {
    const url = new URL(endpoint, typeof window !== 'undefined' ? window.location.origin : 'http://127.0.0.1');
    return url.pathname;
  } catch {
    return String(endpoint || '').split('?')[0];
  }
}

export function liteSnapshotKeyForEndpoint(endpoint = '') {
  return normalizeOfflineEndpoint(endpoint);
}

export function estimateSnapshotSizeBytes(payload) {
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

export function getLiteOfflineDb() {
  if (!browserHasIndexedDb()) return null;
  if (liteOfflineDb) return liteOfflineDb;
  const db = new Dexie(LITE_OFFLINE_DB_NAME);
  db.version(LITE_OFFLINE_DB_VERSION).stores({
    safe_snapshots: '&key, endpoint, checked_at, saved_at, expires_at, status, payload_kind, source, schema_version',
    snapshot_events: '++id, endpoint, event_type, created_at',
    ui_cache_meta: '&key, updated_at',
  });
  liteOfflineDb = db;
  return liteOfflineDb;
}

export async function checkLiteOfflineDbAvailability() {
  if (liteOfflineDbAvailability !== null) return liteOfflineDbAvailability;
  if (!browserHasIndexedDb()) {
    liteOfflineDbAvailability = false;
    updateHealth({ cacheAvailable: false, cacheError: 'indexeddb_unavailable' });
    return false;
  }
  try {
    const db = getLiteOfflineDb();
    await db.open();
    liteOfflineDbAvailability = true;
    updateHealth({ cacheAvailable: true, cacheError: '' });
    return true;
  } catch (error) {
    liteOfflineDbAvailability = false;
    updateHealth({ cacheAvailable: false, cacheError: error?.name || 'dexie_unavailable' });
    return false;
  }
}

export async function recordOfflineSnapshotEvent({ endpoint = '', eventType = 'snapshot_event', detail = '' } = {}) {
  if (!(await checkLiteOfflineDbAvailability())) return false;
  try {
    const db = getLiteOfflineDb();
    await db.snapshot_events.add({
      endpoint: normalizeOfflineEndpoint(endpoint),
      event_type: String(eventType || 'snapshot_event').slice(0, 80),
      created_at: nowIso(),
      detail: safeDetail(detail),
    });
    await pruneOfflineSnapshotEvents();
    return true;
  } catch (error) {
    updateHealth({ cacheError: error?.name || 'snapshot_event_failed' });
    return false;
  }
}

export async function readOfflineSafeSnapshot(endpoint = '') {
  if (!(await checkLiteOfflineDbAvailability())) return null;
  try {
    const db = getLiteOfflineDb();
    const snapshot = await db.safe_snapshots.get(liteSnapshotKeyForEndpoint(endpoint));
    if (snapshot) updateHealth({ lastCacheHitAt: nowIso() });
    return snapshot || null;
  } catch (error) {
    updateHealth({ cacheError: error?.name || 'snapshot_read_failed' });
    return null;
  }
}

export async function writeOfflineSafeSnapshot({
  endpoint = '',
  payload,
  checkedAt = nowIso(),
  savedAt = checkedAt,
  expiresAt = null,
  status = 'saved',
  source = 'network',
  payloadKind = 'lite-safe-read',
} = {}) {
  if (!(await checkLiteOfflineDbAvailability())) return false;
  try {
    const db = getLiteOfflineDb();
    const normalizedEndpoint = normalizeOfflineEndpoint(endpoint);
    const approximateSizeBytes = estimateSnapshotSizeBytes(payload);
    if (normalizedEndpoint.includes('/api/lite/security/profiles/') && approximateSizeBytes > LITE_SECURITY_SNAPSHOT_RETENTION_POLICY.maxProfileSnapshotBytes) {
      updateHealth({ cacheError: 'security_profile_snapshot_too_large' });
      await recordOfflineSnapshotEvent({ endpoint: normalizedEndpoint, eventType: 'snapshot_rejected', detail: 'security profile snapshot too large' });
      return false;
    }
    if (normalizedEndpoint === '/api/lite/security/history/index' && approximateSizeBytes > LITE_SECURITY_SNAPSHOT_RETENTION_POLICY.maxHistorySnapshotBytes) {
      updateHealth({ cacheError: 'security_history_snapshot_too_large' });
      await recordOfflineSnapshotEvent({ endpoint: normalizedEndpoint, eventType: 'snapshot_rejected', detail: 'security history snapshot too large' });
      return false;
    }
    const snapshot = {
      key: liteSnapshotKeyForEndpoint(normalizedEndpoint),
      endpoint: normalizedEndpoint,
      payload,
      checked_at: checkedAt,
      saved_at: savedAt,
      expires_at: expiresAt,
      schema_version: LITE_OFFLINE_SCHEMA_VERSION,
      redaction_version: LITE_OFFLINE_REDACTION_VERSION,
      source,
      payload_kind: payloadKind,
      status,
      approximate_size_bytes: approximateSizeBytes,
    };
    await db.safe_snapshots.put(snapshot);
    updateHealth({ cacheAvailable: true, cacheError: '', lastCacheWriteAt: nowIso() });
    await recordOfflineSnapshotEvent({ endpoint: normalizedEndpoint, eventType: 'snapshot_saved', detail: status });
    await pruneExpiredOfflineSnapshots();
    return true;
  } catch (error) {
    updateHealth({ cacheError: error?.name || 'snapshot_write_failed' });
    return false;
  }
}

export async function deleteOfflineSafeSnapshot(endpoint = '') {
  if (!(await checkLiteOfflineDbAvailability())) return false;
  try {
    const db = getLiteOfflineDb();
    await db.safe_snapshots.delete(liteSnapshotKeyForEndpoint(endpoint));
    await recordOfflineSnapshotEvent({ endpoint, eventType: 'snapshot_deleted', detail: 'safe snapshot removed' });
    return true;
  } catch (error) {
    updateHealth({ cacheError: error?.name || 'snapshot_delete_failed' });
    return false;
  }
}

export async function clearOfflineSafeSnapshots() {
  if (!(await checkLiteOfflineDbAvailability())) return false;
  try {
    const db = getLiteOfflineDb();
    await db.safe_snapshots.clear();
    await recordOfflineSnapshotEvent({ endpoint: '*', eventType: 'snapshots_cleared', detail: 'safe snapshots cleared' });
    return true;
  } catch (error) {
    updateHealth({ cacheError: error?.name || 'snapshots_clear_failed' });
    return false;
  }
}

export async function setOfflineCacheMeta(key, value) {
  if (!(await checkLiteOfflineDbAvailability())) return false;
  try {
    const db = getLiteOfflineDb();
    await db.ui_cache_meta.put({ key: String(key || ''), value, updated_at: nowIso() });
    return true;
  } catch (error) {
    updateHealth({ cacheError: error?.name || 'cache_meta_write_failed' });
    return false;
  }
}

export async function getOfflineCacheMeta(key) {
  if (!(await checkLiteOfflineDbAvailability())) return null;
  try {
    const db = getLiteOfflineDb();
    const record = await db.ui_cache_meta.get(String(key || ''));
    return record?.value ?? null;
  } catch (error) {
    updateHealth({ cacheError: error?.name || 'cache_meta_read_failed' });
    return null;
  }
}

export async function pruneOfflineSnapshotEvents(limit = LITE_OFFLINE_EVENT_LIMIT) {
  if (!(await checkLiteOfflineDbAvailability())) return false;
  try {
    const db = getLiteOfflineDb();
    const count = await db.snapshot_events.count();
    if (count <= limit) return true;
    const removeCount = count - limit;
    const oldest = await db.snapshot_events.orderBy('created_at').limit(removeCount).toArray();
    await db.snapshot_events.bulkDelete(oldest.map((event) => event.id));
    return true;
  } catch (error) {
    updateHealth({ cacheError: error?.name || 'snapshot_event_prune_failed' });
    return false;
  }
}


async function pruneSecurityProfileSnapshots(db) {
  const securitySnapshots = await db.safe_snapshots
    .filter((snapshot) => String(snapshot.endpoint || '').startsWith('/api/lite/security/'))
    .toArray();
  const profileSnapshots = securitySnapshots.filter((snapshot) => String(snapshot.endpoint || '').includes('/profiles/'));
  const historySnapshots = securitySnapshots.filter((snapshot) => snapshot.endpoint === '/api/lite/security/history/index');
  const oversized = securitySnapshots.filter((snapshot) => {
    const size = Number(snapshot.approximate_size_bytes || 0);
    if (String(snapshot.endpoint || '').includes('/profiles/')) return size > LITE_SECURITY_SNAPSHOT_RETENTION_POLICY.maxProfileSnapshotBytes;
    if (snapshot.endpoint === '/api/lite/security/history/index') return size > LITE_SECURITY_SNAPSHOT_RETENTION_POLICY.maxHistorySnapshotBytes;
    return false;
  });
  const profileGroups = profileSnapshots.reduce((groups, snapshot) => {
    const profile = String(snapshot.endpoint || '').split('/').pop() || 'quick';
    groups[profile] = groups[profile] || [];
    groups[profile].push(snapshot);
    return groups;
  }, {});
  const deletions = new Set(oversized.map((snapshot) => snapshot.key));
  Object.values(profileGroups).forEach((items) => {
    items
      .sort((left, right) => String(right.saved_at || '').localeCompare(String(left.saved_at || '')))
      .slice(LITE_SECURITY_SNAPSHOT_RETENTION_POLICY.profileSnapshotLimit)
      .forEach((snapshot) => deletions.add(snapshot.key));
  });
  historySnapshots
    .sort((left, right) => String(right.saved_at || '').localeCompare(String(left.saved_at || '')))
    .slice(1)
    .forEach((snapshot) => deletions.add(snapshot.key));
  if (deletions.size) await db.safe_snapshots.bulkDelete(Array.from(deletions));
  if (deletions.size) await recordOfflineSnapshotEvent({ endpoint: '/api/lite/security', eventType: 'security_snapshot_pruned', detail: `${deletions.size} Security snapshot(s) pruned` });
}

export async function pruneExpiredOfflineSnapshots({
  retentionMs = LITE_OFFLINE_RETENTION_MS,
  maxSnapshots = LITE_OFFLINE_SNAPSHOT_LIMIT,
} = {}) {
  if (!(await checkLiteOfflineDbAvailability())) return false;
  try {
    const db = getLiteOfflineDb();
    await pruneSecurityProfileSnapshots(db);
    const securityRetentionMs = Math.max(retentionMs, LITE_SECURITY_SNAPSHOT_RETENTION_POLICY.retentionMs);
    const retentionCutoff = new Date(Date.now() - retentionMs).toISOString();
    const securityCutoff = new Date(Date.now() - securityRetentionMs).toISOString();
    const oldExpired = await db.safe_snapshots
      .where('expires_at')
      .below(retentionCutoff)
      .filter((snapshot) => !String(snapshot.endpoint || '').startsWith('/api/lite/security/'))
      .toArray();
    const oldSecurityExpired = await db.safe_snapshots
      .where('expires_at')
      .below(securityCutoff)
      .filter((snapshot) => String(snapshot.endpoint || '').startsWith('/api/lite/security/'))
      .toArray();
    if (oldExpired.length) await db.safe_snapshots.bulkDelete(oldExpired.map((snapshot) => snapshot.key));
    if (oldSecurityExpired.length) await db.safe_snapshots.bulkDelete(oldSecurityExpired.map((snapshot) => snapshot.key));

    const count = await db.safe_snapshots.count();
    if (count > maxSnapshots) {
      const removeCount = count - maxSnapshots;
      const oldest = await db.safe_snapshots.orderBy('saved_at').limit(removeCount).toArray();
      await db.safe_snapshots.bulkDelete(oldest.map((snapshot) => snapshot.key));
    }
    await pruneOfflineSnapshotEvents();
    return true;
  } catch (error) {
    updateHealth({ cacheError: error?.name || 'snapshot_prune_failed' });
    return false;
  }
}

export async function estimateLiteCacheHealth() {
  const available = await checkLiteOfflineDbAvailability();
  if (!available) return getLiteOfflineCacheHealth();
  try {
    const db = getLiteOfflineDb();
    const [snapshotCount, eventCount] = await Promise.all([
      db.safe_snapshots.count(),
      db.snapshot_events.count(),
    ]);
    return updateHealth({ cacheAvailable: true, snapshotCount, eventCount, cacheError: '' });
  } catch (error) {
    return updateHealth({ cacheAvailable: false, cacheError: error?.name || 'cache_health_failed' });
  }
}

export function markLiteBackendReachable() {
  updateHealth({ lastBackendReachableAt: nowIso() });
  setOfflineCacheMeta('lastBackendReachableAt', liteOfflineCacheHealth.lastBackendReachableAt);
}

export function markLiteBackendUnreachable() {
  updateHealth({ lastBackendUnreachableAt: nowIso() });
  setOfflineCacheMeta('lastBackendUnreachableAt', liteOfflineCacheHealth.lastBackendUnreachableAt);
}

export function markLiteSnapshotRejected(endpoint = '', detail = 'unsafe snapshot rejected') {
  updateHealth({ lastCacheRejectedAt: nowIso() });
  recordOfflineSnapshotEvent({ endpoint, eventType: 'snapshot_rejected', detail });
  setOfflineCacheMeta('lastCacheRejectedAt', liteOfflineCacheHealth.lastCacheRejectedAt);
}
