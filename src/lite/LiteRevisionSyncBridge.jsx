import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useMachine } from '@xstate/react';
import { useLiteQuery } from '../hooks/useLiteQuery.js';
import { liteApi } from '../lib/liteApi.js';
import { getOfflineCacheMeta, setOfflineCacheMeta } from '../lib/liteOfflineDb.js';
import { liteQueryKeys, liteQueryPaths } from '../lib/liteQueryClient.js';
import {
  LITE_REVISION_CHANGED_EVENT,
  LITE_REVISION_RESET_EVENT,
  applyLiteRevisionEnvelope,
  acquireLiteRevisionLeadership,
  applyLiteRevisionSnapshot,
  createLiteRevisionBroadcast,
  createLiteRevisionSenderId,
  createLiteRevisionState,
  LITE_REVISION_LEADER_KEY,
  releaseLiteRevisionLeadership,
} from '../lib/liteRevisionSync.js';
import {
  liteRevisionSyncMachine,
  revisionFallbackInterval,
} from '../machines/liteRevisionSyncMachine.js';
import { useLiteUiStore } from '../stores/liteUiStore.js';

const REVISION_SYNC_META_KEY = 'lite_revision_sync_state_v1';

function browserOnline() {
  return typeof navigator === 'undefined' || navigator.onLine !== false;
}

function documentVisible() {
  return typeof document === 'undefined' || document.visibilityState !== 'hidden';
}

function revisionEventsUrl(lastEventId = 0) {
  if (typeof window === 'undefined') return '/api/lite/events';
  const url = new URL('/api/lite/events', window.location.origin);
  if (lastEventId > 0) url.searchParams.set('last_event_id', String(lastEventId));
  return url.toString();
}

function persistedRevisionState(state, snapshot) {
  return {
    databaseInstance: String(state.databaseInstance || '').slice(0, 64),
    lastEventId: Math.max(0, Number(state.lastEventId) || 0),
    revisions: { ...(state.revisions || {}) },
    failureCount: Math.max(0, Math.min(8, Number(snapshot.context.failureCount) || 0)),
    updatedAt: new Date().toISOString(),
  };
}

