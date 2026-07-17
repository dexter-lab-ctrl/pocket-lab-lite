import { useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { liteApi } from '../lib/liteApi.js';
import { broadcastLiteSecurityScanCompleted } from '../lib/liteSafeSnapshots.js';
import { liteQueryKeys, liteQueryPaths } from '../lib/liteQueryClient.js';
import {
  publishLiteLifecycleDiagnostics,
  reconcileLiteSecurityProgress,
  trackLiteLifecycleEventSource,
  trackLiteLifecycleListener,
  trackLiteLifecyclePollTimer,
  updateLiteLifecycleEnvironment,
} from '../lib/liteLifecycleDiagnostics.js';

const API_BASE = (import.meta.env.VITE_POCKETLAB_API_BASE || '').replace(/\/$/, '');
const SECURITY_EVENTS_PATH = '/api/lite/security/events';
const SECURITY_STREAM_TERMINAL_TYPES = new Set([
  'security.scan.completed',
  'security.scan.failed',
  'security.scan.cancelled',
]);
const SECURITY_STREAM_LIVE_TYPES = new Set([
  'security.scan.queued',
  'security.scan.started',
  'security.scan.stage',
  'security.scan.progress',
  'security.scan.evidence_saved',
]);
const SECURITY_TERMINAL_STATUSES = new Set(['succeeded', 'completed', 'degraded', 'failed', 'cancelled', 'canceled']);
const SECURITY_PROGRESS_FALLBACK_MS = 3000;
const SECURITY_STREAM_FALLBACK_LABEL = 'Using backup progress check';

function endpoint(path) {
  return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
}

function normalizeProfile(profile = 'quick') {
  const value = String(profile || 'quick').trim().toLowerCase();
  return ['quick', 'full', 'app'].includes(value) ? value : 'quick';
}

function securityRunKey(value = '') {
  return String(value || '').trim();
}

function securityEventMatchesActiveRun(event = {}, activeRunId = '') {
  const expected = securityRunKey(activeRunId);
  if (!expected) return false;
  const actual = securityRunKey(event.run_id || event.command_id || event.job_id || '');
  return Boolean(actual && actual === expected);
}

function shouldKeepSecurityFallbackAlive(event = {}, { forceFallback = false, localActive = false, activeRunId = '' } = {}) {
  if (!forceFallback && !localActive) return false;
  if (liveSecurityEvent(event)) return true;
  if (!terminalSecurityEvent(event)) return Boolean(forceFallback || localActive);
  if (!localActive) return false;
  return !securityEventMatchesActiveRun(event, activeRunId);
}

function terminalSecurityEvent(event = {}) {
  const type = String(event.type || '').toLowerCase();
  const status = String(event.status || '').toLowerCase();
  return SECURITY_STREAM_TERMINAL_TYPES.has(type) || SECURITY_TERMINAL_STATUSES.has(status) || (event.active_scan === false && Boolean(event.run_id));
}

function liveSecurityEvent(event = {}) {
  const type = String(event.type || '').toLowerCase();
  return Boolean(event.active_scan) || SECURITY_STREAM_LIVE_TYPES.has(type);
}

function typeFromProgress(progress = {}) {
  const status = String(progress.status || '').toLowerCase();
  if (status === 'failed') return 'security.scan.failed';
  if (status === 'cancelled' || status === 'canceled') return 'security.scan.cancelled';
  if (SECURITY_TERMINAL_STATUSES.has(status)) return 'security.scan.completed';
  if (status === 'queued' || status === 'accepted' || status === 'waiting') return 'security.scan.queued';
  if (progress.active_scan) return 'security.scan.progress';
  return 'security.scan.heartbeat';
}

function normalizeSecurityEvent(event = {}) {
  const profile = normalizeProfile(event.profile || 'quick');
  return {
    type: String(event.type || typeFromProgress(event)),
    run_id: event.run_id || null,
    profile,
    app_id: event.app_id || null,
    stage: event.stage || event.status || 'idle',
    percent: Number.isFinite(Number(event.percent)) ? Math.max(0, Math.min(100, Number(event.percent))) : 0,
    message: event.message || (profile === 'app' ? 'Checking app safety' : 'Working'),
    status: event.status || 'idle',
    revision: event.revision || event.progress_revision || '',
    updated_at: event.updated_at || null,
    active_scan: Boolean(event.active_scan),
    summary_revision: event.summary_revision || null,
    profile_revision: event.profile_revision || null,
    history_revision: event.history_revision || null,
    progress_revision: event.progress_revision || event.revision || null,
  };
}

function progressPayloadFromEvent(event = {}) {
  const payload = normalizeSecurityEvent(event);
  return {
    view_model: 'security-progress-stream-f11-v1',
    active_scan: payload.active_scan,
    run_id: payload.run_id,
    profile: payload.profile,
    app_id: payload.app_id || '',
    stage: payload.stage,
    status: payload.status,
    percent: payload.percent,
    message: payload.message,
    revision: payload.progress_revision || payload.revision,
    updated_at: payload.updated_at,
    source: 'security_events_stream',
    sanitized: true,
  };
}

function broadcastTerminalSecurityEvent(payload = {}) {
  if (!terminalSecurityEvent(payload)) return null;
  return broadcastLiteSecurityScanCompleted(payload.profile || 'quick', {
    run_id: payload.run_id || '',
    status: payload.status || 'completed',
    completed_at: payload.updated_at || null,
    updated_at: payload.updated_at || null,
  }, { source: 'security-events-stream', requireTerminal: false });
}

function applySecurityEvent(queryClient, event, historyLimit = 20) {
  const payload = normalizeSecurityEvent(event);
  const profile = normalizeProfile(payload.profile);
  const runId = payload.run_id || 'latest';
  const previous = queryClient.getQueryData(liteQueryKeys.securityProgress()) || {};
  queryClient.setQueryData(liteQueryKeys.securityProgress(), {
    ...previous,
    ...progressPayloadFromEvent(payload),
  });
  reconcileLiteSecurityProgress({
    cachedProgress: previous,
    backendProgress: progressPayloadFromEvent(payload),
    writeActionsBlocked: false,
  });

  if (payload.type === 'security.scan.evidence_saved') {
    queryClient.invalidateQueries({ queryKey: liteQueryKeys.securityEvidenceSummary(runId) });
    queryClient.invalidateQueries({ queryKey: liteQueryKeys.securityRunDetails(runId) });
    return payload;
  }

  if (terminalSecurityEvent(payload)) {
    broadcastTerminalSecurityEvent(payload);
    queryClient.invalidateQueries({ queryKey: liteQueryKeys.security() });
    queryClient.invalidateQueries({ queryKey: liteQueryKeys.securityFreshness() });
    queryClient.invalidateQueries({ queryKey: liteQueryKeys.securityProfile(profile) });
    queryClient.invalidateQueries({ queryKey: liteQueryKeys.securityHistory(historyLimit || 20) });
    queryClient.invalidateQueries({ queryKey: liteQueryKeys.securityProgress() });
  }
  return payload;
}

async function loadProgressFallback(queryClient, historyLimit) {
  const progress = await liteApi.securityProgress();
  return applySecurityEvent(queryClient, {
    ...progress,
    type: typeFromProgress(progress),
  }, historyLimit);
}

function initialEnvironment() {
  return {
    visible: typeof document === 'undefined' || document.visibilityState !== 'hidden',
    online: typeof navigator === 'undefined' || navigator.onLine !== false,
  };
}

function useSecurityLifecycleEnvironment() {
  const [environment, setEnvironment] = useState(initialEnvironment);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof document === 'undefined') return undefined;
    const update = () => {
      const next = initialEnvironment();
      setEnvironment(next);
      updateLiteLifecycleEnvironment({ visibilityState: document.visibilityState, onlineState: next.online });
      publishLiteLifecycleDiagnostics(liteApi);
    };
    trackLiteLifecycleListener('visibility', 1);
    trackLiteLifecycleListener('online', 1);
    trackLiteLifecycleListener('offline', 1);
    document.addEventListener('visibilitychange', update);
    window.addEventListener('online', update);
    window.addEventListener('offline', update);
    update();
    return () => {
      document.removeEventListener('visibilitychange', update);
      window.removeEventListener('online', update);
      window.removeEventListener('offline', update);
      trackLiteLifecycleListener('visibility', -1);
      trackLiteLifecycleListener('online', -1);
      trackLiteLifecycleListener('offline', -1);
    };
  }, []);

  return environment;
}

