import { useCallback, useEffect, useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  attachFreshSnapshotMeta,
  describeLiteSnapshot,
  isSafeLiteSnapshotPath,
  markLiteSnapshotBackendUnreachable,
  normalizeLiteSnapshotPath,
  readLiteSnapshot,
  readLiteSnapshotAsync,
  snapshotAgeLabel,
  writeLiteSnapshot,
} from '../lib/liteSafeSnapshots.js';
import { hasLiteLiveOperation, isLiteDocumentVisible, liteQueryPollingInterval } from '../lib/litePollingPolicy.js';
import { liteQueryKeys, liteQueryPaths } from '../lib/liteQueryClient.js';
import { isLiteNotModified, liteApi } from '../lib/liteApi.js';
import { publishLiteLifecycleDiagnostics, reconcileLiteSecurityProgress } from '../lib/liteLifecycleDiagnostics.js';

const UNSAFE_METHOD_PATTERN = /^(POST|PUT|PATCH|DELETE)$/i;
const UNSAFE_PATH_PATTERN = /bootstrap|invite|token|secret|password|evidence|receipt|debug|raw/i;

function normalizeQueryPath(path = '') {
  return normalizeLiteSnapshotPath(path);
}

function isUnsafeSnapshotRequest(path = '', method = 'GET') {
  return UNSAFE_METHOD_PATTERN.test(String(method || 'GET')) || UNSAFE_PATH_PATTERN.test(normalizeQueryPath(path));
}

function snapshotMeta(data, refreshing = false) {
  const meta = data?.__liteSnapshot || null;
  if (!meta) return null;
  return { ...meta, refreshing: Boolean(refreshing && !(meta.cached || meta.stale || meta.source === 'cache')) };
}

function isSavedSnapshot(data) {
  const meta = data?.__liteSnapshot;
  return Boolean(meta?.cached || meta?.stale || meta?.source === 'cache');
}

function initialDataUpdatedAt(data) {
  const value = data?.__liteSnapshot?.checkedAt || data?.__liteSnapshot?.savedAt;
  const timestamp = value ? new Date(value).getTime() : 0;
  return Number.isFinite(timestamp) ? timestamp : undefined;
}

function defaultQueryKey(path, explicitKey) {
  if (explicitKey) return explicitKey;
  return liteQueryKeys.resource(normalizeQueryPath(path || 'unknown'));
}

function preserveSelectedSnapshotMeta(input, output) {
  if (!input?.__liteSnapshot || !output || typeof output !== 'object' || Array.isArray(output) || output.__liteSnapshot) return output;
  return { ...output, __liteSnapshot: input.__liteSnapshot };
}

function applyLiteQuerySelector(select, data) {
  if (typeof select !== 'function') return data;
  return preserveSelectedSnapshotMeta(data, select(data));
}

async function queryWithSafeSnapshotFallback({ path, queryFn, method = 'GET', snapshotSelect }) {
  const safePath = isSafeLiteSnapshotPath(path) && !isUnsafeSnapshotRequest(path, method);
  try {
    const data = await queryFn();
    if (isLiteNotModified(data)) return data;
    if (safePath && data && typeof data === 'object' && !data.__liteSnapshot && !isSavedSnapshot(data) && !data.read_degraded) {
      const snapshotPayload = typeof snapshotSelect === 'function' ? applyLiteQuerySelector(snapshotSelect, data) : data;
      writeLiteSnapshot(path, snapshotPayload);
      return data.__liteSnapshot ? data : attachFreshSnapshotMeta(path, data);
    }
    return data;
  } catch (error) {
    if (safePath) {
      markLiteSnapshotBackendUnreachable();
      const cached = await readLiteSnapshotAsync(path);
      if (cached) return cached;
    }
    throw error;
  }
}

function useLiteDocumentVisibility() {
  const [visible, setVisible] = useState(isLiteDocumentVisible);

  useEffect(() => {
    if (typeof document === 'undefined') return undefined;
    const updateVisibility = () => setVisible(isLiteDocumentVisible());
    document.addEventListener('visibilitychange', updateVisibility);
    return () => document.removeEventListener('visibilitychange', updateVisibility);
  }, []);

  return visible;
}

