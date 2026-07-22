import { LITE_WORKBOX_CACHE_NAMES } from './liteOfflineReadPolicy.js';
import { hasLiteLiveOperation } from './litePollingPolicy.js';

export const LITE_SERVICE_WORKER_UPDATE_EVENT = 'pocketlab:lite-service-worker-update';
export const LITE_SERVICE_WORKER_RUNTIME_VERSION = 'n6a-safe-read-v2';
export const LITE_NAVIGATION_PRELOAD_POLICY = 'guarded-progressive-enhancement';

let pendingUpdate = null;
const updateBlockers = new Set();

function safeBlockerId(value = '') {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9:_-]+/g, '-')
    .slice(0, 80);
}

function isRiskyWorkflowQueryKey(queryKey = []) {
  const key = Array.isArray(queryKey) ? queryKey.map((part) => String(part || '').toLowerCase()) : [];
  if (key[0] !== 'lite') return false;
  if (key[1] === 'fleet') return key.length === 2;
  if (key[1] === 'security') return !['history', 'evidence-summary'].includes(key[2] || '');
  if (key[1] === 'recovery') return !['history', 'operations'].includes(key[2] || '');
  if (key[1] === 'app') return key[key.length - 1] === 'actions';
  return key[1] === 'apps' && key[2] === 'lifecycle';
}

export function liteQueryCacheHasRiskyWorkflow(queries = []) {
  return (Array.isArray(queries) ? queries : []).some((query) => {
    const queryKey = query?.queryKey || query?.options?.queryKey || [];
    if (!isRiskyWorkflowQueryKey(queryKey)) return false;
    const data = query?.state?.data;
    if (!data || data?.__liteSnapshot?.expired || data?.__liteSnapshot?.isExpired) return false;
    return hasLiteLiveOperation(data);
  });
}

function emitUpdateState() {
  if (typeof window === 'undefined' || typeof window.dispatchEvent !== 'function') return;
  window.dispatchEvent(new CustomEvent(LITE_SERVICE_WORKER_UPDATE_EVENT, {
    detail: getLiteServiceWorkerUpdateState(),
  }));
}

export function getLiteServiceWorkerUpdateState() {
  return {
    runtime_version: LITE_SERVICE_WORKER_RUNTIME_VERSION,
    update_ready: Boolean(pendingUpdate),
    update_blocked: updateBlockers.size > 0,
    blocker_count: updateBlockers.size,
  };
}

export function announceLiteServiceWorkerUpdate(applyUpdate) {
  if (typeof applyUpdate !== 'function') return false;
  pendingUpdate = applyUpdate;
  emitUpdateState();
  return true;
}

export function setLiteServiceWorkerUpdateBlocker(blockerId, active) {
  const id = safeBlockerId(blockerId);
  if (!id) return getLiteServiceWorkerUpdateState();
  const before = updateBlockers.size;
  if (active) updateBlockers.add(id);
  else updateBlockers.delete(id);
  if (before !== updateBlockers.size) emitUpdateState();
  return getLiteServiceWorkerUpdateState();
}

export function subscribeLiteServiceWorkerUpdates(listener) {
  if (typeof listener !== 'function') return () => {};
  const onUpdate = (event) => listener(event?.detail || getLiteServiceWorkerUpdateState());
  listener(getLiteServiceWorkerUpdateState());
  if (typeof window === 'undefined') return () => {};
  window.addEventListener(LITE_SERVICE_WORKER_UPDATE_EVENT, onUpdate);
  return () => window.removeEventListener(LITE_SERVICE_WORKER_UPDATE_EVENT, onUpdate);
}

export async function applyLiteServiceWorkerUpdate() {
  if (!pendingUpdate || updateBlockers.size) return false;
  const apply = pendingUpdate;
  try {
    await apply();
    pendingUpdate = null;
    emitUpdateState();
    return true;
  } catch {
    emitUpdateState();
    return false;
  }
}

export async function getLiteNavigationPreloadDiagnostics(navigatorObject = globalThis.navigator) {
  const base = {
    runtime_version: LITE_SERVICE_WORKER_RUNTIME_VERSION,
    navigation_preload_supported: false,
    navigation_preload_enabled: false,
  };
  try {
    const ready = navigatorObject?.serviceWorker?.ready;
    if (!ready?.then) return base;
    const registration = await ready;
    if (!registration?.navigationPreload?.getState) return base;
    const state = await registration.navigationPreload.getState();
    return {
      ...base,
      navigation_preload_supported: true,
      navigation_preload_enabled: Boolean(state?.enabled),
    };
  } catch {
    return base;
  }
}


export async function pruneLiteRuntimeCaches(cacheStorage = globalThis.caches) {
  const result = { checked: 0, deleted: 0, failed: 0 };
  if (!cacheStorage?.keys || !cacheStorage?.delete) return result;
  const currentNames = Object.values(LITE_WORKBOX_CACHE_NAMES);
  const versionedPattern = /^(pocketlab-lite-(?:app-shell|safe-read-api|static-assets|icons-images))-v(\d+)$/;
  const currentVersions = new Map(currentNames.map((name) => {
    const match = versionedPattern.exec(String(name));
    return match ? [match[1], Number(match[2])] : ['', 0];
  }).filter(([family]) => family));
  try {
    const names = await cacheStorage.keys();
    const stale = names.filter((name) => {
      const match = versionedPattern.exec(String(name));
      if (!match || !currentVersions.has(match[1])) return false;
      return Number(match[2]) < currentVersions.get(match[1]) - 1;
    }).slice(0, 8);
    result.checked = stale.length;
    for (const name of stale) {
      try {
        if (await cacheStorage.delete(name)) result.deleted += 1;
      } catch {
        result.failed += 1;
      }
    }
  } catch {
    result.failed += 1;
  }
  return result;
}

export function resetLiteServiceWorkerRuntimeForTests() {
  pendingUpdate = null;
  updateBlockers.clear();
}
