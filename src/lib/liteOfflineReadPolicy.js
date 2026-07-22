export const LITE_SAFE_READ_CACHE_VERSION = 2;
export const LITE_SAFE_HISTORY_CACHE_SCHEMA_VERSION = 2;
export const LITE_SAFE_READ_NONCE_HEADER = 'X-PocketLab-Read-Nonce';

export const LITE_WORKBOX_CACHE_NAMES = Object.freeze({
  appShell: `pocketlab-lite-app-shell-v${LITE_SAFE_READ_CACHE_VERSION}`,
  safeReads: `pocketlab-lite-safe-read-api-v${LITE_SAFE_READ_CACHE_VERSION}`,
  staticAssets: 'pocketlab-lite-static-assets-v3',
  images: 'pocketlab-lite-icons-images-v2',
});

export const LITE_SAFE_RUNTIME_READ_MAX_AGE_SECONDS = 5 * 60;
export const LITE_SAFE_RUNTIME_READ_MAX_ENTRIES = 24;

const SAFE_RUNTIME_READ_PATHS = Object.freeze([
  /^\/api\/lite\/status$/,
  /^\/api\/lite\/catalog$/,
  /^\/api\/lite\/revisions$/,
  /^\/api\/lite\/apps\/lifecycle$/,
  /^\/api\/lite\/apps\/photoprism\/actions$/,
  /^\/api\/lite\/security\/(?:summary|freshness|progress)$/,
  /^\/api\/lite\/security\/profiles\/(?:quick|full|app)$/,
  /^\/api\/lite\/security\/history$/,
  /^\/api\/lite\/recovery\/(?:summary|backups)$/,
]);

const PWA_NAVIGATION_DENYLIST = /^\/(?:api|terminal|apps|gitea|docs)(?:\/|$)|^\/openapi\.json$/;
const UNSAFE_READ_PATH_PART = /(?:bootstrap|invite|token|secret|credential|receipt|evidence|raw|logs?|command-payload)/i;
let safeReadNonceCounter = 0;

export function createLiteSafeReadNonce(cryptoObject = globalThis.crypto) {
  safeReadNonceCounter = (safeReadNonceCounter + 1) % 0x7fffffff;
  let randomPart = '';
  try {
    const values = new Uint32Array(2);
    cryptoObject?.getRandomValues?.(values);
    randomPart = `${values[0].toString(36)}${values[1].toString(36)}`;
  } catch {
    randomPart = '';
  }
  const timePart = Date.now().toString(36);
  return `plr-${timePart}-${safeReadNonceCounter.toString(36)}-${randomPart || 'fallback'}`.slice(0, 64);
}

export function classifyLiteSafeReadResponse({
  requestNonce = '',
  responseNonce = '',
  serviceWorkerControlled = false,
} = {}) {
  if (!serviceWorkerControlled || !requestNonce) return 'network';
  return String(responseNonce || '') === String(requestNonce) ? 'network' : 'http-cache';
}

function normalizedPath(value = '') {
  try {
    return new URL(value, 'http://127.0.0.1').pathname;
  } catch {
    return String(value || '').split('?')[0];
  }
}

export function isLiteSafeRuntimeRead({ method = 'GET', path = '' } = {}) {
  const pathname = normalizedPath(path);
  if (String(method || 'GET').toUpperCase() !== 'GET') return false;
  if (UNSAFE_READ_PATH_PART.test(pathname)) return false;
  return SAFE_RUNTIME_READ_PATHS.some((pattern) => pattern.test(pathname));
}

export function isLitePwaNavigationPath(path = '/') {
  const pathname = normalizedPath(path);
  return !PWA_NAVIGATION_DENYLIST.test(pathname);
}

export function liteSafeHistorySchemaCompatible(payload = {}) {
  return Number(payload?.cache_schema_version || 0) === LITE_SAFE_HISTORY_CACHE_SCHEMA_VERSION;
}

export function liteOfflineReadDiagnostics({
  endpoint = '',
  savedRowCount = 0,
  savedAt = '',
  source = 'none',
  pruningStatus = 'idle',
  quotaFailureType = '',
} = {}) {
  return {
    cache_version: LITE_SAFE_READ_CACHE_VERSION,
    history_schema_version: LITE_SAFE_HISTORY_CACHE_SCHEMA_VERSION,
    endpoint_kind: normalizedPath(endpoint).includes('/history') || normalizedPath(endpoint).includes('/backups') ? 'bounded-history' : 'safe-read',
    saved_row_count: Math.max(0, Number(savedRowCount) || 0),
    saved_at: String(savedAt || '').slice(0, 40),
    source: ['network', 'cache', 'http-cache', 'none'].includes(source) ? source : 'none',
    pruning_status: String(pruningStatus || 'idle').slice(0, 40),
    quota_failure_type: String(quotaFailureType || '').slice(0, 80),
  };
}
