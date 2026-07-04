import { useCallback, useEffect, useRef, useState } from 'react';
import { liteApi } from '../lib/liteApi.js';
import { describeLiteSnapshot, readLiteSnapshot } from '../lib/liteSafeSnapshots.js';

const initialStatus = {
  overall: 'unknown',
  checked_at: null,
  device: { name: 'pocket-lab', mode: 'lite', resource_profile: 'low-power' },
  services: [],
  summary: {},
  telemetry: {},
};

function initialCachedData(loader, fallback = null) {
  if (!loader?.safeSnapshotPath) return fallback;
  return readLiteSnapshot(loader.safeSnapshotPath) || fallback;
}

function isSavedSnapshot(data) {
  const meta = data?.__liteSnapshot;
  return Boolean(meta?.cached || meta?.stale || meta?.source === 'cache');
}

function snapshotMeta(data, refreshing = false) {
  const meta = data?.__liteSnapshot || null;
  if (!meta) return null;
  return { ...meta, refreshing: Boolean(refreshing && !isSavedSnapshot(data)) };
}

function shouldSkipRefresh(lastRefreshAt, minGapMs) {
  return Date.now() - lastRefreshAt.current < minGapMs;
}

export function useLiteStatus(intervalMs = 30000) {
  const cached = initialCachedData(liteApi.status, null);
  const [status, setStatus] = useState(() => ({ ...initialStatus, ...(cached || {}) }));
  const [loading, setLoading] = useState(() => !cached);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const inFlightRef = useRef(null);
  const lastRefreshAt = useRef(0);

  const refresh = useCallback(async ({ force = false } = {}) => {
    if (inFlightRef.current) return inFlightRef.current;
    if (!force && shouldSkipRefresh(lastRefreshAt, 3500)) return status;
    setRefreshing(true);
    const request = (async () => {
      lastRefreshAt.current = Date.now();
      try {
        const data = await liteApi.status();
        setStatus({ ...initialStatus, ...data });
        setError(null);
        return data;
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Pocket Lab Lite is unreachable.');
        return null;
      } finally {
        setLoading(false);
        setRefreshing(false);
        inFlightRef.current = null;
      }
    })();
    inFlightRef.current = request;
    return request;
  }, [status]);

  useEffect(() => {
    refresh({ force: true });
    const timer = window.setInterval(() => refresh(), Math.max(30000, intervalMs));
    return () => window.clearInterval(timer);
  }, [intervalMs, refresh]);

  useEffect(() => {
    const refreshWhenVisible = () => { if (document.visibilityState === 'visible') refresh(); };
    const refreshWhenOnline = () => refresh({ force: true });
    document.addEventListener('visibilitychange', refreshWhenVisible);
    window.addEventListener('online', refreshWhenOnline);
    return () => {
      document.removeEventListener('visibilitychange', refreshWhenVisible);
      window.removeEventListener('online', refreshWhenOnline);
    };
  }, [refresh]);

  const cacheStatus = describeLiteSnapshot(snapshotMeta(status, refreshing), error);
  return { status, loading, refreshing, error, refresh, cacheStatus, savedStateOnly: Boolean(isSavedSnapshot(status) || (error && status?.__liteSnapshot)) };
}

export function useLiteResource(loader, dependencies = []) {
  const cached = initialCachedData(loader, null);
  const [data, setData] = useState(cached);
  const [loading, setLoading] = useState(() => !cached);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const inFlightRef = useRef(null);
  const lastRefreshAt = useRef(0);

  const refresh = useCallback(async ({ force = false } = {}) => {
    if (inFlightRef.current) return inFlightRef.current;
    if (!force && shouldSkipRefresh(lastRefreshAt, 3500)) return data;
    setLoading(!data);
    setRefreshing(true);
    const request = (async () => {
      lastRefreshAt.current = Date.now();
      try {
        const result = await loader();
        setData(result);
        setError(null);
        return result;
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Pocket Lab Lite could not load this area.');
        return null;
      } finally {
        setLoading(false);
        setRefreshing(false);
        inFlightRef.current = null;
      }
    })();
    inFlightRef.current = request;
    return request;
  }, dependencies); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { refresh({ force: true }); }, [refresh]);
  useEffect(() => {
    const refreshWhenVisible = () => { if (document.visibilityState === 'visible') refresh(); };
    const refreshWhenOnline = () => refresh({ force: true });
    document.addEventListener('visibilitychange', refreshWhenVisible);
    window.addEventListener('online', refreshWhenOnline);
    return () => {
      document.removeEventListener('visibilitychange', refreshWhenVisible);
      window.removeEventListener('online', refreshWhenOnline);
    };
  }, [refresh]);

  const cacheStatus = describeLiteSnapshot(snapshotMeta(data, refreshing), error);
  return { data, loading, refreshing, error, refresh, cacheStatus, savedStateOnly: Boolean(isSavedSnapshot(data) || (error && data?.__liteSnapshot)) };
}
