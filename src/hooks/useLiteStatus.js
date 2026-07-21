import { useMemo } from 'react';
import { litePollingIntervals } from '../lib/litePollingPolicy.js';
import { liteApi } from '../lib/liteApi.js';
import { liteQueryKeys, liteQueryPaths } from '../lib/liteQueryClient.js';
import { useLiteQuery } from './useLiteQuery.js';

const initialStatus = {
  overall: 'unknown',
  checked_at: null,
  device: { name: 'pocket-lab', mode: 'lite', resource_profile: 'low-power' },
  services: [],
  summary: {},
  telemetry: {},
};

function queryKeyForLoader(loader, dependencies = []) {
  const path = loader?.safeSnapshotPath || loader?.name || 'resource';
  if (path === liteQueryPaths.status) return liteQueryKeys.status();
  if (path === liteQueryPaths.catalog) return liteQueryKeys.catalog();
  if (path === liteQueryPaths.appActions('photoprism')) return liteQueryKeys.appActions('photoprism');
  if (path === liteQueryPaths.fleet) return liteQueryKeys.fleet();
  if (path === liteQueryPaths.security) return liteQueryKeys.security();
  if (path === liteQueryPaths.securityDetails) return liteQueryKeys.securityDetails();
  if (path === liteQueryPaths.securityFreshness) return liteQueryKeys.securityFreshness();
  if (path === liteQueryPaths.securityProgress) return liteQueryKeys.securityProgress();
  if (path === liteQueryPaths.recovery) return liteQueryKeys.recovery();
  if (path === liteQueryPaths.recoverySummary) return liteQueryKeys.recoverySummary();
  if (path === liteQueryPaths.recoveryDetails) return liteQueryKeys.recoveryDetails();
  return liteQueryKeys.resource(path, ...dependencies);
}

function pathForLoader(loader) {
  return loader?.safeSnapshotPath || '';
}

export function useLiteStatus(intervalMs = litePollingIntervals.relaxed) {
  const query = useLiteQuery({
    queryKey: liteQueryKeys.status(),
    path: liteQueryPaths.status,
    queryFn: liteApi.status,
    pollingMode: 'relaxed',
    refetchOnWindowFocus: false,
    refetchInterval: Math.max(litePollingIntervals.relaxed, intervalMs),
  });

  const status = useMemo(() => ({ ...initialStatus, ...(query.data || {}) }), [query.data]);

  return {
    status,
    loading: query.loading && !query.data,
    refreshing: query.refreshing,
    error: query.error,
    refresh: query.refresh,
    cacheStatus: query.cacheStatus,
    savedStateOnly: query.savedStateOnly,
    backendReachable: query.backendReachable,
    lastUpdatedLabel: query.lastUpdatedLabel,
    isExpired: query.isExpired,
  };
}

export function useLiteResource(loader, dependencies = [], options = {}) {
  const query = useLiteQuery({
    queryKey: queryKeyForLoader(loader, dependencies),
    path: pathForLoader(loader),
    queryFn: loader,
    ...options,
  });

  return {
    data: query.data,
    loading: query.loading && !query.data,
    refreshing: query.refreshing,
    error: query.error,
    refresh: query.refresh,
    cacheStatus: query.cacheStatus,
    savedStateOnly: query.savedStateOnly,
    backendReachable: query.backendReachable,
    lastUpdatedLabel: query.lastUpdatedLabel,
    isExpired: query.isExpired,
  };
}
