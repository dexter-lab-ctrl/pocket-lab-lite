import { assign, createMachine } from 'xstate';
import { acceptedReference, friendlyFlowError, isBackendReachable } from './liteFlowGuards.js';

const backendStateEvent = { actions: 'setBackendState' };
const failureEvent = { target: 'failed', actions: 'setFailure' };
const capacityEvent = { target: 'waitingForCapacity', actions: 'setCapacityState' };
const degradedEvent = { target: 'degradedVisibility', actions: 'setDegradedState' };

export const liteSecurityCheckMachine = createMachine({
  id: 'liteSecurityCheckFlow',
  initial: 'idle',
  context: {
    backendReachable: true,
    savedStateOnly: false,
    runId: null,
    failureReason: '',
    lastKnownStatus: '',
    loadState: 'normal',
    degradedReason: '',
    retryAfterMs: 0,
  },
  on: {
    BACKEND_STATE: backendStateEvent,
  },
  states: {
    idle: {
      on: { CHECK_READINESS: 'checkingReadiness' },
    },
    checkingReadiness: {
      on: {
        RUN: { target: 'requestAccepted', guard: 'backendReachable' },
        CAPACITY_WAIT: capacityEvent,
        DEGRADED_VISIBILITY: degradedEvent,
        SAVED_STATE_ONLY: 'savedStateOnly',
        BLOCKED: { target: 'blocked', actions: 'setFailure' },
      },
    },
    requestAccepted: {
      on: {
        ACCEPTED: { target: 'queued', actions: 'setAccepted' },
        WORKER_PICKED_UP: 'workerPickedUp',
        CAPACITY_WAIT: capacityEvent,
        DEGRADED_VISIBILITY: degradedEvent,
        FAILED: failureEvent,
      },
    },
    queued: {
      on: {
        WORKER_PICKED_UP: 'workerPickedUp',
        LYNIS_RUNNING: 'lynisRunning',
        CAPACITY_WAIT: capacityEvent,
        DEGRADED_VISIBILITY: degradedEvent,
        COMPLETE: 'complete',
        FAILED: failureEvent,
      },
    },
    waitingForCapacity: {
      on: {
        CAPACITY_READY: 'queued',
        ACCEPTED: { target: 'queued', actions: 'setAccepted' },
        WORKER_PICKED_UP: 'workerPickedUp',
        DEGRADED_VISIBILITY: degradedEvent,
        SAVED_STATE_ONLY: 'savedStateOnly',
        FAILED: failureEvent,
        RESET: 'idle',
      },
    },
    degradedVisibility: {
      on: {
        RECOVERED: 'idle',
        CAPACITY_WAIT: capacityEvent,
        WORKER_PICKED_UP: 'workerPickedUp',
        LYNIS_RUNNING: 'lynisRunning',
        TRIVY_RUNNING: 'trivyRunning',
        EVIDENCE_SAVING: 'evidenceSaving',
        EVIDENCE_SAVED: 'evidenceSaved',
        COMPLETE: 'complete',
        NEEDS_ATTENTION: 'needsAttention',
        SAVED_STATE_ONLY: 'savedStateOnly',
        FAILED: failureEvent,
        RESET: 'idle',
      },
    },
    workerPickedUp: {
      on: {
        LYNIS_RUNNING: 'lynisRunning',
        TRIVY_RUNNING: 'trivyRunning',
        EVIDENCE_SAVING: 'evidenceSaving',
        CAPACITY_WAIT: capacityEvent,
        DEGRADED_VISIBILITY: degradedEvent,
        COMPLETE: 'complete',
        FAILED: failureEvent,
      },
    },
    lynisRunning: {
      on: {
        TRIVY_RUNNING: 'trivyRunning',
        EVIDENCE_SAVING: 'evidenceSaving',
        DEGRADED_VISIBILITY: degradedEvent,
        PARTIAL_RESULTS: 'partialResults',
        FAILED: failureEvent,
      },
    },
    trivyRunning: {
      on: {
        EVIDENCE_SAVING: 'evidenceSaving',
        EVIDENCE_SAVED: 'evidenceSaved',
        DEGRADED_VISIBILITY: degradedEvent,
        PARTIAL_RESULTS: 'partialResults',
        FAILED: failureEvent,
      },
    },
    evidenceSaving: {
      on: {
        EVIDENCE_SAVED: 'evidenceSaved',
        COMPLETE: 'complete',
        NEEDS_ATTENTION: 'needsAttention',
        DEGRADED_VISIBILITY: degradedEvent,
        FAILED: failureEvent,
      },
    },
    evidenceSaved: { on: { COMPLETE: 'complete', NEEDS_ATTENTION: 'needsAttention', RESET: 'idle' } },
    complete: { on: { RUN: 'checkingReadiness', RESET: 'idle' } },
    needsAttention: { on: { RUN: 'checkingReadiness', RESET: 'idle' } },
    partialResults: { on: { EVIDENCE_SAVED: 'evidenceSaved', NEEDS_ATTENTION: 'needsAttention', RUN: 'checkingReadiness' } },
    staleRun: { on: { RUN: 'checkingReadiness', RESET: 'idle' } },
    savedStateOnly: { on: { RESET: 'idle', RECOVERED: 'idle' } },
    backendUnreachable: { on: { RESET: 'idle', RECOVERED: 'idle' } },
    blocked: { on: { RUN: 'checkingReadiness', RESET: 'idle' } },
    failed: { on: { RUN: 'checkingReadiness', RESET: 'idle' } },
    cancelled: { on: { RESET: 'idle' } },
  },
}, {
  guards: {
    backendReachable: ({ context }) => isBackendReachable(context),
  },
  actions: {
    setAccepted: assign(({ context, event }) => ({
      runId: event.payload?.run_id || acceptedReference(event.payload || {}) || context.runId,
      lastKnownStatus: event.payload?.status || context.lastKnownStatus,
      failureReason: '',
      loadState: String(event.payload?.load_state || context.loadState || 'normal'),
      degradedReason: String(event.payload?.degraded_reason || ''),
      retryAfterMs: Number(event.payload?.retry_after_ms || 0),
    })),
    setBackendState: assign(({ context, event }) => ({
      backendReachable: event.backendReachable ?? context.backendReachable,
      savedStateOnly: event.savedStateOnly ?? context.savedStateOnly,
      runId: event.runId ?? context.runId,
      lastKnownStatus: event.status ?? context.lastKnownStatus,
      loadState: String(event.loadState || context.loadState || 'normal'),
      degradedReason: String(event.degradedReason || context.degradedReason || ''),
      retryAfterMs: Number(event.retryAfterMs ?? context.retryAfterMs) || 0,
    })),
    setCapacityState: assign(({ context, event }) => ({
      loadState: String(event.loadState || 'capacity'),
      degradedReason: String(event.reason || event.degradedReason || 'worker_capacity'),
      retryAfterMs: Number(event.retryAfterMs || context.retryAfterMs || 2_000),
      failureReason: '',
    })),
    setDegradedState: assign(({ context, event }) => ({
      loadState: String(event.loadState || context.loadState || 'elevated'),
      degradedReason: String(event.reason || event.degradedReason || 'prepared_state_degraded'),
      retryAfterMs: Number(event.retryAfterMs || context.retryAfterMs || 0),
      failureReason: '',
    })),
    setFailure: assign(({ event }) => ({
      failureReason: event.reason || friendlyFlowError(event.error, 'Safety check needs attention.'),
    })),
  },
});

