import { assign, createMachine } from 'xstate';

export const liteReleaseUpdateMachine = createMachine({
  id: 'liteReleaseUpdateFlow',
  initial: 'idle',
  context: {
    commandId: '',
    failureReason: '',
  },
  states: {
    idle: {
      on: {
        CHECK: 'checking',
        APPLY: 'applying',
      },
    },
    checking: {
      on: {
        ACCEPTED: { target: 'accepted', actions: 'rememberCommand' },
        FAILED: { target: 'failed', actions: 'rememberFailure' },
      },
    },
    applying: {
      on: {
        ACCEPTED: { target: 'accepted', actions: 'rememberCommand' },
        FAILED: { target: 'failed', actions: 'rememberFailure' },
      },
    },
    accepted: {
      on: {
        BACKEND_ACTIVE: 'observing',
        BACKEND_DONE: 'complete',
        BACKEND_FAILED: { target: 'failed', actions: 'rememberFailure' },
        CHECK: 'checking',
        APPLY: 'applying',
      },
    },
    observing: {
      on: {
        BACKEND_DONE: 'complete',
        BACKEND_FAILED: { target: 'failed', actions: 'rememberFailure' },
      },
    },
    complete: {
      on: {
        CHECK: 'checking',
        APPLY: 'applying',
        RESET: 'idle',
      },
    },
    failed: {
      on: {
        CHECK: 'checking',
        APPLY: 'applying',
        RESET: 'idle',
      },
    },
  },
}, {
  actions: {
    rememberCommand: assign(({ event }) => ({
      commandId: String(event.payload?.command_id || event.payload?.job_id || ''),
      failureReason: '',
    })),
    rememberFailure: assign(({ event }) => ({
      failureReason: String(event.reason || event.error?.message || 'Update needs attention.'),
    })),
  },
});
