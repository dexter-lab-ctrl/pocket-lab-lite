import { assign, createMachine } from 'xstate';

function boundedFailure(value) {
  return Math.max(0, Math.min(8, Number(value) || 0));
}

function retryForFailure(value) {
  const failure = boundedFailure(value);
  if (failure <= 0) return 0;
  return Math.min(30 * 60_000, 30_000 * (2 ** Math.min(failure - 1, 6)));
}

export const liteRevisionSyncMachine = createMachine({
  id: 'liteRevisionSync',
  initial: 'idle',
  context: {
    failureCount: 0,
    lastEventId: 0,
    retryAfterMs: 0,
  },
  on: {
    RESTORE: { actions: 'restoreState' },
  },
  states: {
    idle: {
      on: {
        CONNECT: 'connecting',
        OFFLINE: 'offline',
        FOLLOWER: 'follower',
      },
    },
    offline: {
      on: {
        CONNECT: 'connecting',
        FOLLOWER: 'follower',
      },
    },
    follower: {
      on: {
        CONNECT: 'connecting',
        OFFLINE: 'offline',
      },
    },
    connecting: {
      on: {
        OPEN: { target: 'open', actions: 'resetFailures' },
        ERROR: { target: 'fallback', actions: 'recordFailure' },
        OFFLINE: 'offline',
        FOLLOWER: 'follower',
      },
    },
    open: {
      on: {
        EVENT: { actions: 'recordEvent' },
        ERROR: { target: 'fallback', actions: 'recordFailure' },
        OFFLINE: 'offline',
        FOLLOWER: 'follower',
      },
    },
    fallback: {
      on: {
        RETRY: 'connecting',
        OPEN: { target: 'open', actions: 'resetFailures' },
        EVENT: { actions: 'recordEvent' },
        OFFLINE: 'offline',
        FOLLOWER: 'follower',
      },
    },
  },
}, {
  actions: {
    restoreState: assign(({ context, event }) => {
      const failureCount = boundedFailure(event.failureCount ?? context.failureCount);
      return {
        failureCount,
        retryAfterMs: retryForFailure(failureCount),
        lastEventId: Math.max(context.lastEventId, Number(event.lastEventId) || 0),
      };
    }),
    resetFailures: assign(({ context }) => ({
      failureCount: 0,
      retryAfterMs: 0,
      lastEventId: context.lastEventId,
    })),
    recordFailure: assign(({ context }) => {
      const failureCount = boundedFailure(context.failureCount + 1);
      return {
        failureCount,
        retryAfterMs: retryForFailure(failureCount),
      };
    }),
    recordEvent: assign(({ context, event }) => ({
      failureCount: 0,
      retryAfterMs: 0,
      lastEventId: Math.max(context.lastEventId, Number(event.lastEventId) || 0),
    })),
  },
});

export function revisionFallbackInterval({ value = 'idle', context = {}, visible = true, isLeader = true } = {}) {
  if (value === 'open' || value === 'offline') return false;
  const base = !visible ? 5 * 60_000 : !isLeader ? 2 * 60_000 : 60_000;
  return Math.max(base, Number(context.retryAfterMs) || 0);
}
