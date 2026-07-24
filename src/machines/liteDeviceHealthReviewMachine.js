import { assign, createMachine } from 'xstate';
import { isBackendReachable } from './liteFlowGuards.js';

export const LITE_DEVICE_HEALTH_REVIEW_BACKEND_AUTHORITATIVE_D4 = true;
export const LITE_DEVICE_HEALTH_REVIEW_NO_AUTOMATIC_REPAIR_D4 = true;

function isWaitRecommendation(context = {}) {
  return String(context.recommendation || '').toLowerCase() === 'wait_for_recovery';
}

function backendConfirmedResolved(context = {}, event = {}) {
  const status = String(event.status || '').toLowerCase().replace(/[\s-]+/g, '_');
  const revision = String(event.healthRevision || '');
  return Boolean(
    isBackendReachable(context)
    && revision
    && revision !== String(context.healthRevision || '')
    && ['healthy', 'watch', 'unknown'].includes(status)
    && Number(event.attentionCount || 0) === 0
  );
}

export const liteDeviceHealthReviewMachine = createMachine({
  id: 'liteDeviceHealthReview',
  initial: 'idle',
  context: {
    nodeId: '',
    healthRevision: '',
    recommendation: 'review_device',
    backendReachable: true,
    savedStateOnly: false,
    failureReason: '',
  },
  states: {
    idle: {
      on: {
        REVIEW: { target: 'reviewing', actions: 'setReview' },
      },
    },
    reviewing: {
      always: [
        { target: 'offline', guard: 'reviewBlocked' },
        { target: 'waitingForRecovery', guard: 'waitRecommendation' },
        { target: 'actionAvailable' },
      ],
      on: { CANCEL: 'cancelled' },
    },
    actionAvailable: {
      on: {
        ROUTE: 'routing',
        BACKEND_STATE: { target: 'reviewing', actions: 'setBackendState' },
        CANCEL: 'cancelled',
      },
    },
    routing: {
      on: {
        ROUTED: 'actionAvailable',
        FAILED: { target: 'failed', actions: 'setFailure' },
      },
    },
    waitingForRecovery: {
      on: {
        BACKEND_CONFIRMED: [
          { target: 'resolved', guard: 'backendResolved', actions: 'setBackendState' },
          { target: 'waitingForRecovery', actions: 'setBackendState' },
        ],
        BACKEND_STATE: { target: 'reviewing', actions: 'setBackendState' },
        CANCEL: 'cancelled',
      },
    },
    offline: {
      on: {
        BACKEND_STATE: { target: 'reviewing', guard: 'eventBackendReachable', actions: 'setBackendState' },
        REVIEW: { target: 'reviewing', actions: 'setReview' },
        CANCEL: 'cancelled',
      },
    },
    resolved: {
      on: {
        REVIEW: { target: 'reviewing', actions: 'setReview' },
        RESET: 'idle',
      },
    },
    failed: {
      on: {
        REVIEW: { target: 'reviewing', actions: 'setReview' },
        RESET: 'idle',
      },
    },
    cancelled: {
      on: {
        REVIEW: { target: 'reviewing', actions: 'setReview' },
        RESET: 'idle',
      },
    },
  },
}, {
  guards: {
    reviewBlocked: ({ context }) => !isBackendReachable(context),
    waitRecommendation: ({ context }) => isWaitRecommendation(context),
    backendResolved: ({ context, event }) => backendConfirmedResolved(context, event),
    eventBackendReachable: ({ event }) => event.backendReachable !== false && event.savedStateOnly !== true,
  },
  actions: {
    setReview: assign(({ context, event }) => ({
      nodeId: String(event.nodeId || context.nodeId || ''),
      healthRevision: String(event.healthRevision || context.healthRevision || ''),
      recommendation: String(event.recommendation || context.recommendation || 'review_device'),
      backendReachable: event.backendReachable ?? context.backendReachable,
      savedStateOnly: event.savedStateOnly ?? context.savedStateOnly,
      failureReason: '',
    })),
    setBackendState: assign(({ context, event }) => ({
      healthRevision: String(event.healthRevision || context.healthRevision || ''),
      backendReachable: event.backendReachable ?? context.backendReachable,
      savedStateOnly: event.savedStateOnly ?? context.savedStateOnly,
    })),
    setFailure: assign(({ event }) => ({
      failureReason: String(event.reason || 'Health review needs attention.'),
    })),
  },
});
