import { liteApi } from '../../lib/liteApi.js';
import { liteQueryKeys } from '../../lib/liteQueryClient.js';
import { selectSecurityPollingPolicyView } from '../../lib/liteViewModels.js';

export const SECURITY_INSTANT_FEEL_FRONTEND_BUNDLE = 'security-group1-f4-f5-f6-f13';
export const SECURITY_SUMMARY_IDLE_STALE_TIME_MS = 180_000;
export const SECURITY_SUMMARY_ACTIVE_STALE_TIME_MS = 2_000;
export const SECURITY_SUMMARY_GC_TIME_MS = 45 * 60_000;
export const SECURITY_DETAILS_IDLE_STALE_TIME_MS = 60_000;
export const SECURITY_DETAILS_GC_TIME_MS = 30 * 60_000;
export const SECURITY_PREFETCH_COOLDOWN_MS = 60_000;
export const SECURITY_PREFETCH_SETTLE_MS = 1_200;
export const SECURITY_PREFETCH_GUARD_TEXT = 'online saveData effectiveType document.visibilityState backend healthy active scan';

let lastSecuritySummaryPrefetchAt = 0;
let securityDetailsPreloadPromise = null;
let securityHistoryPreloadPromise = null;
let securityManagePreloadPromise = null;

function securityConnection() {
  if (typeof navigator === 'undefined') return null;
  return navigator.connection || navigator.mozConnection || navigator.webkitConnection || null;
}

function documentAllowsPrefetch() {
  return typeof document === 'undefined' || document.visibilityState !== 'hidden';
}

function browserOnline() {
  return typeof navigator === 'undefined' || navigator.onLine !== false;
}

function connectionAllowsPrefetch() {
  const connection = securityConnection();
  if (!connection) return true;
  if (connection.saveData) return false;
  const effectiveType = String(connection.effectiveType || '').toLowerCase();
  return !['slow-2g', '2g'].includes(effectiveType);
}

async function batteryAllowsPrefetch(force = false) {
  if (force || typeof navigator === 'undefined' || typeof navigator.getBattery !== 'function') return true;
  try {
    const battery = await navigator.getBattery();
    if (!battery) return true;
    if (battery.charging) return true;
    return Number(battery.level) > 0.2;
  } catch {
    return true;
  }
}

export function securitySummaryStaleTime(payload = {}) {
  const policy = selectSecurityPollingPolicyView(payload || {});
  return policy.live ? SECURITY_SUMMARY_ACTIVE_STALE_TIME_MS : SECURITY_SUMMARY_IDLE_STALE_TIME_MS;
}

export function securityDetailsStaleTime(payload = {}) {
  const policy = selectSecurityPollingPolicyView(payload || {});
  return policy.live ? SECURITY_SUMMARY_ACTIVE_STALE_TIME_MS : SECURITY_DETAILS_IDLE_STALE_TIME_MS;
}

export function canPrefetchSecuritySummary({ backendHealthy = true, activeScan = false, force = false } = {}) {
  if (!force && activeScan) return false;
  if (!backendHealthy) return false;
  if (!browserOnline()) return false;
  if (!documentAllowsPrefetch()) return false;
  if (!connectionAllowsPrefetch()) return false;
  return true;
}

export async function prefetchSecuritySummary(queryClient, options = {}) {
  if (!queryClient || typeof queryClient.prefetchQuery !== 'function') return { prefetched: false, reason: 'missing_query_client' };
  const now = Date.now();
  const force = Boolean(options.force);
  if (!force && now - lastSecuritySummaryPrefetchAt < SECURITY_PREFETCH_COOLDOWN_MS) {
    return { prefetched: false, reason: 'cooldown' };
  }
  if (!canPrefetchSecuritySummary(options)) return { prefetched: false, reason: 'guarded' };
  if (!(await batteryAllowsPrefetch(force))) return { prefetched: false, reason: 'battery' };

  lastSecuritySummaryPrefetchAt = now;
  try {
    await queryClient.prefetchQuery({
      queryKey: liteQueryKeys.security(),
      queryFn: liteApi.securitySummary,
      staleTime: SECURITY_SUMMARY_IDLE_STALE_TIME_MS,
      gcTime: SECURITY_SUMMARY_GC_TIME_MS,
    });
    return { prefetched: true, reason: 'security_summary' };
  } catch (error) {
    return { prefetched: false, reason: 'prefetch_failed', error };
  }
}

export function preloadSecurityDetails() {
  if (!securityDetailsPreloadPromise) {
    securityDetailsPreloadPromise = import('./SecurityProgressiveDetailsLazy.jsx').catch(() => null);
  }
  return securityDetailsPreloadPromise;
}

export function preloadSecurityHistory() {
  if (!securityHistoryPreloadPromise) {
    securityHistoryPreloadPromise = Promise.all([
      import('./SecurityHistoryLazy.jsx').catch(() => null),
      import('../components/LiteHistorySection.jsx').catch(() => null),
    ]).catch(() => null);
  }
  return securityHistoryPreloadPromise;
}

export function preloadSecurityManageChunks() {
  if (!securityManagePreloadPromise) {
    securityManagePreloadPromise = Promise.allSettled([
      preloadSecurityDetails(),
      preloadSecurityHistory(),
    ]).catch(() => null);
  }
  return securityManagePreloadPromise;
}

export async function prefetchSecurityManageOnIntent(queryClient, options = {}) {
  preloadSecurityManageChunks();
  if (!queryClient || typeof queryClient.prefetchQuery !== 'function') return { prefetched: false, reason: 'missing_query_client' };
  if (!canPrefetchSecuritySummary(options)) return { prefetched: false, reason: 'guarded' };
  if (!(await batteryAllowsPrefetch(Boolean(options.force)))) return { prefetched: false, reason: 'battery' };
  try {
    await queryClient.prefetchQuery({
      queryKey: liteQueryKeys.securityDetails(),
      queryFn: liteApi.securityDetails,
      staleTime: SECURITY_DETAILS_IDLE_STALE_TIME_MS,
      gcTime: SECURITY_DETAILS_GC_TIME_MS,
    });
    return { prefetched: true, reason: 'security_details' };
  } catch (error) {
    return { prefetched: false, reason: 'prefetch_failed', error };
  }
}
