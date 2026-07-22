import { LITE_WORKBOX_CACHE_NAMES } from './liteOfflineReadPolicy.js';
import { hasLiteLiveOperation } from './litePollingPolicy.js';

export const LITE_SERVICE_WORKER_UPDATE_EVENT = 'pocketlab:lite-service-worker-update';
export const LITE_SERVICE_WORKER_RUNTIME_VERSION = 'n6b-native-install-v1';
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


export const LITE_SERVICE_WORKER_RELOAD_GUARD_KEY = 'pocketlab:lite-sw-controller-reload';
export const LITE_SERVICE_WORKER_RELOAD_GUARD_MS = 2 * 60 * 1000;

function safeBuildId(value = '') {
  return String(value || 'development')
    .trim()
    .replace(/[^a-zA-Z0-9._-]+/g, '-')
    .slice(0, 100) || 'development';
}

export function isLiteTextEntryElement(element) {
  const tagName = String(element?.tagName || '').toLowerCase();
  return tagName === 'input' || tagName === 'textarea' || tagName === 'select' || element?.isContentEditable === true;
}

export function createLiteControlledServiceWorkerUpdate({
  updateServiceWorker,
  navigatorObject = globalThis.navigator,
  locationObject = globalThis.location,
  sessionStorageObject = globalThis.sessionStorage,
  buildId = 'development',
  timeoutMs = 15_000,
  now = () => Date.now(),
} = {}) {
  const normalizedBuildId = safeBuildId(buildId);
  return async function applyControlledUpdate() {
    if (typeof updateServiceWorker !== 'function') throw new Error('service_worker_update_unavailable');
    const serviceWorker = navigatorObject?.serviceWorker;
    if (!serviceWorker?.addEventListener) throw new Error('service_worker_controller_unavailable');
    try {
      const stored = JSON.parse(sessionStorageObject?.getItem?.(LITE_SERVICE_WORKER_RELOAD_GUARD_KEY) || 'null');
      const appliedAt = Number(stored?.applied_at || 0);
      if (stored?.build_id === normalizedBuildId && appliedAt > 0 && Number(now()) - appliedAt < LITE_SERVICE_WORKER_RELOAD_GUARD_MS) {
        return false;
      }
    } catch {
      // Continue without persistence; the once-only listener still bounds reloads in this page.
    }

    return new Promise((resolve, reject) => {
      let settled = false;
      const finish = (callback) => {
        if (settled) return;
        settled = true;
        globalThis.clearTimeout?.(timer);
        serviceWorker.removeEventListener?.('controllerchange', onControllerChange);
        callback();
      };
      const onControllerChange = () => finish(() => {
        try {
          sessionStorageObject?.setItem?.(LITE_SERVICE_WORKER_RELOAD_GUARD_KEY, JSON.stringify({
            build_id: normalizedBuildId,
            applied_at: Number(now()),
          }));
        } catch {
          // Session storage is a best-effort reload-loop fence.
        }
        resolve(true);
        try {
          locationObject?.reload?.();
        } catch {
          // Controller activation succeeded; a manual refresh remains available.
        }
      });
      const timer = globalThis.setTimeout?.(
        () => finish(() => reject(new Error('service_worker_controller_timeout'))),
        Math.max(1_000, Math.min(30_000, Number(timeoutMs) || 15_000)),
      );

      serviceWorker.addEventListener('controllerchange', onControllerChange, { once: true });
      Promise.resolve(updateServiceWorker(false)).catch((error) => {
        finish(() => reject(error instanceof Error ? error : new Error('service_worker_update_failed')));
      });
    });
  };
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
