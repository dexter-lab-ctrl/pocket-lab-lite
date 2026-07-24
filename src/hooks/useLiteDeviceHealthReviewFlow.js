import { useCallback } from 'react';
import { useMachine } from '@xstate/react';
import { liteDeviceHealthReviewMachine } from '../machines/liteDeviceHealthReviewMachine.js';

export function useLiteDeviceHealthReviewFlow({
  nodeId = '',
  healthRevision = '',
  recommendation = 'review_device',
  backendReachable = true,
  savedStateOnly = false,
} = {}) {
  const [snapshot, send] = useMachine(liteDeviceHealthReviewMachine);
  const value = String(snapshot.value || 'idle');
  const blocked = savedStateOnly || backendReachable === false;

  const review = useCallback(() => {
    send({
      type: 'REVIEW',
      nodeId,
      healthRevision,
      recommendation,
      backendReachable,
      savedStateOnly,
    });
  }, [backendReachable, healthRevision, nodeId, recommendation, savedStateOnly, send]);

  const routeTo = useCallback((screenId, navigate) => {
    review();
    if (blocked || !screenId || typeof navigate !== 'function') return false;
    send({ type: 'ROUTE' });
    try {
      navigate(screenId);
      send({ type: 'ROUTED' });
      return true;
    } catch (error) {
      send({ type: 'FAILED', reason: error?.message || 'Health review could not open the requested area.' });
      return false;
    }
  }, [blocked, review, send]);

  const confirmBackend = useCallback((payload = {}) => {
    send({
      type: 'BACKEND_CONFIRMED',
      status: payload.status,
      attentionCount: payload.attention_count,
      healthRevision: payload.health_revision,
      backendReachable,
      savedStateOnly,
    });
  }, [backendReachable, savedStateOnly, send]);

  return {
    state: value,
    context: snapshot.context,
    blocked,
    review,
    routeTo,
    confirmBackend,
    cancel: () => send({ type: 'CANCEL' }),
    reset: () => send({ type: 'RESET' }),
  };
}
