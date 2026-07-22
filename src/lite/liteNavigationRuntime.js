export const LITE_SCREEN_PRELOAD_BATTERY_FLOOR = 0.2;
export const LITE_CHUNK_RECOVERY_PREFIX = 'pocketlab:lite-chunk-recovery';

function runtimeNavigator(explicitNavigator) {
  if (explicitNavigator !== undefined) return explicitNavigator;
  return typeof navigator === 'undefined' ? null : navigator;
}

function runtimeDocument(explicitDocument) {
  if (explicitDocument !== undefined) return explicitDocument;
  return typeof document === 'undefined' ? null : document;
}

export function litePreloadBlockReason({
  force = false,
  navigatorObject,
  documentObject,
} = {}) {
  if (force) return '';
  const currentNavigator = runtimeNavigator(navigatorObject);
  const currentDocument = runtimeDocument(documentObject);

  if (currentNavigator?.onLine === false) return 'offline';
  if (currentDocument?.visibilityState === 'hidden') return 'hidden_document';

  const connection = currentNavigator?.connection
    || currentNavigator?.mozConnection
    || currentNavigator?.webkitConnection
    || null;
  if (connection?.saveData) return 'data_saver';

  const effectiveType = String(connection?.effectiveType || '').toLowerCase();
  if (effectiveType === '2g' || effectiveType === 'slow-2g') return 'slow_connection';
  return '';
}

async function batteryAllowsPreload(currentNavigator, force) {
  if (force || typeof currentNavigator?.getBattery !== 'function') return true;
  try {
    const battery = await currentNavigator.getBattery();
    if (!battery || battery.charging) return true;
    return Number(battery.level) > LITE_SCREEN_PRELOAD_BATTERY_FLOOR;
  } catch {
    return true;
  }
}

export function createLiteScreenPreloader({
  loaders,
  navigatorObject,
  documentObject,
  diagnostic = () => {},
} = {}) {
  const loaderMap = loaders instanceof Map ? loaders : new Map(Object.entries(loaders || {}));
  const inFlight = new Map();
  const loaded = new Set();

  function preload(screenId, options = {}) {
    const normalizedId = String(screenId || '').trim().toLowerCase();
    const loader = loaderMap.get(normalizedId);
    if (typeof loader !== 'function') {
      return Promise.resolve({ preloaded: false, reason: 'not_lazy', screenId: normalizedId });
    }
    if (loaded.has(normalizedId)) {
      return Promise.resolve({ preloaded: false, reason: 'already_loaded', screenId: normalizedId });
    }
    if (inFlight.has(normalizedId)) return inFlight.get(normalizedId);

    const force = Boolean(options.force);
    const blockedBy = litePreloadBlockReason({
      force,
      navigatorObject: runtimeNavigator(options.navigatorObject ?? navigatorObject),
      documentObject: runtimeDocument(options.documentObject ?? documentObject),
    });
    if (blockedBy) {
      return Promise.resolve({ preloaded: false, reason: blockedBy, screenId: normalizedId });
    }

    const currentNavigator = runtimeNavigator(options.navigatorObject ?? navigatorObject);
    const tracked = (async () => {
      if (!(await batteryAllowsPreload(currentNavigator, force))) {
        return { preloaded: false, reason: 'low_battery', screenId: normalizedId };
      }
      try {
        await loader();
        loaded.add(normalizedId);
        return { preloaded: true, reason: 'loaded', screenId: normalizedId };
      } catch {
        diagnostic('screen_preload_failed', { screenId: normalizedId });
        return { preloaded: false, reason: 'load_failed', screenId: normalizedId };
      }
    })().finally(() => {
      inFlight.delete(normalizedId);
    });

    inFlight.set(normalizedId, tracked);
    return tracked;
  }

  return Object.freeze({
    preload,
    isLoaded: (screenId) => loaded.has(String(screenId || '').trim().toLowerCase()),
    isInFlight: (screenId) => inFlight.has(String(screenId || '').trim().toLowerCase()),
  });
}

export function prefersLiteReducedMotion(windowObject = typeof window === 'undefined' ? null : window) {
  try {
    return Boolean(windowObject?.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches);
  } catch {
    return false;
  }
}

export function startLiteViewTransition(commit, {
  documentObject = typeof document === 'undefined' ? null : document,
  reducedMotion = false,
  previousTransition = null,
} = {}) {
  let committed = false;
  const safeCommit = () => {
    if (committed) return;
    committed = true;
    commit();
  };

  try {
    previousTransition?.skipTransition?.();
  } catch {
    // A prior transition is optional and must never block navigation.
  }

  if (reducedMotion || typeof documentObject?.startViewTransition !== 'function') {
    safeCommit();
    return { started: false, reason: reducedMotion ? 'reduced_motion' : 'unsupported', transition: null };
  }

  try {
    const transition = documentObject.startViewTransition(safeCommit);
    return { started: true, reason: 'started', transition: transition || null };
  } catch {
    safeCommit();
    return { started: false, reason: 'failed_safe', transition: null };
  }
}

export function isLiteChunkLoadError(error) {
  const name = String(error?.name || '').toLowerCase();
  const message = String(error?.message || error || '').toLowerCase();
  return name.includes('chunkloaderror')
    || message.includes('failed to fetch dynamically imported module')
    || message.includes('error loading dynamically imported module')
    || message.includes('loading chunk')
    || message.includes('importing a module script failed')
    || message.includes('css chunk load failed');
}

export function createLiteChunkRecoveryController({
  buildId = 'development',
  storage = typeof sessionStorage === 'undefined' ? null : sessionStorage,
  locationObject = typeof window === 'undefined' ? null : window.location,
} = {}) {
  const guardKey = `${LITE_CHUNK_RECOVERY_PREFIX}:${String(buildId || 'development')}`;

  function attempt(error) {
    if (!isLiteChunkLoadError(error) || !storage || typeof locationObject?.reload !== 'function') return false;
    try {
      if (storage.getItem(guardKey) === '1') return false;
      storage.setItem(guardKey, '1');
      locationObject.reload();
      return true;
    } catch {
      return false;
    }
  }

  return Object.freeze({ attempt, guardKey });
}
