import { assign, setup } from 'xstate';

export const liteHotPathDiagnosticsMachine = setup({
  actions: {
    captureSuccess: assign(({ event }) => ({
      capturedAt: event.capturedAt || new Date().toISOString(),
      failureCount: 0,
    })),
    captureFailure: assign(({ context }) => ({
      failureCount: Math.min(5, context.failureCount + 1),
    })),
  },
}).createMachine({
  id: 'liteHotPathDiagnostics',
  initial: 'idle',
  context: { capturedAt: null, failureCount: 0 },
  states: {
    idle: { on: { CAPTURE: 'capturing' } },
    capturing: {
      on: {
        SUCCESS: { target: 'ready', actions: 'captureSuccess' },
        FAILURE: { target: 'degraded', actions: 'captureFailure' },
      },
    },
    ready: { on: { CAPTURE: 'capturing' } },
    degraded: { on: { RETRY: 'capturing', RESET: 'idle' } },
  },
});
