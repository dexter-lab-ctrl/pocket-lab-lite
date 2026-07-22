import { hasLiteLiveOperation } from './litePollingPolicy.js';
import {
  createLiteScreenLaunchUrl,
  normalizeLiteScreenId,
  parseLiteScreenLaunch,
} from '../lite/liteNavigationMetadata.js';

export const LITE_INSTALL_DISMISSAL_KEY = 'pocketlab:lite-install-dismissed-until';
export const LITE_INSTALL_PROMPT_COOLDOWN_MS = 7 * 24 * 60 * 60 * 1000;
export const LITE_INSTALL_FAILURE_COOLDOWN_MS = 24 * 60 * 60 * 1000;
export const LITE_BADGE_MAX_COUNT = 9;
export const LITE_BADGE_FRESHNESS_MS = 2 * 60 * 1000;

const SAFE_SHARE_TITLE = 'Pocket Lab Lite';
const SAFE_SHARE_TEXT = 'Pocket Lab Lite — self-hosted workspace.';
const SAFE_WEB_PROTOCOLS = new Set(['https:', 'http:']);
const BADGE_DOMAINS = new Set(['fleet', 'security', 'recovery', 'apps', 'app']);

function finiteTimestamp(value) {
  const timestamp = Number(value);
  return Number.isFinite(timestamp) && timestamp > 0 ? timestamp : 0;
}

function safeStorageNumber(storage, key) {
  try {
    return finiteTimestamp(storage?.getItem?.(key));
  } catch {
    return 0;
  }
}

export function isLiteStandaloneDisplay({
  windowObject = globalThis.window,
  navigatorObject = globalThis.navigator,
} = {}) {
  try {
    return Boolean(
      navigatorObject?.standalone === true
      || windowObject?.matchMedia?.('(display-mode: standalone)')?.matches
      || windowObject?.matchMedia?.('(display-mode: window-controls-overlay)')?.matches
      || windowObject?.matchMedia?.('(display-mode: minimal-ui)')?.matches,
    );
  } catch {
    return Boolean(navigatorObject?.standalone === true);
  }
}

export function liteInstallCooldownUntil(storage = globalThis.localStorage) {
  return safeStorageNumber(storage, LITE_INSTALL_DISMISSAL_KEY);
}

export function recordLiteInstallCooldown({
  storage = globalThis.localStorage,
  now = Date.now(),
  durationMs = LITE_INSTALL_PROMPT_COOLDOWN_MS,
} = {}) {
  const boundedDuration = Math.max(60_000, Math.min(30 * 24 * 60 * 60 * 1000, Number(durationMs) || 0));
  const until = Math.max(0, Number(now) || Date.now()) + boundedDuration;
  try {
    storage?.setItem?.(LITE_INSTALL_DISMISSAL_KEY, String(until));
    return until;
  } catch {
    return 0;
  }
}

export function clearLiteInstallCooldown(storage = globalThis.localStorage) {
  try {
    storage?.removeItem?.(LITE_INSTALL_DISMISSAL_KEY);
    return true;
  } catch {
    return false;
  }
}

export function canOfferLiteInstall({
  promptAvailable = false,
  installed = false,
  workflowActive = false,
  criticalOverlayOpen = false,
  storage = globalThis.localStorage,
  now = Date.now(),
} = {}) {
  if (!promptAvailable || installed || workflowActive || criticalOverlayOpen) return false;
  const cooldownUntil = liteInstallCooldownUntil(storage);
  return !cooldownUntil || cooldownUntil <= Number(now || Date.now());
}

export async function requestLiteInstall(promptEvent, {
  storage = globalThis.localStorage,
  now = Date.now(),
} = {}) {
  if (!promptEvent || typeof promptEvent.prompt !== 'function') return { status: 'unavailable' };
  try {
    await promptEvent.prompt();
    const choice = await promptEvent.userChoice;
    const outcome = String(choice?.outcome || '').toLowerCase();
    if (outcome === 'accepted') {
      return { status: 'accepted_pending_confirmation' };
    }
    recordLiteInstallCooldown({ storage, now, durationMs: LITE_INSTALL_PROMPT_COOLDOWN_MS });
    return { status: 'dismissed' };
  } catch {
    recordLiteInstallCooldown({ storage, now, durationMs: LITE_INSTALL_FAILURE_COOLDOWN_MS });
    return { status: 'failed' };
  }
}

function badgeDomainFromQueryKey(queryKey = []) {
  const key = Array.isArray(queryKey) ? queryKey.map((part) => String(part || '').toLowerCase()) : [];
  if (key[0] !== 'lite' || !BADGE_DOMAINS.has(key[1])) return '';
  if (key[1] === 'app') return `app:${String(key[2] || 'unknown').slice(0, 40)}`;
  return key[1];
}

function queryIsFreshNetworkState(query, now, maxAgeMs) {
  const data = query?.state?.data;
  if (!data || query?.state?.error) return false;
  const meta = data?.__liteSnapshot || null;
  if (meta && (meta.source !== 'network' || meta.stale || meta.expired || meta.isExpired || meta.cached)) return false;
  const updatedAt = finiteTimestamp(query?.state?.dataUpdatedAt)
    || finiteTimestamp(new Date(meta?.checkedAt || meta?.savedAt || 0).getTime());
  return Boolean(updatedAt && Number(now) - updatedAt <= maxAgeMs);
}

