import { useCallback, useEffect, useMemo, useState } from 'react';
import { usePocketLabEvents } from './usePocketLabEvents';

const initialTelemetry = {
  cpu_temp_c: 0,
  free_space_mb: 0,
  cpu_usage_percent: 0,
  memory_usage_mb: 0,
  memory_total_mb: 0,
  memory_free_mb: 0,
  timestamp: null,
};

function normalizeTelemetry(data = {}) {
  const sample = data.sample || data.telemetry || data;
  const memoryTotal = Number(sample.memory_total_mb ?? sample.memoryTotalMB ?? 0);
  const memoryFree = Number(sample.memory_free_mb ?? sample.memoryFreeMB ?? 0);
  return {
    ...initialTelemetry,
    ...sample,
    cpu_temp_c: Number(sample.cpu_temp_c ?? sample.cpuTemp ?? 0),
    free_space_mb: Number(sample.free_space_mb ?? sample.freeSpaceMB ?? 0),
    cpu_usage_percent: Number(sample.cpu_usage_percent ?? sample.cpuUsagePercent ?? 0),
    memory_usage_mb: Number(sample.memory_usage_mb ?? Math.max(0, memoryTotal - memoryFree)),
    memory_total_mb: memoryTotal,
    memory_free_mb: memoryFree,
    timestamp: sample.timestamp || sample.sampled_at || new Date().toISOString(),
  };
}

export function useTelemetry({ pollFallbackMs = 30000 } = {}) {
  const [liveData, setLiveData] = useState(() => {
    try {
      const cached = localStorage.getItem('pocket_telemetry');
      return cached ? normalizeTelemetry(JSON.parse(cached)) : initialTelemetry;
    } catch {
      return initialTelemetry;
    }
  });
  const [isConnected, setIsConnected] = useState(false);
  const [source, setSource] = useState('initial');
  const [error, setError] = useState(null);

  const { latest: latestTelemetryEvent, connection, isLive, lastEventAt } = usePocketLabEvents({
    subjectPrefixes: ['pocketlab.events.telemetry.'],
    limit: 25,
    pollFallbackMs: 5000,
  });

  const persist = useCallback((next) => {
    setLiveData(next);
    try { localStorage.setItem('pocket_telemetry', JSON.stringify(next)); } catch (_error) {
      // Ignore telemetry refresh failures; stale telemetry remains visible.
    }
  }, []);

  const refresh = useCallback(async () => {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 3500);
    try {
      const res = await fetch('/api/telemetry.json', {
        cache: 'no-store',
        headers: { Accept: 'application/json' },
        signal: controller.signal,
      });
      const text = await res.text();
      const data = JSON.parse(text || '{}');
      if (!res.ok || data.error) throw new Error(data.error || 'Telemetry unavailable');
      const normalized = normalizeTelemetry(data);
      persist(normalized);
      setIsConnected(true);
      setSource(data.sample_source || 'api-read');
      setError(null);
      return normalized;
    } catch (err) {
      setIsConnected(false);
      setError(err instanceof Error ? err.message : 'Telemetry unavailable');
      return null;
    } finally {
      window.clearTimeout(timeoutId);
    }
  }, [persist]);

  useEffect(() => {
    refresh();
    const intervalId = window.setInterval(() => {
      const wsOpen = connection?.state === 'connected';
      if (!wsOpen) refresh();
    }, pollFallbackMs);
    return () => window.clearInterval(intervalId);
  }, [refresh, pollFallbackMs, connection?.state]);

  useEffect(() => {
    const data = latestTelemetryEvent?.data;
    if (!data || Object.keys(data).length === 0) return;
    const normalized = normalizeTelemetry(data);
    persist(normalized);
    setIsConnected(true);
    setSource(data.source || data.sample?.sample_source || 'event-stream');
    setError(null);
  }, [latestTelemetryEvent?.id, latestTelemetryEvent?.time, persist]);

  const status = useMemo(() => ({
    connection,
    isLive,
    source,
    lastEventAt,
    error,
  }), [connection, isLive, source, lastEventAt, error]);

  return { liveData, isConnected: isConnected || isLive, refresh, status };
}
