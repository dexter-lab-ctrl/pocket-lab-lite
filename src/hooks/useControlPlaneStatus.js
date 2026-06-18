import { useCallback, useEffect, useState } from 'react';

const INITIAL_STATUS = {
  ready: false,
  loading: true,
  degraded: true,
  api: false,
  nats: false,
  jetstream: false,
  worker: false,
  message: 'Checking control plane readiness...',
  raw: null,
  checkedAt: null,
};

function normalizeStatus(readyPayload, natsPayload, workerPayload) {
  const nats = natsPayload?.nats || natsPayload || {};
  const ready = readyPayload || {};
  const worker = workerPayload || {};
  const natsConnected = Boolean(nats.connected ?? ready.nats_connected ?? ready.nats?.connected);
  const jetstreamEnabled = Boolean(nats.jetstream_enabled ?? ready.jetstream_enabled ?? ready.nats?.jetstream_enabled);
  const workerReady = Boolean(worker.running ?? worker.connected ?? ready.worker_ready ?? true);
  const apiReady = Boolean(ready.status === 'ready' || ready.ready === true || ready.ok === true);
  const hardReady = apiReady && natsConnected && jetstreamEnabled && workerReady;
  let message = 'Control plane is ready.';
  if (!apiReady) message = ready.detail || ready.error || 'Control API readiness check failed.';
  else if (!natsConnected) message = 'The event bus is required for governed changes and is not connected.';
  else if (!jetstreamEnabled) message = 'The durable event stream is required for governed changes and is not enabled.';
  else if (!workerReady) message = 'The command executor is not reporting ready.';
  return {
    ready: hardReady,
    loading: false,
    degraded: !hardReady,
    api: apiReady,
    nats: natsConnected,
    jetstream: jetstreamEnabled,
    worker: workerReady,
    message,
    raw: { ready, nats, worker },
    checkedAt: new Date().toISOString(),
  };
}

async function readJson(path) {
  const res = await fetch(path, { cache: 'no-store', headers: { Accept: 'application/json' } });
  const text = await res.text();
  let data = {};
  try { data = text ? JSON.parse(text) : {}; } catch { data = { error: 'Invalid JSON response' }; }
  if (!res.ok) data = { ...data, status_code: res.status, error: data?.detail || data?.error || res.statusText };
  return data;
}

export function useControlPlaneStatus(intervalMs = 15000) {
  const [status, setStatus] = useState(INITIAL_STATUS);

  const refresh = useCallback(async () => {
    try {
      const [readyPayload, natsPayload, workerPayload] = await Promise.all([
        readJson('/ready'),
        readJson('/api/nats/status'),
        readJson('/api/workers/status'),
      ]);
      setStatus(normalizeStatus(readyPayload, natsPayload, workerPayload));
    } catch (err) {
      setStatus({
        ...INITIAL_STATUS,
        loading: false,
        message: err?.message || 'Control plane is unreachable.',
        checkedAt: new Date().toISOString(),
      });
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, intervalMs);
    return () => clearInterval(timer);
  }, [refresh, intervalMs]);

  return { status, refresh };
}

export function productionWriteBlockedMessage(simpleMode = false) {
  return simpleMode
    ? 'Pocket Lab needs its live control plane before it can safely make changes.'
    : 'Governed changes are disabled until the control API, event bus, durable stream, and executor are ready.';
}
