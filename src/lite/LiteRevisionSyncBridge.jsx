import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useLiteQuery } from '../hooks/useLiteQuery.js';
import { liteApi } from '../lib/liteApi.js';
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

export default function LiteRevisionSyncBridge() {
  const queryClient = useQueryClient();
  const revisionState = useRef(createLiteRevisionState());
  const senderId = useRef(createLiteRevisionSenderId());
  const broadcastRef = useRef(null);
  const wasOnline = useRef(browserOnline());
  const [online, setOnline] = useState(browserOnline);
  const [visible, setVisible] = useState(documentVisible);
  const [streamStatus, setStreamStatus] = useState('idle');
  const [broadcastSupported, setBroadcastSupported] = useState(
    () => typeof window !== 'undefined' && typeof window.BroadcastChannel !== 'undefined',
  );
  const [isLeader, setIsLeader] = useState(() => !broadcastSupported);

  const processEnvelope = useCallback((envelope, { relay = false } = {}) => {
    const result = applyLiteRevisionEnvelope(queryClient, revisionState.current, envelope);
    if (result.accepted && relay) broadcastRef.current?.post(result.event);
    return result;
  }, [queryClient]);

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
      const acquired = acquireLiteRevisionLeadership(window.localStorage, senderId.current);
      setIsLeader(acquired);
      if (!acquired) setStreamStatus('follower');
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

  const fallbackInterval = useMemo(() => {
    if (!online) return false;
    if (streamStatus === 'open') return false;
    if (!visible) return 120_000;
    if (!isLeader) return 60_000 + Math.floor(Math.random() * 7_500);
    return 30_000 + Math.floor(Math.random() * 7_500);
  }, [isLeader, online, streamStatus, visible]);

  const revisions = useLiteQuery({
    queryKey: liteQueryKeys.domainRevisions(),
    path: liteQueryPaths.domainRevisions,
    queryFn: liteApi.domainRevisions,
    enabled: online,
    staleTime: streamStatus === 'open' ? 120_000 : 10_000,
    gcTime: 30 * 60_000,
    refetchInterval: fallbackInterval,
    enabledWhenHidden: false,
    refetchOnReconnect: true,
    refetchOnMount: true,
    placeholderData: (previous) => previous,
  });

  useEffect(() => {
    if (!revisions.data || revisions.data.__liteNotModified) return;
    applyLiteRevisionSnapshot(queryClient, revisionState.current, revisions.data);
  }, [queryClient, revisions.data]);

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
    if (!online || !visible || !isLeader || typeof window === 'undefined' || typeof window.EventSource === 'undefined') {
      setStreamStatus(!online ? 'offline' : isLeader ? 'fallback' : 'follower');
      return undefined;
    }
    const source = new window.EventSource(revisionEventsUrl(revisionState.current.lastEventId));
    let closed = false;
    const consume = (message) => {
      if (closed) return;
      try {
        processEnvelope(JSON.parse(message.data || '{}'), { relay: true });
      } catch {
        // Invalid event data is ignored; revisions polling remains the recovery path.
      }
    };
    const opened = () => setStreamStatus('open');
    const failed = () => setStreamStatus('fallback');
    source.addEventListener('open', opened);
    source.addEventListener(LITE_REVISION_CHANGED_EVENT, consume);
    source.addEventListener(LITE_REVISION_RESET_EVENT, consume);
    source.addEventListener('error', failed);
    setStreamStatus('connecting');
    return () => {
      closed = true;
      source.removeEventListener('open', opened);
      source.removeEventListener(LITE_REVISION_CHANGED_EVENT, consume);
      source.removeEventListener(LITE_REVISION_RESET_EVENT, consume);
      source.removeEventListener('error', failed);
      source.close();
    };
  }, [isLeader, online, processEnvelope, visible]);

  return null;
}
