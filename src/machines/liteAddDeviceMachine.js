import { assign, createMachine } from 'xstate';
import { acceptedReference, friendlyFlowError, isBackendReachable } from './liteFlowGuards.js';

export const liteAddDeviceMachine = createMachine({
  id: 'liteAddDeviceFlow',
  initial: 'idle',
  context: { deviceName: '', role: 'compute', backendReachable: true, savedStateOnly: false, inviteId: null, acceptedCommandId: null, failureReason: '' },
  states: {
    idle: { on: { ENTER_DEVICE: { target: 'enteringDevice', actions: 'setInput' }, BACKEND_UNREACHABLE: { target: 'backendUnreachable', actions: 'setFailure' } } },
    enteringDevice: { on: { CHANGE: { actions: 'setInput' }, VALIDATE_NAME: { target: 'validatingName', actions: 'setInput' }, CANCEL: 'idle' } },
    validatingName: { on: { NAME_VALID: 'checkingDuplicates', NAME_INVALID: { target: 'blocked', actions: 'setFailure' }, BACKEND_UNREACHABLE: { target: 'backendUnreachable', actions: 'setFailure' } } },
    checkingDuplicates: { on: { DUPLICATE_FOUND: { target: 'blocked', actions: 'setFailure' }, PROTECTED_HOST: { target: 'blocked', actions: 'setFailure' }, SUBMIT: { target: 'creatingInvite', guard: 'backendReachable' }, BACKEND_UNREACHABLE: { target: 'backendUnreachable', actions: 'setFailure' } } },
    creatingInvite: { on: { INVITE_READY: { target: 'inviteReady', actions: 'setInvite' }, QUEUED: { target: 'waitingForDevice', actions: 'setInvite' }, BLOCKED: { target: 'blocked', actions: 'setFailure' }, FAILED: { target: 'failed', actions: 'setFailure' } } },
    inviteReady: { on: { WAIT_FOR_DEVICE: 'waitingForDevice', DEVICE_JOINED: 'joined', DEVICE_ONLINE: 'online', BLOCKED: { target: 'blocked', actions: 'setFailure' }, FAILED: { target: 'failed', actions: 'setFailure' }, RESET: 'idle' } },
    waitingForDevice: { on: { DEVICE_JOINED: 'joined', DEVICE_ONLINE: 'online', IDENTITY_MISMATCH: { target: 'blocked', actions: 'setFailure' }, INVITE_EXPIRED: { target: 'blocked', actions: 'setFailure' }, FAILED: { target: 'failed', actions: 'setFailure' }, RESET: 'idle' } },
    joined: { on: { DEVICE_ONLINE: 'online', RESET: 'idle' } },
    online: { on: { RESET: 'idle' } },
    backendUnreachable: { on: { RESET: 'idle', ENTER_DEVICE: { target: 'enteringDevice', actions: 'setInput' } } },
    blocked: { on: { CHANGE: { target: 'enteringDevice', actions: 'setInput' }, RESET: 'idle' } },
    failed: { on: { RETRY: 'checkingDuplicates', RESET: 'idle' } },
  },
}, {
  guards: { backendReachable: ({ context }) => isBackendReachable(context) },
  actions: {
    setInput: assign(({ context, event }) => ({ deviceName: event.deviceName ?? context.deviceName, role: event.role ?? context.role, backendReachable: event.backendReachable ?? context.backendReachable, savedStateOnly: event.savedStateOnly ?? context.savedStateOnly, failureReason: '' })),
    setInvite: assign(({ context, event }) => ({ inviteId: event.invite?.invite_id || event.invite?.id || context.inviteId, acceptedCommandId: acceptedReference(event.payload || event.invite || {}) || context.acceptedCommandId, failureReason: '' })),
    setFailure: assign(({ event }) => ({ failureReason: event.reason || friendlyFlowError(event.error) })),
  },
});

export const liteAddDeviceStateLabels = { idle: 'Add Device', enteringDevice: 'Add Device', validatingName: 'Checking device name…', checkingDuplicates: 'Checking device name…', creatingInvite: 'Creating invite…', inviteReady: 'Connect this device', waitingForDevice: 'Waiting for device…', joined: 'Device connected', online: 'Online', backendUnreachable: 'Reconnect to continue', blocked: 'Needs attention', failed: 'Needs attention' };
export function addDeviceFlowSteps(value) { const v = String(value || 'idle'); return [{ id: 'validate', label: 'Checking device name…', state: ['validatingName','checkingDuplicates'].includes(v) ? 'active' : ['creatingInvite','inviteReady','waitingForDevice','joined','online'].includes(v) ? 'done' : v === 'blocked' ? 'failed' : 'waiting' }, { id: 'invite', label: 'Creating invite…', state: v === 'creatingInvite' ? 'active' : ['inviteReady','waitingForDevice','joined','online'].includes(v) ? 'done' : v === 'failed' ? 'failed' : 'waiting' }, { id: 'connect', label: 'Connect this device', state: v === 'inviteReady' ? 'active' : ['waitingForDevice','joined','online'].includes(v) ? 'done' : 'waiting' }, { id: 'online', label: 'Device connected', state: v === 'waitingForDevice' ? 'active' : ['joined','online'].includes(v) ? 'done' : 'waiting' }]; }
