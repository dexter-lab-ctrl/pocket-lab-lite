import { useEffect, useMemo } from 'react';
import { useMachine } from '@xstate/react';
import {
  liteRecoveryFlowLabels,
  liteRecoveryFlowMachine,
  recoveryFlowIsBusy,
  recoveryFlowSteps,
} from '../machines/liteRecoveryFlowMachine.js';
import { writeBlockedReason } from '../machines/liteFlowGuards.js';

export const LITE_RECOVERY_FLOW_USES_FASTAPI_ONLY = true;
export const LITE_RECOVERY_FLOW_QUERY_RECONCILED = true;

const LIVE_STATUSES = new Set(['accepted', 'queued', 'running', 'working', 'in_progress', 'checkpointing', 'validating', 'restarting']);
const FAILED_STATUSES = new Set(['failed', 'failure', 'error', 'blocked', 'rolled_back', 'rollback_failed']);
const DONE_STATUSES = new Set(['succeeded', 'success', 'completed', 'complete', 'done', 'ready', 'verified', 'succeeded_with_warnings']);

function normalizeStatus(value = '') {
  return String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
}

function timestampAtOrAfter(value = '', floor = '') {
  if (!floor) return Boolean(value);
  const timestamp = new Date(value || '').getTime();
  const floorTimestamp = new Date(floor).getTime();
  return Number.isFinite(timestamp) && Number.isFinite(floorTimestamp) && timestamp >= floorTimestamp;
}

function matchingId(actual = '', expected = '') {
  return !expected || String(actual || '') === String(expected || '');
}

function terminalRecoveryPayload({ actionId, context, recovery, latestBackup, latestPreview, lastRestore }) {
  const startedAt = context.actionStartedAt || '';
  const expectedBackupId = context.backupId || '';
  const expectedPreviewId = context.previewId || '';

  if (actionId === 'backup_now') {
    const status = normalizeStatus(latestBackup?.status || latestBackup?.state || latestBackup?.verification_status);
    if (FAILED_STATUSES.has(status) && matchingId(latestBackup?.backup_id, expectedBackupId)) return { failed: true, payload: latestBackup };
    if (matchingId(latestBackup?.backup_id, expectedBackupId)
      && !latestBackup?.pending
      && timestampAtOrAfter(latestBackup?.created_at || latestBackup?.updated_at, startedAt)
      && (DONE_STATUSES.has(status) || Boolean(latestBackup?.backup_id))) {
      return { done: true, payload: latestBackup };
    }
  }

  if (actionId === 'verify_backup') {
    const status = normalizeStatus(latestBackup?.verification_status || latestBackup?.status);
    if (FAILED_STATUSES.has(status) && matchingId(latestBackup?.backup_id, expectedBackupId)) return { failed: true, payload: latestBackup };
    if (matchingId(latestBackup?.backup_id, expectedBackupId)
      && status === 'verified'
      && timestampAtOrAfter(latestBackup?.verified_at || latestBackup?.updated_at, startedAt)) {
      return { done: true, payload: latestBackup };
    }
  }

  if (actionId === 'preview_restore_recovery') {
    const status = normalizeStatus(latestPreview?.status || latestPreview?.state);
    if (FAILED_STATUSES.has(status) && matchingId(latestPreview?.backup_id, expectedBackupId)) return { failed: true, payload: latestPreview };
    if (matchingId(latestPreview?.backup_id, expectedBackupId)
      && (!expectedPreviewId || matchingId(latestPreview?.preview_id, expectedPreviewId))
      && status === 'ready'
      && timestampAtOrAfter(latestPreview?.created_at || latestPreview?.updated_at, startedAt)) {
      return { done: true, payload: latestPreview };
    }
  }

  if (actionId === 'recovery_restore') {
    const status = normalizeStatus(lastRestore?.status || lastRestore?.state || lastRestore?.phase);
    const matches = matchingId(lastRestore?.backup_id, expectedBackupId)
      && matchingId(lastRestore?.preview_id, expectedPreviewId);
    if (matches && FAILED_STATUSES.has(status) && timestampAtOrAfter(lastRestore?.updated_at || lastRestore?.completed_at, startedAt)) {
      return { failed: true, payload: lastRestore };
    }
    if (matches && DONE_STATUSES.has(status) && timestampAtOrAfter(lastRestore?.completed_at || lastRestore?.updated_at, startedAt)) {
      return { done: true, payload: lastRestore };
    }
  }

  const operation = recovery?.current_operation || recovery?.latest_operation || recovery?.operation || {};
  const operationStatus = normalizeStatus(operation?.status || operation?.state || operation?.phase || operation?.progress?.status);
  return LIVE_STATUSES.has(operationStatus) || operation?.live === true
    ? { live: true, payload: operation }
    : null;
}