export function useLiteQuery({
  queryKey,
  path,
  queryFn,
  enabled = true,
  method = 'GET',
  staleTime,
  gcTime,
  refetchInterval,
  pollingMode = 'normal',
  isLive,
  enabledWhenHidden = false,
  refetchOnWindowFocus = false,
  refetchOnMount = true,
  refetchOnReconnect = true,
  placeholderData,
  select,
  snapshotSelect,
} = {}) {
  const normalizedPath = normalizeQueryPath(path || queryFn?.safeSnapshotPath || '');
  const resolvedQueryKey = defaultQueryKey(normalizedPath || queryFn?.name || 'lite-query', queryKey);
  const queryClient = useQueryClient();
  const safeSnapshotPath = isSafeLiteSnapshotPath(normalizedPath) && !isUnsafeSnapshotRequest(normalizedPath, method)
    ? normalizedPath
    : null;
  const cached = useMemo(() => (safeSnapshotPath ? readLiteSnapshot(safeSnapshotPath) : null), [safeSnapshotPath]);
  const documentVisible = useLiteDocumentVisibility();
  const resolvedRefetchInterval = useCallback((queryState) => {
    if (typeof refetchInterval === 'function') return refetchInterval(queryState);
    if (refetchInterval !== undefined) return refetchInterval;
    const data = queryState?.state?.data;
    const live = typeof isLive === 'function' ? Boolean(isLive(data)) : hasLiteLiveOperation(data);
    return liteQueryPollingInterval({
      visible: documentVisible,
      live,
      mode: pollingMode,
      enabledWhenHidden,
      failureCount: queryState?.state?.failureCount || 0,
      error: queryState?.state?.error || null,
      savedState: isSavedSnapshot(data),
      retryAfterSeconds: Math.max(
        Number(data?.retry_after_seconds || 0),
        Number(data?.retry_after_ms || data?.__liteSnapshot?.retryAfterMs || 0) / 1000,
        Number(data?.__liteSnapshot?.retryAfterSeconds || 0),
      ),
    });
  }, [documentVisible, enabledWhenHidden, isLive, pollingMode, refetchInterval]);

  const query = useQuery({
    queryKey: resolvedQueryKey,
    enabled: Boolean(enabled && queryFn),
    queryFn: async () => {
      const previous = queryClient.getQueryData(resolvedQueryKey) || {};
      const data = await queryWithSafeSnapshotFallback({ path: normalizedPath, queryFn, method, snapshotSelect: snapshotSelect || select });
      if (!isLiteNotModified(data)) {
        if (normalizedPath === liteQueryPaths.securityProgress && !isSavedSnapshot(data)) {
          const reconciled = reconcileLiteSecurityProgress({ cachedProgress: previous, backendProgress: data });
          if (reconciled) publishLiteLifecycleDiagnostics(liteApi);
        }
        return data;
      }
      const cachedPrevious = queryClient.getQueryData(resolvedQueryKey);
      if (cachedPrevious) return cachedPrevious;
      if (safeSnapshotPath) {
        const saved = await readLiteSnapshotAsync(safeSnapshotPath);
        if (saved) return saved;
      }
      return data;
    },
    initialData: cached || undefined,
    initialDataUpdatedAt: initialDataUpdatedAt(cached),
    placeholderData,
    staleTime,
    gcTime,
    select: typeof select === 'function' ? (payload) => applyLiteQuerySelector(select, payload) : undefined,
    refetchInterval: resolvedRefetchInterval,
    refetchIntervalInBackground: Boolean(enabledWhenHidden),
    refetchOnWindowFocus,
    refetchOnMount,
    refetchOnReconnect,
    structuralSharing: true,
    retry: (failureCount, error) => {
      if (['critical', 'capacity'].includes(String(error?.loadState || '').toLowerCase())) return false;
      if (String(error?.degradedReason || '').includes('capacity')) return false;
      if (Number(error?.status) === 503) return failureCount < 1;
      return failureCount < 2;
    },
    retryDelay: (attemptIndex, error) => {
      const retryAfterMs = Math.max(
        Math.max(0, Math.min(Number(error?.retryAfterSeconds) || 0, 3600)) * 1000,
        Math.max(0, Math.min(Number(error?.retryAfterMs) || 0, 3_600_000)),
      );
      return retryAfterMs || Math.min(30_000, 1_000 * (2 ** attemptIndex));
    },
  });

  const refresh = useCallback(async () => {
    const result = await query.refetch({ cancelRefetch: false });
    return result.data;
  }, [query]);

  const meta = snapshotMeta(query.data, query.isFetching);
  const saved = isSavedSnapshot(query.data);
  const expired = Boolean(meta?.expired || meta?.isExpired);
  const errorMessage = query.error instanceof Error ? query.error.message : query.error ? 'Pocket Lab Lite could not load this area.' : null;
  const checkedAt = meta?.checkedAt || meta?.savedAt || null;
  const cacheStatus = describeLiteSnapshot(meta, errorMessage);
  const backendDegraded = Boolean(query.data?.read_degraded);
  const loadState = String(query.data?.load_state || 'normal').toLowerCase();
  const degradedReason = String(query.data?.degraded_reason || '');
  const retryAfterMs = Math.max(
    Number(query.data?.retry_after_ms || 0),
    Number(query.data?.retry_after_seconds || 0) * 1000,
  );
  const waitingForCapacity = Boolean(
    loadState === 'critical'
    || degradedReason.includes('capacity')
    || degradedReason.includes('queue_pressure')
    || degradedReason.includes('cpu_budget')
  );

  return {
    ...query,
    loading: query.isLoading,
    refreshing: query.isFetching,
    refresh,
    refetch: refresh,
    isSavedState: saved,
    savedStateOnly: Boolean(saved || (query.error && query.data?.__liteSnapshot)),
    isStale: Boolean(saved || expired || query.isStale),
    isExpired: expired,
    savedAt: meta?.savedAt || null,
    checkedAt,
    lastUpdatedLabel: checkedAt ? snapshotAgeLabel(checkedAt) : '',
    cacheStatus,
    backendReachable: Boolean(query.data && !saved && !query.error),
    degraded: Boolean(saved || query.error || backendDegraded),
    backendDegraded,
    degradedReason,
    loadState,
    retryAfterMs,
    waitingForCapacity,
    dataSource: String(query.data?.data_source || (saved ? 'saved_snapshot' : 'fastapi')),
    disabledReason: expired
      ? 'Saved state expired. Reconnect to continue.'
      : saved || query.error
        ? 'Saved state only. Reconnect to continue.'
        : waitingForCapacity
          ? 'Pocket Lab is busy. Current saved state remains visible while capacity recovers.'
          : backendDegraded
            ? 'Pocket Lab is showing the latest safe state while background work recovers.'
            : '',
    error: errorMessage,
  };
}

export function isUnsafeLiteSnapshotRequest(path = '', method = 'GET') {
  return isUnsafeSnapshotRequest(path, method);
}
