import { useCallback, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  attachFreshSnapshotMeta,
  describeLiteSnapshot,
  isSafeLiteSnapshotPath,
  markLiteSnapshotBackendUnreachable,
  readLiteSnapshot,
  readLiteSnapshotAsync,
  snapshotAgeLabel,
  writeLiteSnapshot,
} from '../lib/liteSafeSnapshots.js';
import { liteQueryKeys } from '../lib/liteQueryClient.js';

const UNSAFE_METHOD_PATTERN = /^(POST|PUT|PATCH|DELETE)$/i;
const UNSAFE_PATH_PATTERN = /bootstrap|invite|token|secret|password|evidence|receipt|debug|raw/i;

function normalizeQueryPath(path = '') {
  try {
    const url = new URL(path, typeof window !== 'undefined' ? window.location.origin : 'http://127.0.0.1');
    return url.pathname;
  } catch {
    return String(path || '').split('?')[0];
  }
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

async function queryWithSafeSnapshotFallback({ path, queryFn, method = 'GET' }) {
  const safePath = isSafeLiteSnapshotPath(path) && !isUnsafeSnapshotRequest(path, method);
  try {
    const data = await queryFn();
    if (safePath && data && typeof data === 'object' && !isSavedSnapshot(data)) {
      writeLiteSnapshot(path, data);
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

export function useLiteQuery({
  queryKey,
  path,
  queryFn,
  enabled = true,
  method = 'GET',
  staleTime,
  refetchInterval,
  placeholderData,
} = {}) {
  const normalizedPath = normalizeQueryPath(path || queryFn?.safeSnapshotPath || '');
  const safeSnapshotPath = isSafeLiteSnapshotPath(normalizedPath) && !isUnsafeSnapshotRequest(normalizedPath, method)
    ? normalizedPath
    : null;
  const cached = useMemo(() => (safeSnapshotPath ? readLiteSnapshot(safeSnapshotPath) : null), [safeSnapshotPath]);

  const query = useQuery({
    queryKey: defaultQueryKey(normalizedPath || queryFn?.name || 'lite-query', queryKey),
    enabled: Boolean(enabled && queryFn),
    queryFn: () => queryWithSafeSnapshotFallback({ path: normalizedPath, queryFn, method }),
    initialData: cached || undefined,
    initialDataUpdatedAt: initialDataUpdatedAt(cached),
    placeholderData,
    staleTime,
    refetchInterval,
    refetchIntervalInBackground: false,
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
    degraded: Boolean(saved || query.error),
    disabledReason: expired ? 'Saved state expired. Reconnect to continue.' : saved || query.error ? 'Saved state only. Reconnect to continue.' : '',
    error: errorMessage,
  };
}

export function isUnsafeLiteSnapshotRequest(path = '', method = 'GET') {
  return isUnsafeSnapshotRequest(path, method);
}
