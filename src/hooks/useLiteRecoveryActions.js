import { useCallback, useMemo, useRef } from 'react';
import { liteQueryKeys } from '../lib/liteQueryClient.js';
import { triggerLiteHaptic } from '../lib/liteNativeFeedback.js';
import {
  getLiteRecoveryActionInvalidations,
  isAcceptedLiteMutationResponse,
  useLiteMutation,
} from './useLiteMutation.js';

export const LITE_RECOVERY_ACTION_RUNNER_VERSION = 'recovery-actions-v1';
export const LITE_RECOVERY_ACTIONS_DO_NOT_QUEUE_OFFLINE = true;
export const LITE_RECOVERY_ACTIONS_SINGLE_FLIGHT = true;

function normalizeActionId(value = '') {
  return String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_').slice(0, 80);
}

function normalizeAppId(value = '') {
  return String(value || '').trim().toLowerCase().replace(/[^a-z0-9_-]+/g, '').slice(0, 80);
}

function actionError(message, code = 'recovery_action_blocked') {
  const error = new Error(String(message || 'Recovery action could not start.'));
  error.code = code;
  return error;
}

export function useLiteRecoveryActions({
  writeBlocked = false,
  blockedReason = '',
  operationBusy = false,
  operationBusyReason = '',
} = {}) {
  const inFlightRef = useRef('');
  const mutation = useLiteMutation({
    mutationFn: async ({ execute }) => {
      if (typeof execute !== 'function') throw actionError('Recovery action is not configured.', 'recovery_action_missing');
      return execute();
    },
    invalidateForAction: (variables, result) => {
      const keys = getLiteRecoveryActionInvalidations(variables?.actionId, result);
      const appId = normalizeAppId(variables?.appId);
      return appId ? [...keys, liteQueryKeys.appActions(appId)] : keys;
    },
    invalidateOnSuccess: true,
  });

  const runAction = useCallback(async ({
    actionId,
    busyKey = actionId,
    appId = '',
    execute,
    blocked = false,
    blockedMessage = '',
    onAccepted,
    onDone,
    onFailure,
    successHaptic = '',
    failureHaptic = '',
  } = {}) => {
    const normalizedActionId = normalizeActionId(actionId);
    const normalizedBusyKey = String(busyKey || normalizedActionId || 'recovery').slice(0, 120);
    if (!normalizedActionId || typeof execute !== 'function') {
      const error = actionError('Recovery action is not configured.', 'recovery_action_missing');
      onFailure?.(error);
      return { ok: false, error, reason: error.message };
    }
    if (writeBlocked || blocked) {
      const error = actionError(blockedMessage || blockedReason || 'Reconnect to continue.', 'recovery_action_write_blocked');
      if (failureHaptic) triggerLiteHaptic(failureHaptic);
      return { ok: false, error, reason: error.message };
    }
    if (operationBusy) {
      const error = actionError(operationBusyReason || 'Another Recovery action is already running.', 'recovery_operation_in_flight');
      if (failureHaptic) triggerLiteHaptic(failureHaptic);
      return { ok: false, error, reason: error.message };
    }
    if (inFlightRef.current) {
      const error = actionError('Another Recovery action is already running.', 'recovery_action_in_flight');
      if (failureHaptic) triggerLiteHaptic(failureHaptic);
      return { ok: false, error, reason: error.message };
    }

    inFlightRef.current = normalizedBusyKey;
    mutation.reset();
    try {
      const payload = await mutation.run({
        actionId: normalizedActionId,
        busyKey: normalizedBusyKey,
        appId: normalizeAppId(appId),
        execute,
      });
      const accepted = isAcceptedLiteMutationResponse(payload);
      onAccepted?.(payload);
      if (!accepted) onDone?.(payload);
      if (successHaptic) triggerLiteHaptic(successHaptic);
      return { ok: true, payload, accepted };
    } catch (error) {
      onFailure?.(error);
      if (failureHaptic) triggerLiteHaptic(failureHaptic);
      return { ok: false, error, reason: error?.message || 'Recovery action needs attention.' };
    } finally {
      inFlightRef.current = '';
    }
  }, [blockedReason, mutation, operationBusy, operationBusyReason, writeBlocked]);

  return useMemo(() => ({
    runAction,
    busyKey: mutation.isPending
      ? String(mutation.variables?.busyKey || mutation.variables?.actionId || 'recovery')
      : '',
    activeActionId: mutation.isPending ? normalizeActionId(mutation.variables?.actionId) : '',
    isPending: mutation.isPending,
    isSuccess: mutation.isSuccess,
    error: mutation.error || null,
    errorMessage: mutation.error instanceof Error
      ? mutation.error.message
      : mutation.error
        ? 'Recovery action needs attention.'
        : '',
    reset: mutation.reset,
  }), [mutation.error, mutation.isPending, mutation.isSuccess, mutation.reset, mutation.variables, runAction]);
}
