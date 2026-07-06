import { useMemo } from 'react';
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
  if (path === liteQueryPaths.recovery) return liteQueryKeys.recovery();
  return liteQueryKeys.resource(path, ...dependencies);
}

function pathForLoader(loader) {
  return loader?.safeSnapshotPath || '';
}

export function useLiteStatus(intervalMs = 30000) {
  const query = useLiteQuery({
    queryKey: liteQueryKeys.status(),
    path: liteQueryPaths.status,
    queryFn: liteApi.status,
    refetchInterval: Math.max(30000, intervalMs),
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
  };
}

export function useLiteResource(loader, dependencies = []) {
  const query = useLiteQuery({
    queryKey: queryKeyForLoader(loader, dependencies),
    path: pathForLoader(loader),
    queryFn: loader,
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
  };
}
