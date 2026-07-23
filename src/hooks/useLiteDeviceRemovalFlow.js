import { useEffect } from 'react';
import { useMachine } from '@xstate/react';
import { liteDeviceRemovalMachine } from '../machines/liteDeviceRemovalMachine.js';

export function useLiteDeviceRemovalFlow({ backendReachable = true, savedStateOnly = false } = {}) {
  const [snapshot, send] = useMachine(liteDeviceRemovalMachine);
  useEffect(() => {
    send({ type: 'BACKEND_STATE', backendReachable, savedStateOnly });
  }, [backendReachable, savedStateOnly, send]);
  const value = String(snapshot.value || 'idle');
  return {
    state: value,
    context: snapshot.context,
    isOpen: !['idle', 'succeeded'].includes(value),
    isLoading: value === 'loadingAssessment',
    isBlocked: value === 'blocked',
    isReviewing: value === 'reviewing',
    isConfirming: value === 'confirming',
    isSubmitting: ['submitting', 'accepted', 'verifying'].includes(value),
    isOffline: value === 'offline',
    review: (deviceId) => send({ type: 'REVIEW', deviceId }),
    assessmentReady: (assessment) => send({ type: 'ASSESSMENT_READY', assessment }),
    confirm: () => send({ type: 'CONFIRM' }),
    submit: () => send({ type: 'SUBMIT' }),
    accepted: () => send({ type: 'ACCEPTED' }),
    verify: () => send({ type: 'VERIFY' }),
    refresh: () => send({ type: 'REFRESH' }),
    complete: () => send({ type: 'COMPLETE' }),
    stale: (reason) => send({ type: 'STALE', reason }),
    fail: (error) => send({ type: 'FAILED', error, reason: error?.message }),
    cancel: () => send({ type: 'CANCEL' }),
    reset: () => send({ type: 'RESET' }),
  };
}
