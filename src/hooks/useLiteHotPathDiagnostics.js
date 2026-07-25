import { useEffect } from 'react';
import { useLiteQuery } from './useLiteQuery.js';
import { liteApi } from '../lib/liteApi.js';
import { setOfflineCacheMeta } from '../lib/liteOfflineDb.js';
import { liteQueryKeys, liteQueryPaths } from '../lib/liteQueryClient.js';
import { useLiteUiStore } from '../stores/liteUiStore.js';

const META_KEY = 'lite_hot_path_diagnostics_v1';

function summarize(payload = {}) {
  const jobs = Array.isArray(payload?.hot_path?.top_cpu_jobs)
    ? payload.hot_path.top_cpu_jobs
    : [];
  const top = jobs[0] || {};
  return {
    status: 'ready',
    capturedAt: new Date().toISOString(),
    topJob: String(top.job || ''),
    topCpuMs: Number(top.cpu_ms_total || 0),
    budgetWarningCount: jobs.filter((job) => job?.cpu_budget_warning || job?.wall_budget_warning).length,
    skippedUnchanged: jobs.reduce((sum, job) => sum + Number(job?.skipped_unchanged || 0), 0),
    coalesced: jobs.reduce((sum, job) => sum + Number(job?.coalesced || 0), 0),
  };
}

/** Opt-in only: no polling, no hidden-tab work, and no automatic idle load. */
export function useLiteHotPathDiagnostics({ enabled = false } = {}) {
  const setHotPathDiagnostics = useLiteUiStore((state) => state.setHotPathDiagnostics);
  const query = useLiteQuery({
    queryKey: liteQueryKeys.hotPathDiagnostics(),
    path: liteQueryPaths.hotPathDiagnostics,
    queryFn: liteApi.hotPathDiagnostics,
    enabled,
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
    refetchInterval: false,
    enabledWhenHidden: false,
    refetchOnMount: false,
    refetchOnReconnect: false,
    placeholderData: (previous) => previous,
  });

  useEffect(() => {
    if (!query.data || query.data.__liteNotModified) return;
    const summary = summarize(query.data);
    setHotPathDiagnostics(summary);
    void setOfflineCacheMeta(META_KEY, summary);
  }, [query.data, setHotPathDiagnostics]);

  return query;
}
