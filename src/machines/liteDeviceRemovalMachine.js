import { assign, createMachine } from 'xstate';

export const liteDeviceRemovalMachine = createMachine({
  id: 'liteDeviceRemovalFlow',
  initial: 'idle',
  context: {
    deviceId: '',
    assessmentRevision: '',
    awarenessRevision: 0,
    safeToRemove: false,
    backendReachable: true,
    savedStateOnly: false,
    failureReason: '',
  },
  on: {
    BACKEND_STATE: { actions: 'setBackendState' },
  },
  states: {
    idle: {
      on: { REVIEW: { target: 'loadingAssessment', actions: 'setDevice' } },
    },
    loadingAssessment: {
      on: {
        ASSESSMENT_READY: [
          { target: 'reviewing', guard: 'safeAssessment', actions: 'setAssessment' },
          { target: 'blocked', actions: 'setAssessment' },
        ],
        FAILED: { target: 'failed', actions: 'setFailure' },
        CANCEL: 'cancelled',
      },
    },
    reviewing: {
      on: {
        CONFIRM: [
          { target: 'confirming', guard: 'canWrite' },
          { target: 'offline', actions: 'setOfflineFailure' },
        ],
        REFRESH: 'loadingAssessment',
        CANCEL: 'cancelled',
      },
    },
    blocked: {
      on: { REFRESH: 'loadingAssessment', CANCEL: 'cancelled' },
    },
    confirming: {
      on: {
        SUBMIT: [
          { target: 'submitting', guard: 'canWrite' },
          { target: 'offline', actions: 'setOfflineFailure' },
        ],
        CANCEL: 'reviewing',
      },
    },
    submitting: {
      on: {
        ACCEPTED: 'accepted',
        COMPLETE: 'succeeded',
        STALE: { target: 'staleAssessment', actions: 'setFailure' },
        FAILED: { target: 'failed', actions: 'setFailure' },
      },
    },
    accepted: {
      on: { VERIFY: 'verifying', COMPLETE: 'succeeded', FAILED: { target: 'failed', actions: 'setFailure' } },
    },
    verifying: {
      on: { COMPLETE: 'succeeded', FAILED: { target: 'failed', actions: 'setFailure' } },
    },
    staleAssessment: {
      on: { ASSESSMENT_READY: [
        { target: 'reviewing', guard: 'safeAssessment', actions: 'setAssessment' },
        { target: 'blocked', actions: 'setAssessment' },
      ], REFRESH: 'loadingAssessment', CANCEL: 'cancelled' },
    },
    offline: { on: { REFRESH: 'loadingAssessment', CANCEL: 'cancelled' } },
    succeeded: { on: { RESET: 'idle' } },
    failed: { on: { RETRY: 'loadingAssessment', CANCEL: 'cancelled' } },
    cancelled: { always: 'idle' },
  },
}, {
  guards: {
    safeAssessment: ({ event }) => Boolean(event.assessment?.safe_to_remove),
    canWrite: ({ context }) => context.backendReachable !== false && context.savedStateOnly !== true,
  },
  actions: {
    setDevice: assign(({ event }) => ({
      deviceId: String(event.deviceId || ''),
      assessmentRevision: '',
      awarenessRevision: 0,
      safeToRemove: false,
      failureReason: '',
    })),
    setAssessment: assign(({ context, event }) => ({
      deviceId: String(event.assessment?.node_id || context.deviceId || ''),
      assessmentRevision: String(event.assessment?.assessment_revision || ''),
      awarenessRevision: Number(event.assessment?.awareness_revision || 0),
      safeToRemove: Boolean(event.assessment?.safe_to_remove),
      failureReason: '',
    })),
    setBackendState: assign(({ context, event }) => ({
      backendReachable: event.backendReachable ?? context.backendReachable,
      savedStateOnly: event.savedStateOnly ?? context.savedStateOnly,
    })),
    setOfflineFailure: assign(() => ({ failureReason: 'Reconnect to review current device responsibilities.' })),
    setFailure: assign(({ event }) => ({
      failureReason: String(event.reason || event.error?.message || 'Removal needs attention.'),
    })),
  },
});
