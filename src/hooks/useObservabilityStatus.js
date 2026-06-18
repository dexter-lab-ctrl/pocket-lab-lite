import { useCallback, useEffect, useMemo, useState } from 'react';

const initialStatus = {
  status: 'unknown',
  checked_at: null,
  cached: false,
  cache_ttl_seconds: 30,
  services: {},
  prometheus_targets: {
    status: 'unknown',
    up: 0,
    down: 0,
    total: 0,
    down_targets: [],
  },
  warnings: [],
};

const VALID_STATUSES = new Set(['healthy', 'degraded', 'unavailable', 'unknown']);

function normalizeStatus(value) {
  const status = String(value || 'unknown').toLowerCase();
  return VALID_STATUSES.has(status) ? status : 'unknown';
}

function normalizeService(value = {}) {
  if (!value || typeof value !== 'object') {
    return { status: 'unknown', reason: 'No runtime status reported' };
  }
  return {
    ...value,
    status: normalizeStatus(value.status),
    latency_ms: Number.isFinite(Number(value.latency_ms)) ? Number(value.latency_ms) : undefined,
    reason: value.reason || value.error || 'No detail reported',
  };
}

export function normalizeObservabilityStatus(payload = {}) {
  const services = Object.fromEntries(
    Object.entries(payload.services || {}).map(([name, value]) => [name, normalizeService(value)])
  );
  const targets = payload.prometheus_targets || {};
  return {
    ...initialStatus,
    ...payload,
    status: normalizeStatus(payload.status),
    services,
    prometheus_targets: {
      ...initialStatus.prometheus_targets,
      ...targets,
      status: normalizeStatus(targets.status),
      up: Number(targets.up || 0),
      down: Number(targets.down || 0),
      total: Number(targets.total || 0),
      down_targets: Array.isArray(targets.down_targets) ? targets.down_targets : [],
    },
    warnings: Array.isArray(payload.warnings) ? payload.warnings : [],
  };
}

export function useObservabilityStatus(pollIntervalMs = 60000) {
  const [snapshot, setSnapshot] = useState(initialStatus);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 5000);
    try {
      const res = await fetch('/api/observability/status', {
        cache: 'no-store',
        headers: { Accept: 'application/json' },
        signal: controller.signal,
      });
      const text = await res.text();
      const data = JSON.parse(text || '{}');
      if (!res.ok || data.error) throw new Error(data.error || 'Observability status unavailable');
      const normalized = normalizeObservabilityStatus(data);
      setSnapshot(normalized);
      setError(null);
      setIsLoading(false);
      return normalized;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Observability status unavailable');
      setSnapshot((prev) => ({ ...prev, status: prev.status === 'unknown' ? 'unavailable' : prev.status }));
      setIsLoading(false);
      return null;
    } finally {
      window.clearTimeout(timeoutId);
    }
  }, []);

  useEffect(() => {
    refresh();
    const intervalId = window.setInterval(refresh, pollIntervalMs);
    return () => window.clearInterval(intervalId);
  }, [refresh, pollIntervalMs]);

  const summary = useMemo(() => {
    const services = Object.values(snapshot.services || {});
    return {
      healthy: services.filter((service) => service.status === 'healthy').length,
      degraded: services.filter((service) => service.status === 'degraded').length,
      unavailable: services.filter((service) => service.status === 'unavailable').length,
      unknown: services.filter((service) => service.status === 'unknown').length,
      total: services.length,
    };
  }, [snapshot.services]);

  return { snapshot, summary, isLoading, error, refresh };
}
