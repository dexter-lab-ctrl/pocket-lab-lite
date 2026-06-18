import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { eventSocketUrl, matchesPocketLabEvent, mergeEvents } from '../lib/pocketLabEvents';

export function usePocketLabEvents({
  enabled = true,
  subjectPrefixes = [],
  eventTypes = [],
  operations = [],
  jobId = '',
  limit = 50,
  replay = true,
  pollFallbackMs = 5000,
} = {}) {
  const [events, setEvents] = useState([]);
  const [connection, setConnection] = useState({ state: 'connecting', mode: 'websocket', error: '' });
  const [lastEventAt, setLastEventAt] = useState(null);
  const socketRef = useRef(null);
  const retryRef = useRef(0);
  const stoppedRef = useRef(false);

  const filters = useMemo(() => ({ subjectPrefixes, eventTypes, operations, jobId }), [
    JSON.stringify(subjectPrefixes),
    JSON.stringify(eventTypes),
    JSON.stringify(operations),
    jobId,
  ]);

  const acceptEvent = useCallback((event) => {
    if (!matchesPocketLabEvent(event, filters)) return;
    setEvents((prev) => mergeEvents(prev, [event], limit));
    setLastEventAt(event?.time || new Date().toISOString());
  }, [filters, limit]);

  const fetchRecent = useCallback(async () => {
    const prefix = subjectPrefixes.length === 1 ? `&subject_prefix=${encodeURIComponent(subjectPrefixes[0])}` : '';
    const res = await fetch(`/api/events/recent?limit=${Math.max(limit, 25)}${prefix}`, {
      cache: 'no-store',
      headers: { Accept: 'application/json' },
    });
    const text = await res.text();
    const data = JSON.parse(text || '{}');
    const incoming = Array.isArray(data.events) ? data.events.filter((event) => matchesPocketLabEvent(event, filters)) : [];
    if (incoming.length) {
      setEvents((prev) => mergeEvents(prev, incoming, limit));
      setLastEventAt(incoming[0]?.time || new Date().toISOString());
    }
  }, [filters, limit, JSON.stringify(subjectPrefixes)]);

  useEffect(() => {
    if (!enabled) return undefined;
    stoppedRef.current = false;

    if (replay) {
      fetchRecent().catch(() => {});
    }

    const connect = () => {
      if (stoppedRef.current) return;
      try {
        const ws = new WebSocket(eventSocketUrl('/ws/events'));
        socketRef.current = ws;
        setConnection({ state: 'connecting', mode: 'websocket', error: '' });

        ws.onopen = () => {
          retryRef.current = 0;
          setConnection({ state: 'connected', mode: 'websocket', error: '' });
        };

        ws.onmessage = (message) => {
          try {
            const event = JSON.parse(message.data);
            acceptEvent(event);
          } catch {
            // Ignore non-JSON payloads so one malformed event does not break live updates.
          }
        };

        ws.onerror = () => {
          setConnection({ state: 'degraded', mode: 'websocket', error: 'Live stream error' });
        };

        ws.onclose = () => {
          if (stoppedRef.current) return;
          retryRef.current += 1;
          const delay = Math.min(10000, 1000 * retryRef.current);
          setConnection({ state: 'reconnecting', mode: 'websocket', error: `Retrying in ${Math.round(delay / 1000)}s` });
          window.setTimeout(connect, delay);
        };
      } catch (err) {
        setConnection({ state: 'degraded', mode: 'polling', error: err?.message || 'WebSocket unavailable' });
      }
    };

    connect();

    const poller = window.setInterval(() => {
      const state = socketRef.current?.readyState;
      if (state !== WebSocket.OPEN) {
        setConnection((prev) => ({ ...prev, mode: 'polling' }));
        fetchRecent().catch(() => setConnection({ state: 'degraded', mode: 'polling', error: 'Recent events unavailable' }));
      }
    }, pollFallbackMs);

    return () => {
      stoppedRef.current = true;
      window.clearInterval(poller);
      if (socketRef.current) socketRef.current.close();
    };
  }, [enabled, replay, acceptEvent, fetchRecent, pollFallbackMs]);

  const clearEvents = useCallback(() => setEvents([]), []);

  return {
    events,
    latest: events[0] || null,
    connection,
    isLive: connection.state === 'connected',
    lastEventAt,
    clearEvents,
    refreshEvents: fetchRecent,
  };
}