export function useLiteSecurityEvents({ enabled = false, profile = 'quick', historyLimit = 20, forceFallback = false, activeRunId = '', localActive = false, onProgress = null } = {}) {
  const queryClient = useQueryClient();
  const [eventState, setEventState] = useState({ status: 'idle', usingFallback: false, event: null });
  const [fallbackActive, setFallbackActive] = useState(false);
  const lastEventActiveRef = useRef(false);
  const seenEventRef = useRef(false);
  const sourceActiveRef = useRef(false);
  const environment = useSecurityLifecycleEnvironment();
  const historyLimitValue = Number(historyLimit || 20);
  const profileValue = normalizeProfile(profile);
  const activeRunKey = securityRunKey(activeRunId);
  const localProgressActive = Boolean(localActive);
  const canObserve = Boolean(enabled && environment.visible && environment.online);

  useEffect(() => {
    seenEventRef.current = false;
    lastEventActiveRef.current = false;
    if (!canObserve) {
      setFallbackActive(false);
      setEventState((state) => ({ ...state, status: enabled ? 'paused' : 'idle', usingFallback: false }));
      return undefined;
    }
    if (typeof window === 'undefined' || typeof window.EventSource === 'undefined') {
      setFallbackActive(true);
      return undefined;
    }

    let closed = false;
    const source = new window.EventSource(endpoint(SECURITY_EVENTS_PATH));
    sourceActiveRef.current = true;
    trackLiteLifecycleEventSource(true);
    setFallbackActive(false);
    setEventState((state) => ({ ...state, status: 'connecting', usingFallback: false }));
    publishLiteLifecycleDiagnostics(liteApi);

    const closeSource = () => {
      if (closed) return;
      closed = true;
      source.close();
      if (sourceActiveRef.current) {
        sourceActiveRef.current = false;
        trackLiteLifecycleEventSource(false);
      }
      publishLiteLifecycleDiagnostics(liteApi);
    };

    source.onopen = () => {
      if (closed) return;
      setFallbackActive(false);
      setEventState((state) => ({ ...state, status: 'connected', usingFallback: false }));
      publishLiteLifecycleDiagnostics(liteApi);
    };

    source.onmessage = (message) => {
      if (closed) return;
      try {
        const event = normalizeSecurityEvent(JSON.parse(message.data || '{}'));
        seenEventRef.current = true;
        lastEventActiveRef.current = liveSecurityEvent(event);
        const appliedEvent = applySecurityEvent(queryClient, event, historyLimitValue);
        publishLiteLifecycleDiagnostics(liteApi);
        onProgress?.(appliedEvent);
        const terminal = terminalSecurityEvent(event);
        const keepFallbackAlive = shouldKeepSecurityFallbackAlive(event, { forceFallback, localActive: localProgressActive, activeRunId: activeRunKey });
        setEventState({ status: terminal ? 'done' : 'connected', usingFallback: false, event });
        if (terminal || !event.active_scan) {
          closeSource();
          if (keepFallbackAlive && environment.visible && environment.online) setFallbackActive(true);
        }
      } catch {
        closeSource();
        setFallbackActive(true);
      }
    };

    const securityEventHandler = (message) => source.onmessage(message);
    [
      'security.scan.queued',
      'security.scan.started',
      'security.scan.stage',
      'security.scan.progress',
      'security.scan.evidence_saved',
      'security.scan.completed',
      'security.scan.failed',
      'security.scan.cancelled',
      'security.scan.heartbeat',
    ].forEach((eventName) => source.addEventListener(eventName, securityEventHandler));

    source.onerror = () => {
      if (closed) return;
      closeSource();
      if (lastEventActiveRef.current || !seenEventRef.current) {
        setFallbackActive(true);
        setEventState((state) => ({ ...state, status: 'paused', usingFallback: true }));
      }
    };

    return closeSource;
  }, [activeRunKey, canObserve, enabled, environment.online, environment.visible, forceFallback, historyLimitValue, localProgressActive, onProgress, profileValue, queryClient]);

  useEffect(() => {
    if (!canObserve || sourceActiveRef.current || (!fallbackActive && !forceFallback)) return undefined;
    let stopped = false;
    let timer;
    let timerTracked = false;

    const schedule = () => {
      if (stopped) return;
      timer = window.setTimeout(tick, SECURITY_PROGRESS_FALLBACK_MS);
      if (!timerTracked) {
        timerTracked = true;
        trackLiteLifecyclePollTimer(true);
        publishLiteLifecycleDiagnostics(liteApi);
      }
    };

    const tick = async () => {
      if (stopped || sourceActiveRef.current) return;
      try {
        const event = await loadProgressFallback(queryClient, historyLimitValue);
        onProgress?.(event);
        lastEventActiveRef.current = liveSecurityEvent(event);
        const terminal = terminalSecurityEvent(event);
        const keepFallbackAlive = shouldKeepSecurityFallbackAlive(event, { forceFallback, localActive: localProgressActive, activeRunId: activeRunKey });
        setEventState({ status: terminal ? 'done' : 'fallback', usingFallback: true, event });
        publishLiteLifecycleDiagnostics(liteApi);
        if (!keepFallbackAlive && (terminal || !liveSecurityEvent(event))) {
          setFallbackActive(false);
          return;
        }
      } catch {
        setEventState((state) => ({ ...state, status: 'paused', usingFallback: true }));
      }
      schedule();
    };

    tick();
    return () => {
      stopped = true;
      if (timer) window.clearTimeout(timer);
      if (timerTracked) trackLiteLifecyclePollTimer(false);
      publishLiteLifecycleDiagnostics(liteApi);
    };
  }, [activeRunKey, canObserve, fallbackActive, forceFallback, historyLimitValue, localProgressActive, onProgress, queryClient]);

  return useMemo(() => ({
    data: eventState.event ? progressPayloadFromEvent(eventState.event) : null,
    status: eventState.status,
    usingFallback: eventState.usingFallback,
    fallbackLabel: SECURITY_STREAM_FALLBACK_LABEL,
    path: liteQueryPaths.securityEvents,
  }), [eventState]);
}

export default useLiteSecurityEvents;