export default function LiteRevisionSyncBridge() {
  const queryClient = useQueryClient();
  const revisionState = useRef(createLiteRevisionState());
  const senderId = useRef(createLiteRevisionSenderId());
  const broadcastRef = useRef(null);
  const wasOnline = useRef(browserOnline());
  const [online, setOnline] = useState(browserOnline);
  const [visible, setVisible] = useState(documentVisible);
  const [broadcastSupported, setBroadcastSupported] = useState(
    () => typeof window !== 'undefined' && typeof window.BroadcastChannel !== 'undefined',
  );
  const [isLeader, setIsLeader] = useState(() => !broadcastSupported);
  const [syncSnapshot, sendSync] = useMachine(liteRevisionSyncMachine);
  const syncSnapshotRef = useRef(syncSnapshot);
  syncSnapshotRef.current = syncSnapshot;
  const setRevisionSyncState = useLiteUiStore((state) => state.setRevisionSyncState);
  const streamStatus = String(syncSnapshot.value || 'idle');

  const persistState = useCallback(() => {
    void setOfflineCacheMeta(
      REVISION_SYNC_META_KEY,
      persistedRevisionState(revisionState.current, syncSnapshotRef.current),
    );
  }, []);

  const processEnvelope = useCallback((envelope, { relay = false } = {}) => {
    const result = applyLiteRevisionEnvelope(queryClient, revisionState.current, envelope);
    if (result.event) {
      sendSync({ type: 'EVENT', lastEventId: revisionState.current.lastEventId });
      void setOfflineCacheMeta(REVISION_SYNC_META_KEY, {
        databaseInstance: revisionState.current.databaseInstance,
        lastEventId: revisionState.current.lastEventId,
        revisions: { ...revisionState.current.revisions },
        failureCount: 0,
        updatedAt: new Date().toISOString(),
      });
    }
    if (result.accepted && relay) broadcastRef.current?.post(result.event);
    return result;
  }, [queryClient, sendSync]);

  useEffect(() => {
    let cancelled = false;
    void getOfflineCacheMeta(REVISION_SYNC_META_KEY).then((saved) => {
      if (cancelled || !saved || typeof saved !== 'object') return;
      revisionState.current = createLiteRevisionState({
        databaseInstance: saved.databaseInstance,
        lastEventId: saved.lastEventId,
        revisions: saved.revisions,
      });
      sendSync({
        type: 'RESTORE',
        failureCount: saved.failureCount,
        lastEventId: saved.lastEventId,
      });
    });
    return () => { cancelled = true; };
  }, [sendSync]);

  useEffect(() => {
    setRevisionSyncState({
      status: streamStatus,
      failureCount: syncSnapshot.context.failureCount,
      lastEventId: Math.max(syncSnapshot.context.lastEventId, revisionState.current.lastEventId),
      retryAfterMs: syncSnapshot.context.retryAfterMs,
    });
    persistState();
  }, [persistState, setRevisionSyncState, streamStatus, syncSnapshot.context.failureCount, syncSnapshot.context.lastEventId, syncSnapshot.context.retryAfterMs]);

  useEffect(() => {
    const broadcast = createLiteRevisionBroadcast({
      senderId: senderId.current,
      onEnvelope: (envelope) => processEnvelope(envelope, { relay: false }),
    });
    broadcastRef.current = broadcast;
    setBroadcastSupported(broadcast.supported);
    return () => {
      broadcast.close();
      broadcastRef.current = null;
    };
  }, [processEnvelope]);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const updateOnline = () => setOnline(browserOnline());
    const updateVisibility = () => setVisible(documentVisible());
    window.addEventListener('online', updateOnline);
    window.addEventListener('offline', updateOnline);
    document.addEventListener('visibilitychange', updateVisibility);
    return () => {
      window.removeEventListener('online', updateOnline);
      window.removeEventListener('offline', updateOnline);
      document.removeEventListener('visibilitychange', updateVisibility);
    };
  }, []);

  useEffect(() => {
    if (!online || !visible) {
      if (typeof window !== 'undefined') {
        releaseLiteRevisionLeadership(window.localStorage, senderId.current);
      }
      setIsLeader(false);
      return undefined;
    }
    if (!broadcastSupported || typeof window === 'undefined') {
      setIsLeader(true);
      return undefined;
    }
    let stopped = false;
    const refreshLeadership = () => {
      if (stopped) return;
      setIsLeader(acquireLiteRevisionLeadership(window.localStorage, senderId.current));
    };
    const storageChanged = (event) => {
      if (event.key === LITE_REVISION_LEADER_KEY) refreshLeadership();
    };
    refreshLeadership();
    const timer = window.setInterval(refreshLeadership, 7_000);
    window.addEventListener('storage', storageChanged);
    return () => {
      stopped = true;
      window.clearInterval(timer);
      window.removeEventListener('storage', storageChanged);
      releaseLiteRevisionLeadership(window.localStorage, senderId.current);
    };
  }, [broadcastSupported, online, visible]);

  useEffect(() => {
    if (!online) {
      sendSync({ type: 'OFFLINE' });
      return;
    }
    if (!visible || !isLeader) {
      sendSync({ type: 'FOLLOWER' });
      return;
    }
    if (['idle', 'offline', 'follower'].includes(streamStatus)) {
      sendSync({ type: 'CONNECT' });
    }
  }, [isLeader, online, sendSync, streamStatus, visible]);

  useEffect(() => {
    if (streamStatus !== 'fallback' || !online || !visible || !isLeader || typeof window === 'undefined') {
      return undefined;
    }
    const delay = Math.max(30_000, Number(syncSnapshot.context.retryAfterMs) || 30_000);
    const timer = window.setTimeout(() => sendSync({ type: 'RETRY' }), delay);
    return () => window.clearTimeout(timer);
  }, [isLeader, online, sendSync, streamStatus, syncSnapshot.context.retryAfterMs, visible]);

  const fallbackInterval = useMemo(() => revisionFallbackInterval({
    value: streamStatus,
    context: syncSnapshot.context,
    visible,
    isLeader,
  }), [isLeader, streamStatus, syncSnapshot.context, visible]);

  const revisions = useLiteQuery({
    queryKey: liteQueryKeys.domainRevisions(),
    path: liteQueryPaths.domainRevisions,
    queryFn: liteApi.domainRevisions,
    enabled: online,
    staleTime: streamStatus === 'open' ? 5 * 60_000 : 30_000,
    gcTime: 30 * 60_000,
    refetchInterval: fallbackInterval,
    enabledWhenHidden: false,
    refetchOnReconnect: true,
    refetchOnMount: true,
    placeholderData: (previous) => previous,
  });

  useEffect(() => {
    if (!revisions.data || revisions.data.__liteNotModified) return;
    const result = applyLiteRevisionSnapshot(queryClient, revisionState.current, revisions.data);
    if (!result.accepted || !result.changed) return;
    sendSync({ type: 'EVENT', lastEventId: revisionState.current.lastEventId });
    persistState();
  }, [persistState, queryClient, revisions.data, sendSync]);

  useEffect(() => {
    if (online && !wasOnline.current) {
      queryClient.invalidateQueries({
        queryKey: liteQueryKeys.domainRevisions(),
        exact: true,
        refetchType: 'active',
      });
    }
    wasOnline.current = online;
  }, [online, queryClient]);

  useEffect(() => {
    if (streamStatus !== 'connecting' || !online || !visible || !isLeader
      || typeof window === 'undefined' || typeof window.EventSource === 'undefined') {
      return undefined;
    }
    const source = new window.EventSource(revisionEventsUrl(revisionState.current.lastEventId));
    let closed = false;
    const consume = (message) => {
      if (closed) return;
      try {
        processEnvelope(JSON.parse(message.data || '{}'), { relay: true });
      } catch {
        // Invalid event data is ignored; TanStack fallback reads remain available.
      }
    };
    const opened = () => sendSync({ type: 'OPEN' });
    const failed = () => {
      if (closed) return;
      closed = true;
      source.close();
      sendSync({ type: 'ERROR' });
    };
    source.addEventListener('open', opened);
    source.addEventListener(LITE_REVISION_CHANGED_EVENT, consume);
    source.addEventListener(LITE_REVISION_RESET_EVENT, consume);
    source.addEventListener('error', failed);
    return () => {
      closed = true;
      source.removeEventListener('open', opened);
      source.removeEventListener(LITE_REVISION_CHANGED_EVENT, consume);
      source.removeEventListener(LITE_REVISION_RESET_EVENT, consume);
      source.removeEventListener('error', failed);
      source.close();
    };
  }, [isLeader, online, processEnvelope, sendSync, streamStatus, visible]);

  return null;
}