export const liteSecurityCheckLabels = {
  idle: 'Run Safety Check',
  checkingReadiness: 'Getting ready',
  requestAccepted: 'Request accepted',
  queued: 'Request accepted',
  waitingForCapacity: 'Waiting for capacity',
  degradedVisibility: 'Showing latest safe state',
  workerPickedUp: 'Worker picked it up',
  lynisRunning: 'Lynis host check',
  trivyRunning: 'Trivy dependency & secret check',
  evidenceSaving: 'Evidence saving',
  evidenceSaved: 'Evidence saved',
  complete: 'Safety check complete',
  needsAttention: 'Needs attention',
  partialResults: 'Needs attention',
  staleRun: 'Saved state only',
  savedStateOnly: 'Saved state only',
  backendUnreachable: 'Reconnect to continue',
  blocked: 'Needs attention',
  failed: 'Needs attention',
  cancelled: 'Dismissed',
};

export function securityCheckFlowSteps(value) {
  const current = String(value || 'idle');
  const afterRequest = ['workerPickedUp', 'lynisRunning', 'trivyRunning', 'evidenceSaving', 'evidenceSaved', 'complete', 'needsAttention'];
  const afterWorker = ['lynisRunning', 'trivyRunning', 'evidenceSaving', 'evidenceSaved', 'complete', 'needsAttention'];
  const afterLynis = ['trivyRunning', 'evidenceSaving', 'evidenceSaved', 'complete', 'needsAttention'];
  const afterTrivy = ['evidenceSaving', 'evidenceSaved', 'complete', 'needsAttention'];
  return [
    { id: 'request', label: 'Request accepted', state: ['requestAccepted', 'queued', 'waitingForCapacity'].includes(current) ? 'active' : afterRequest.includes(current) ? 'done' : 'waiting' },
    { id: 'worker', label: current === 'waitingForCapacity' ? 'Waiting for capacity' : 'Worker picked it up', state: current === 'workerPickedUp' || current === 'waitingForCapacity' ? 'active' : afterWorker.includes(current) ? 'done' : 'waiting' },
    { id: 'lynis', label: 'Lynis host check', state: current === 'lynisRunning' ? 'active' : afterLynis.includes(current) ? 'done' : 'waiting' },
    { id: 'trivy', label: 'Trivy dependency & secret check', state: current === 'trivyRunning' ? 'active' : afterTrivy.includes(current) ? 'done' : 'waiting' },
    { id: 'evidence', label: 'Evidence saved', state: current === 'evidenceSaving' ? 'active' : ['evidenceSaved', 'complete', 'needsAttention'].includes(current) ? 'done' : current === 'failed' ? 'failed' : 'waiting' },
  ];
}
