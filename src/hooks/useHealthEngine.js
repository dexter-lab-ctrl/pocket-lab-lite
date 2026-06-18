import { useEffect, useState, useCallback } from 'react';
import { normalizeHealthPayload } from '../lib/health';
import { usePocketLabEvents } from './usePocketLabEvents';

const initialHealth = {
  engine: 'gatus',
  source: 'fallback',
  status: 'unknown',
  summary: {
    healthy: 0,
    warning: 0,
    degraded: 0,
    unhealthy: 0,
    unavailable: 0,
    maintenance: 0,
    unknown: 0,
    total: 0,
  },
  services: {},
  checks: [],
  last_checked_at: null,
  gatus: {
    base_url: '',
    statuses_path: '/api/health-engine.json',
    reachable: false,
  },
};

export function useHealthEngine(pollIntervalMs = 60000) {
  const [health, setHealth] = useState(initialHealth);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [source, setSource] = useState('initial');
  const { latest: latestHealthEvent, connection, isLive, lastEventAt } = usePocketLabEvents({
    subjectPrefixes: ['pocketlab.events.health.'],
    limit: 25,
    pollFallbackMs: 5000,
  });

  const applyHealth = useCallback((payload, nextSource = 'event-stream') => {
    const snapshot = payload?.snapshot || payload?.health || payload;
    if (!snapshot || typeof snapshot !== 'object') return;
    setHealth((prev) => normalizeHealthPayload({ ...prev, ...snapshot }));
    setSource(nextSource);
    setError(null);
    setIsLoading(false);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch('/api/health-engine.json', { cache: 'no-store', headers: { Accept: 'application/json' } });
      const text = await res.text();
      const data = JSON.parse(text || '{}');
      applyHealth(data, data.sample_source || 'api-read');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load health engine');
      setHealth(normalizeHealthPayload(initialHealth));
      setIsLoading(false);
    }
  }, [applyHealth]);

  useEffect(() => {
    refresh();
    const interval = window.setInterval(() => {
      if (connection?.state !== 'connected') refresh();
    }, pollIntervalMs);
    return () => window.clearInterval(interval);
  }, [pollIntervalMs, refresh, connection?.state]);

  useEffect(() => {
    if (!latestHealthEvent?.data) return;
    applyHealth(latestHealthEvent.data, latestHealthEvent.data.source || 'event-stream');
  }, [latestHealthEvent?.id, latestHealthEvent?.time, applyHealth]);

  return { health, isLoading, error, refresh, live: { connection, isLive, source, lastEventAt } };
}
