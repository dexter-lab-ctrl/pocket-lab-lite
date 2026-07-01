import { useCallback, useEffect, useRef, useState } from 'react';
import { liteApi } from '../lib/liteApi.js';

const initialStatus = {
  overall: 'unknown',
  checked_at: null,
  device: { name: 'pocket-lab', mode: 'lite', resource_profile: 'low-power' },
  services: [],
  summary: {},
  telemetry: {},
};

export function useLiteStatus(intervalMs = 15000) {
  const [status, setStatus] = useState(initialStatus);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
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
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs, refresh]);

  return { status, loading, error, refresh };
}

export function useLiteResource(loader, dependencies = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const inFlightRef = useRef(null);

  const refresh = useCallback(async () => {
    if (inFlightRef.current) {
      return inFlightRef.current;
    }
    setLoading(true);
    const request = (async () => {
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
        inFlightRef.current = null;
      }
    })();
    inFlightRef.current = request;
    return request;
  }, dependencies);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { data, loading, error, refresh };
}