export function useLiteRecoveryFlow({
  recovery = {},
  latestBackup = null,
  latestPreview = null,
  lastRestore = null,
  backendReachable = true,
  savedStateOnly = false,
} = {}) {
  const [snapshot, send] = useMachine(liteRecoveryFlowMachine);
  const value = String(snapshot.value || 'ready');
  const writeBlocked = savedStateOnly || backendReachable === false;
  const blockedReason = writeBlockedReason({ backendReachable, savedStateOnly });

  useEffect(() => {
    send({
      type: 'BACKEND_STATE',
      backendReachable,
      savedStateOnly,
      backupId: latestBackup?.backup_id,
      previewId: latestPreview?.preview_id,
      status: recovery?.status,
    });
    if (savedStateOnly) send({ type: 'SAVED_STATE_ONLY' });
  }, [backendReachable, latestBackup?.backup_id, latestPreview?.preview_id, recovery?.status, savedStateOnly, send]);

  useEffect(() => {
    const actionId = snapshot.context.activeActionId;
    if (!actionId) return;
    const terminal = terminalRecoveryPayload({
      actionId,
      context: snapshot.context,
      recovery,
      latestBackup,
      latestPreview,
      lastRestore,
    });
    if (!terminal) return;
    if (terminal.failed) {
      send({ type: 'FAILED', error: terminal.payload, reason: terminal.payload?.summary || 'Recovery action needs attention.' });
      return;
    }
    if (terminal.done) {
      send({ type: 'DONE', payload: terminal.payload });
      return;
    }
    if (terminal.live) {
      const phase = normalizeStatus(terminal.payload?.phase || terminal.payload?.progress?.phase);
      if (phase.includes('checkpoint')) send({ type: 'CHECKPOINT_CREATING' });
      else if (phase.includes('validat')) send({ type: 'VALIDATING_HEALTH' });
      else send({ type: 'RUNNING' });
    }
  }, [lastRestore, latestBackup, latestPreview, recovery, send, snapshot.context]);

  const canWrite = () => {
    if (writeBlocked) {
      send({ type: 'SAVED_STATE_ONLY' });
      return { ok: false, reason: blockedReason || 'Reconnect to continue.' };
    }
    return { ok: true };
  };

  return useMemo(() => ({
    value,
    label: liteRecoveryFlowLabels[value] || 'Recovery ready',
    steps: recoveryFlowSteps(value),
    isBusy: recoveryFlowIsBusy(value),
    writeBlocked,
    blockedReason,
    error: snapshot.context.failureReason || '',
    context: snapshot.context,
    requestBackup: () => {
      const check = canWrite();
      if (check.ok) send({ type: 'REQUEST_BACKUP' });
      return check;
    },
    backupAccepted: (payload) => send({ type: 'ACCEPTED', payload }),
    backupDone: (payload) => send({ type: 'DONE', payload }),
    requestVerify: () => {
      const check = canWrite();
      if (check.ok) send({ type: 'REQUEST_VERIFY' });
      return check;
    },
    verifyAccepted: (payload) => send({ type: 'ACCEPTED', payload }),
    verified: (payload) => send({ type: 'DONE', payload }),
    requestPreview: () => {
      const check = canWrite();
      if (check.ok) send({ type: 'REQUEST_PREVIEW' });
      return check;
    },
    previewAccepted: (payload) => send({ type: 'ACCEPTED', payload }),
    previewReady: (payload) => send({ type: 'DONE', payload }),
    requestRestore: ({ verified = false, previewReady = false, explicitBackup = false } = {}) => {
      const check = canWrite();
      if (!check.ok) return check;
      if (!explicitBackup) return { ok: false, reason: 'Choose an explicit backup before restore.' };
      if (!verified) return { ok: false, reason: 'Verify the backup before restore.' };
      if (!previewReady) return { ok: false, reason: 'Preview restore before making changes.' };
      send({ type: 'REQUEST_RESTORE' });
      return { ok: true };
    },
    confirmRestore: () => send({ type: 'CONFIRM_RESTORE' }),
    restoreAccepted: (payload) => send({ type: 'ACCEPTED', payload }),
    complete: (payload) => send({ type: 'DONE', payload }),
    fail: (error) => send({ type: 'FAILED', error, reason: error?.message }),
    cancel: () => send({ type: 'CANCEL' }),
    reset: () => send({ type: 'RESET' }),
  }), [blockedReason, send, snapshot.context, value, writeBlocked]);
}
