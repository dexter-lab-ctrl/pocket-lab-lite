import { assign, createMachine } from 'xstate';

export const liteDeviceModelMachine = createMachine({
  id: 'liteDeviceModelFlow',
  initial: 'idle',
  context: { deviceId: '', candidate: '', confirmed: '', failureReason: '' },
  states: {
    idle: { on: { OPEN: { target: 'editing', actions: 'open' } } },
    editing: {
      on: {
        CHANGE: { actions: 'change' },
        REVIEW: { target: 'confirming', actions: 'change' },
        CLEAR: { target: 'confirming', actions: 'clear' },
        BACKEND_UNREACHABLE: { target: 'backendUnreachable', actions: 'fail' },
        CANCEL: 'idle',
      },
    },
    confirming: { on: { CONFIRM: 'saving', EDIT: 'editing', CANCEL: 'idle' } },
    saving: { on: { SUCCEEDED: { target: 'succeeded', actions: 'succeed' }, FAILED: { target: 'failed', actions: 'fail' } } },
    succeeded: { on: { CLOSE: 'idle', CHANGE: { target: 'editing', actions: 'change' } } },
    failed: { on: { RETRY: 'confirming', EDIT: 'editing', CANCEL: 'idle' } },
    backendUnreachable: { on: { RETRY: 'editing', CANCEL: 'idle' } },
  },
}, {
  actions: {
    open: assign(({ event }) => ({ deviceId: String(event.deviceId || ''), candidate: String(event.current || ''), confirmed: '', failureReason: '' })),
    change: assign(({ context, event }) => ({ candidate: String(event.value ?? context.candidate).slice(0, 80), confirmed: String(event.value ?? context.candidate).slice(0, 80), failureReason: '' })),
    clear: assign(() => ({ candidate: '', confirmed: '', failureReason: '' })),
    succeed: assign(({ context, event }) => ({ candidate: String(event.value ?? context.confirmed), confirmed: String(event.value ?? context.confirmed), failureReason: '' })),
    fail: assign(({ event }) => ({ failureReason: String(event.reason || event.error?.message || 'Could not update the device model.') })),
  },
});

export const DEVICE_MODEL_FLOW_BACKEND_CONFIRMED = true;
