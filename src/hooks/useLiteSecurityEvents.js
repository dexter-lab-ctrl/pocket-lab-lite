import { useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { liteApi } from '../lib/liteApi.js';
import { broadcastLiteSecurityScanCompleted } from '../lib/liteSafeSnapshots.js';
import { liteQueryKeys, liteQueryPaths } from '../lib/liteQueryClient.js';
import {
  acceptSecurityProgressEvent,
  activeSecurityProgress,
  normalizeSecurityProgressEvent,
  progressPayloadFromSecurityEvent,
  terminalSecurityProgress,
} from '../lib/securityProgressEvents.js';
import {
  publishLiteLifecycleDiagnostics,
  reconcileLiteSecurityProgress,
  recordLiteSecurityFallbackActivation,
  recordLiteSecurityProgressDecision,
  trackLiteLifecycleEventSource,
  trackLiteLifecycleListener,
  trackLiteLifecyclePollTimer,
  updateLiteLifecycleEnvironment,
} from '../lib/liteLifecycleDiagnostics.js';

const API_BASE = (import.meta.env.VITE_POCKETLAB_API_BASE || '').replace(/\/$/, '');
const SECURITY_EVENTS_PATH = '/api/lite/security/events';
const SECURITY_PROGRESS_FALLBACK_MS = 3000;
const SECURITY_STREAM_FALLBACK_LABEL = 'Using backup progress check';
const SECURITY_EVENT_TYPES = [
  'security.scan.snapshot',
  'security.scan.queued',
  'security.scan.started',
  'security.scan.stage',
  'security.scan.progress',
  'security.scan.evidence_saved',
  'security.scan.completed',
  'security.scan.failed',
  'security.scan.cancelled',
  'security.scan.heartbeat',
];

function endpoint(path) {
  return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
}

function normalizeProfile(profile = 'quick') {
  const value = String(profile || 'quick').trim().toLowerCase();
  return ['quick', 'full', 'app'].includes(value) ? value : 'quick';
}

function securityEventMatchesActiveRun(event = {}, activeRunId = '') {
  const expected = String(activeRunId || '').trim();
  if (!expected) return false;
  const actual = String(event?.run_id || event?.command_id || event?.job_id || '').trim();
  return Boolean(actual && actual === expected);
}

function shouldKeepSecurityFallbackAlive(event = {}, { forceFallback = false, localActive = false, activeRunId = '' } = {}) {
  if (!forceFallback && !localActive) return activeSecurityProgress(event);
  if (activeSecurityProgress(event)) return true;
  if (!terminalSecurityProgress(event)) return Boolean(forceFallback || localActive);
  if (!localActive) return false;
  return !securityEventMatchesActiveRun(event, activeRunId);
}

function typeFromProgress(progress = {}) {
  const status = String(progress.status || '').toLowerCase();
  if (status === 'failed') return 'security.scan.failed';
  if (status === 'cancelled' || status === 'canceled') return 'security.scan.cancelled';
  if (terminalSecurityProgress(progress)) return 'security.scan.completed';
  if (status === 'queued' || status === 'accepted' || status === 'waiting') return 'security.scan.queued';
  if (activeSecurityProgress(progress)) return 'security.scan.progress';
  return 'security.scan.snapshot';
}

function broadcastTerminalSecurityEvent(payload = {}) {
  if (!terminalSecurityProgress(payload) || payload.snapshot) return null;
  return broadcastLiteSecurityScanCompleted(payload.profile || 'quick', {
    run_id: payload.run_id || '',
    status: payload.status || 'completed',
    completed_at: payload.updated_at || null,
    updated_at: payload.updated_at || null,
  }, { source: 'security-events-stream', requireTerminal: false });
}

function invalidateTerminalSecurityQueries(queryClient, payload, historyLimit) {
  const profile = normalizeProfile(payload.profile);
  const runId = payload.run_id || 'latest';
  queryClient.invalidateQueries({ queryKey: liteQueryKeys.security() });
  queryClient.invalidateQueries({ queryKey: liteQueryKeys.securityFreshness() });
  queryClient.invalidateQueries({ queryKey: liteQueryKeys.securityProfile(profile) });
  queryClient.invalidateQueries({ queryKey: liteQueryKeys.securityHistory(historyLimit || 20) });
  queryClient.invalidateQueries({ queryKey: liteQueryKeys.securityProgress() });
  queryClient.invalidateQueries({ queryKey: liteQueryKeys.securityEvidenceSummary(runId) });
  queryClient.invalidateQueries({ queryKey: liteQueryKeys.securityRunDetails(runId) });
}

function acceptAndApplySecurityEvent(queryClient, event, historyLimit = 20) {
  const incoming = normalizeSecurityProgressEvent(event);
  if (incoming.type === 'security.scan.heartbeat') {
    return { decision: { accepted: false, reason: 'heartbeat', value: null }, payload: null };
  }
  const previous = queryClient.getQueryData(liteQueryKeys.securityProgress()) || null;
  const decision = acceptSecurityProgressEvent(previous, incoming);
  recordLiteSecurityProgressDecision(decision, incoming);
  if (!decision.accepted) return { decision, payload: decision.value };
  const payload = progressPayloadFromSecurityEvent(decision.value);
  queryClient.setQueryData(liteQueryKeys.securityProgress(), payload);
  reconcileLiteSecurityProgress({
    cachedProgress: previous || {},
    backendProgress: payload,
    writeActionsBlocked: false,
  });
  if (terminalSecurityProgress(payload)) {
    broadcastTerminalSecurityEvent(payload);
    invalidateTerminalSecurityQueries(queryClient, payload, historyLimit);
  } else if (incoming.type === 'security.scan.evidence_saved') {
    const runId = payload.run_id || 'latest';
    queryClient.invalidateQueries({ queryKey: liteQueryKeys.securityEvidenceSummary(runId) });
    queryClient.invalidateQueries({ queryKey: liteQueryKeys.securityRunDetails(runId) });
  }
  return { decision, payload };
}

async function loadProgressFallback(queryClient, historyLimit) {
  const progress = await liteApi.securityProgress();
  return acceptAndApplySecurityEvent(queryClient, {
    ...progress,
    type: typeFromProgress(progress),
    source: 'security_progress_json',
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
  const sourceActiveRef = useRef(false);
  const fallbackActiveRef = useRef(false);
  const environment = useSecurityLifecycleEnvironment();
  const historyLimitValue = Number(historyLimit || 20);
  const profileValue = normalizeProfile(profile);
  const activeRunKey = String(activeRunId || '').trim();
  const localProgressActive = Boolean(localActive);
  const canObserve = Boolean(enabled && environment.visible && environment.online);
  const activateFallback = () => {
    if (!fallbackActiveRef.current) recordLiteSecurityFallbackActivation();
    fallbackActiveRef.current = true;
    setFallbackActive(true);
  };

  useEffect(() => {
    if (!canObserve) {
      fallbackActiveRef.current = false;
      setFallbackActive(false);
      setEventState((state) => ({ ...state, status: enabled ? 'paused' : 'idle', usingFallback: false }));
      return undefined;
    }
    if (typeof window === 'undefined' || typeof window.EventSource === 'undefined') {
      activateFallback();
      return undefined;
    }

    let disposed = false;
    const source = new window.EventSource(endpoint(SECURITY_EVENTS_PATH));
    sourceActiveRef.current = true;
    trackLiteLifecycleEventSource(true);
    setEventState((state) => ({ ...state, status: 'connecting', usingFallback: false }));
    publishLiteLifecycleDiagnostics(liteApi);

    const disposeSource = () => {
      if (disposed) return;
      disposed = true;
      source.close();
      sourceActiveRef.current = false;
      trackLiteLifecycleEventSource(false);
      publishLiteLifecycleDiagnostics(liteApi);
    };

    source.onopen = () => {
      if (disposed) return;
      fallbackActiveRef.current = false;
      setFallbackActive(false);
      setEventState((state) => ({ ...state, status: 'connected', usingFallback: false }));
      publishLiteLifecycleDiagnostics(liteApi);
    };

    const handleMessage = (message) => {
      if (disposed) return;
      try {
        const event = normalizeSecurityProgressEvent(JSON.parse(message.data || '{}'));
        if (event.type === 'security.scan.heartbeat') {
          setEventState((state) => ({ ...state, status: 'connected', usingFallback: false }));
          return;
        }
        const { decision, payload } = acceptAndApplySecurityEvent(queryClient, event, historyLimitValue);
        if (decision.accepted && payload) {
          onProgress?.(payload);
          setEventState({ status: terminalSecurityProgress(payload) ? 'done' : 'connected', usingFallback: false, event: payload });
        }
        publishLiteLifecycleDiagnostics(liteApi);
      } catch {
        activateFallback();
        setEventState((state) => ({ ...state, status: 'paused', usingFallback: true }));
      }
    };

    source.onmessage = handleMessage;
    SECURITY_EVENT_TYPES.forEach((eventName) => source.addEventListener(eventName, handleMessage));
    source.onerror = () => {
      if (disposed) return;
      // Native EventSource owns reconnect and automatically sends Last-Event-ID.
      // Polling is a bounded handover only; onopen stops it again.
      activateFallback();
      setEventState((state) => ({ ...state, status: 'paused', usingFallback: true }));
      publishLiteLifecycleDiagnostics(liteApi);
    };
    return disposeSource;
  }, [activeRunKey, canObserve, enabled, environment.online, environment.visible, historyLimitValue, localProgressActive, onProgress, profileValue, queryClient]);

  useEffect(() => {
    if (!canObserve || sourceActiveRef.current && !fallbackActive || (!fallbackActive && !forceFallback)) return undefined;
    let stopped = false;
    let timer;
    let timerTracked = false;

    const schedule = () => {
      if (stopped || (!fallbackActive && !forceFallback)) return;
      timer = window.setTimeout(tick, SECURITY_PROGRESS_FALLBACK_MS);
      if (!timerTracked) {
        timerTracked = true;
        trackLiteLifecyclePollTimer(true);
        publishLiteLifecycleDiagnostics(liteApi);
      }
    };
    const tick = async () => {
      if (stopped || (!fallbackActive && !forceFallback)) return;
      try {
        const { decision, payload } = await loadProgressFallback(queryClient, historyLimitValue);
        if (decision.accepted && payload) {
          onProgress?.(payload);
          setEventState({ status: terminalSecurityProgress(payload) ? 'done' : 'fallback', usingFallback: true, event: payload });
          const keepFallbackAlive = shouldKeepSecurityFallbackAlive(payload, {
            forceFallback,
            localActive: localProgressActive,
            activeRunId: activeRunKey,
          });
          if (!keepFallbackAlive) {
            fallbackActiveRef.current = false;
            setFallbackActive(false);
            return;
          }
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
    data: eventState.event || null,
    status: eventState.status,
    usingFallback: eventState.usingFallback,
    fallbackLabel: SECURITY_STREAM_FALLBACK_LABEL,
    path: liteQueryPaths.securityEvents,
  }), [eventState]);
}

export default useLiteSecurityEvents;