export function deriveLiteAppBadgeState(queries = [], {
  online = true,
  now = Date.now(),
  maxAgeMs = LITE_BADGE_FRESHNESS_MS,
  maxCount = LITE_BADGE_MAX_COUNT,
} = {}) {
  if (!online) return Object.freeze({ count: 0, active_domains: Object.freeze([]), source: 'offline-cleared' });
  const activeDomains = new Set();
  for (const query of Array.isArray(queries) ? queries : []) {
    const domain = badgeDomainFromQueryKey(query?.queryKey || query?.options?.queryKey || []);
    if (!domain || !queryIsFreshNetworkState(query, Number(now), Math.max(10_000, Number(maxAgeMs) || 0))) continue;
    if (hasLiteLiveOperation(query?.state?.data)) activeDomains.add(domain);
  }
  const domains = [...activeDomains].sort().slice(0, Math.max(1, Number(maxCount) || LITE_BADGE_MAX_COUNT));
  return Object.freeze({
    count: Math.min(Math.max(0, Number(maxCount) || LITE_BADGE_MAX_COUNT), domains.length),
    active_domains: Object.freeze(domains),
    source: domains.length ? 'fresh-current-state' : 'clear',
  });
}

export async function applyLiteAppBadge(navigatorObject = globalThis.navigator, count = 0, previousCount = null) {
  const boundedCount = Math.max(0, Math.min(LITE_BADGE_MAX_COUNT, Number(count) || 0));
  if (previousCount === boundedCount) return { applied: false, count: boundedCount, reason: 'unchanged' };
  try {
    if (boundedCount > 0 && typeof navigatorObject?.setAppBadge === 'function') {
      await navigatorObject.setAppBadge(boundedCount);
      return { applied: true, count: boundedCount, reason: 'set' };
    }
    if (boundedCount === 0 && typeof navigatorObject?.clearAppBadge === 'function') {
      await navigatorObject.clearAppBadge();
      return { applied: true, count: 0, reason: 'cleared' };
    }
    return { applied: false, count: boundedCount, reason: 'unsupported' };
  } catch {
    return { applied: false, count: boundedCount, reason: 'failed' };
  }
}

function safeShareOrigin(origin) {
  try {
    const parsed = new URL(String(origin || ''));
    if (!SAFE_WEB_PROTOCOLS.has(parsed.protocol) || parsed.username || parsed.password) return '';
    return parsed.origin;
  } catch {
    return '';
  }
}

export function buildLiteSafeSharePayload({
  origin = globalThis.location?.origin,
  screenId = 'home',
} = {}) {
  const safeOrigin = safeShareOrigin(origin);
  if (!safeOrigin) return null;
  const safeScreenId = normalizeLiteScreenId(screenId);
  return Object.freeze({
    title: SAFE_SHARE_TITLE,
    text: SAFE_SHARE_TEXT,
    url: `${safeOrigin}${createLiteScreenLaunchUrl(safeScreenId)}`,
  });
}

export async function shareLiteSafeWorkspace({
  navigatorObject = globalThis.navigator,
  origin = globalThis.location?.origin,
  screenId = 'home',
} = {}) {
  const payload = buildLiteSafeSharePayload({ origin, screenId });
  if (!payload) return { status: 'blocked' };
  if (typeof navigatorObject?.share === 'function') {
    try {
      await navigatorObject.share(payload);
      return { status: 'shared' };
    } catch (error) {
      if (String(error?.name || '') === 'AbortError') return { status: 'cancelled' };
    }
  }
  try {
    if (typeof navigatorObject?.clipboard?.writeText === 'function') {
      await navigatorObject.clipboard.writeText(payload.url);
      return { status: 'copied' };
    }
  } catch {
    return { status: 'failed' };
  }
  return { status: 'unavailable' };
}

export function collectLiteInstallDiagnostics({
  windowObject = globalThis.window,
  navigatorObject = globalThis.navigator,
  promptAvailable = false,
  installed = isLiteStandaloneDisplay({ windowObject, navigatorObject }),
  updateWaiting = false,
  locationObject = globalThis.location,
} = {}) {
  const launch = parseLiteScreenLaunch(locationObject);
  return Object.freeze({
    manifest_configured: true,
    service_worker_controlled: Boolean(navigatorObject?.serviceWorker?.controller),
    secure_context: Boolean(windowObject?.isSecureContext),
    standalone_mode: Boolean(installed),
    install_prompt_available: Boolean(promptAvailable),
    app_installed: Boolean(installed),
    update_waiting: Boolean(updateWaiting),
    shortcut_launch_parsed: Boolean(launch.requested_screen_id),
    shortcut_launch_valid: Boolean(launch.valid),
    navigation_preload_check_available: Boolean(navigatorObject?.serviceWorker?.ready),
    badge_api_supported: Boolean(navigatorObject?.setAppBadge || navigatorObject?.clearAppBadge),
    share_api_supported: Boolean(navigatorObject?.share),
  });
}
