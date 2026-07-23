import { useEffect, useMemo } from 'react';
import { useMachine } from '@xstate/react';
import { liteDeviceModelMachine } from '../machines/liteDeviceModelMachine.js';

export function useLiteDeviceModelFlow({ open = false, deviceId = '', current = '', backendReachable = true, savedStateOnly = false } = {}) {
  const [snapshot, send] = useMachine(liteDeviceModelMachine);
  useEffect(() => {
    if (open && String(snapshot.value) === 'idle') send({ type: 'OPEN', deviceId, current });
    if (!open && String(snapshot.value) !== 'idle') send({ type: 'CANCEL' });
  }, [current, deviceId, open, send, snapshot.value]);
  const writeBlocked = backendReachable === false || savedStateOnly;
  return useMemo(() => ({
    state: String(snapshot.value || 'idle'),
    candidate: snapshot.context.candidate,
    confirmed: snapshot.context.confirmed,
    failureReason: snapshot.context.failureReason,
    writeBlocked,
    change: (value) => send({ type: 'CHANGE', value }),
    review: (value) => writeBlocked ? send({ type: 'BACKEND_UNREACHABLE', reason: 'Reconnect to change this device model.' }) : send({ type: 'REVIEW', value }),
    clear: () => writeBlocked ? send({ type: 'BACKEND_UNREACHABLE', reason: 'Reconnect to change this device model.' }) : send({ type: 'CLEAR' }),
    confirm: () => send({ type: 'CONFIRM' }),
    edit: () => send({ type: 'EDIT' }),
    succeeded: (value) => send({ type: 'SUCCEEDED', value }),
    failed: (error) => send({ type: 'FAILED', error }),
    retry: () => send({ type: 'RETRY' }),
  }), [send, snapshot.context, snapshot.value, writeBlocked]);
}
