import { assign, createMachine } from 'xstate';
import { acceptedReference, friendlyFlowError, isBackendReachable } from './liteFlowGuards.js';

const TERMINAL_ACTION_STATES = new Set([
  'backupDone',
  'verified',
  'previewReady',
  'complete',
  'failed',
  'blocked',
  'cancelled',
  'savedStateOnly',
  'previewRequired',
  'verificationRequired',
  'explicitBackupRequired',
  'confirmationMissing',
  'restoreBlocked',
]);

const READY_ACTION_TRANSITIONS = {
  REQUEST_BACKUP: { target: 'backupRequested', guard: 'backendReachable', actions: 'setBackupAction' },
  REQUEST_VERIFY: { target: 'verifyRequested', guard: 'backendReachable', actions: 'setVerifyAction' },
  REQUEST_PREVIEW: { target: 'previewRequested', guard: 'backendReachable', actions: 'setPreviewAction' },
  REQUEST_RESTORE: { target: 'restoreConfirmationRequired', guard: 'backendReachable', actions: 'setRestoreAction' },
};

export const liteRecoveryFlowMachine = createMachine({
  id: 'liteRecoveryFlow',
  initial: 'ready',
  context: {
    backendReachable: true,
    savedStateOnly: false,
    backupId: null,
    previewId: null,
    acceptedCommandId: null,
    activeActionId: '',
    actionStartedAt: '',
    lastCompletedActionId: '',
    lastCompletedAt: '',
    failureReason: '',
  },
  on: {
    BACKEND_STATE: { actions: 'setBackendState' },
  },
  states: {
    idle: {
      on: {
        CHECK_READINESS: 'checkingReadiness',
        READY: 'ready',
        SAVED_STATE_ONLY: 'savedStateOnly',
      },
    },
    checkingReadiness: {
      on: {
        READY: 'ready',
        SAVED_STATE_ONLY: 'savedStateOnly',
        BLOCKED: { target: 'blocked', actions: 'setFailure' },
        FAILED: { target: 'failed', actions: 'setFailure' },
      },
    },
    ready: { on: { ...READY_ACTION_TRANSITIONS, SAVED_STATE_ONLY: 'savedStateOnly' } },
    backupRequested: {
      on: {
        ACCEPTED: { target: 'backupQueued', actions: 'setAccepted' },
        FAILED: { target: 'failed', actions: 'setFailure' },
      },
    },
    backupQueued: {
      on: {
        RUNNING: 'backupRunning',
        DONE: { target: 'backupDone', actions: ['setAccepted', 'completeAction'] },
        FAILED: { target: 'failed', actions: 'setFailure' },
      },
    },
    backupRunning: {
      on: {
        DONE: { target: 'backupDone', actions: ['setAccepted', 'completeAction'] },
        FAILED: { target: 'failed', actions: 'setFailure' },
      },
    },
    backupDone: { on: { ...READY_ACTION_TRANSITIONS, RESET: { target: 'ready', actions: 'clearFailure' } } },
    verifyRequested: {
      on: {
        ACCEPTED: { target: 'verifyQueued', actions: 'setAccepted' },
        FAILED: { target: 'failed', actions: 'setFailure' },
      },
    },
    verifyQueued: {
      on: {
        RUNNING: 'verifying',
        DONE: { target: 'verified', actions: ['setAccepted', 'completeAction'] },
        FAILED: { target: 'failed', actions: 'setFailure' },
      },
    },
    verifying: {
      on: {
        DONE: { target: 'verified', actions: ['setAccepted', 'completeAction'] },
        FAILED: { target: 'failed', actions: 'setFailure' },
      },
    },
    verified: { on: { ...READY_ACTION_TRANSITIONS, RESET: { target: 'ready', actions: 'clearFailure' } } },
    previewRequested: {
      on: {
        ACCEPTED: { target: 'previewQueued', actions: 'setAccepted' },
        FAILED: { target: 'failed', actions: 'setFailure' },
      },
    },
    previewQueued: {
      on: {
        RUNNING: 'previewQueued',
        DONE: { target: 'previewReady', actions: ['setAccepted', 'completeAction'] },
        FAILED: { target: 'failed', actions: 'setFailure' },
      },
    },
    previewReady: { on: { ...READY_ACTION_TRANSITIONS, RESET: { target: 'ready', actions: 'clearFailure' } } },
    restoreConfirmationRequired: {
      on: {
        CONFIRM_RESTORE: 'restoreRequested',
        CANCEL: { target: 'cancelled', actions: 'clearFailure' },
        MISSING_CONFIRMATION: 'confirmationMissing',
      },
    },
    restoreRequested: {
      on: {
        ACCEPTED: { target: 'restoreQueued', actions: 'setAccepted' },
        FAILED: { target: 'failed', actions: 'setFailure' },
      },
    },
    restoreQueued: {
      on: {
        CHECKPOINT_CREATING: 'checkpointCreating',
        RUNNING: 'restoring',
        DONE: { target: 'complete', actions: ['setAccepted', 'completeAction'] },
        FAILED: { target: 'failed', actions: 'setFailure' },
      },
    },
    checkpointCreating: {
      on: {
        RUNNING: 'restoring',
        FAILED: { target: 'failed', actions: 'setFailure' },
      },
    },
    restoring: {
      on: {
        VALIDATING_HEALTH: 'validatingHealth',
        DONE: { target: 'complete', actions: ['setAccepted', 'completeAction'] },
        FAILED: { target: 'failed', actions: 'setFailure' },
      },
    },
    validatingHealth: {
      on: {
        DONE: { target: 'complete', actions: ['setAccepted', 'completeAction'] },
        FAILED: { target: 'failed', actions: 'setFailure' },
      },
    },
    complete: { on: { ...READY_ACTION_TRANSITIONS, RESET: { target: 'ready', actions: 'clearFailure' } } },
    previewRequired: { on: { ...READY_ACTION_TRANSITIONS, RESET: { target: 'ready', actions: 'clearFailure' } } },
    verificationRequired: { on: { ...READY_ACTION_TRANSITIONS, RESET: { target: 'ready', actions: 'clearFailure' } } },
    explicitBackupRequired: { on: { ...READY_ACTION_TRANSITIONS, RESET: { target: 'ready', actions: 'clearFailure' } } },
    confirmationMissing: { on: { ...READY_ACTION_TRANSITIONS, RESET: { target: 'ready', actions: 'clearFailure' } } },
    restoreBlocked: { on: { ...READY_ACTION_TRANSITIONS, RESET: { target: 'ready', actions: 'clearFailure' } } },
    savedStateOnly: {
      on: {
        BACKEND_STATE: [
          { target: 'ready', guard: 'backendReachable', actions: 'setBackendState' },
          { actions: 'setBackendState' },
        ],
        RESET: 'idle',
      },
    },
    backendUnreachable: { on: { RESET: 'idle' } },
    blocked: { on: { ...READY_ACTION_TRANSITIONS, RESET: { target: 'ready', actions: 'clearFailure' } } },
    failed: { on: { ...READY_ACTION_TRANSITIONS, RETRY: { target: 'ready', actions: 'clearFailure' }, RESET: { target: 'idle', actions: 'clearFailure' } } },
    cancelled: { on: { ...READY_ACTION_TRANSITIONS, RESET: { target: 'ready', actions: 'clearFailure' } } },
  },
}, {
  guards: {
    backendReachable: ({ context }) => isBackendReachable(context),
  },
  actions: {
    setBackendState: assign(({ context, event }) => ({
      backendReachable: event.backendReachable ?? context.backendReachable,
      savedStateOnly: event.savedStateOnly ?? context.savedStateOnly,
      backupId: context.activeActionId ? context.backupId : event.backupId ?? context.backupId,
      previewId: context.activeActionId ? context.previewId : event.previewId ?? context.previewId,
    })),
    setBackupAction: assign(() => ({ activeActionId: 'backup_now', actionStartedAt: new Date().toISOString(), backupId: null, previewId: null, acceptedCommandId: null, failureReason: '' })),
    setVerifyAction: assign(() => ({ activeActionId: 'verify_backup', actionStartedAt: new Date().toISOString(), acceptedCommandId: null, failureReason: '' })),
    setPreviewAction: assign(() => ({ activeActionId: 'preview_restore_recovery', actionStartedAt: new Date().toISOString(), previewId: null, acceptedCommandId: null, failureReason: '' })),
    setRestoreAction: assign(() => ({ activeActionId: 'recovery_restore', actionStartedAt: new Date().toISOString(), acceptedCommandId: null, failureReason: '' })),
    setAccepted: assign(({ context, event }) => ({
      acceptedCommandId: acceptedReference(event.payload || {}) || context.acceptedCommandId,
      backupId: event.payload?.backup_id || event.backupId || context.backupId,
      previewId: event.payload?.preview_id || event.previewId || context.previewId,
      failureReason: '',
    })),
    completeAction: assign(({ context }) => ({
      lastCompletedActionId: context.activeActionId,
      lastCompletedAt: new Date().toISOString(),
      activeActionId: '',
      actionStartedAt: '',
      failureReason: '',
    })),
    setFailure: assign(({ event }) => ({
      activeActionId: '',
      actionStartedAt: '',
      failureReason: event.reason || friendlyFlowError(event.error, 'Recovery needs attention.'),
    })),
    clearFailure: assign(() => ({
      activeActionId: '',
      actionStartedAt: '',
      acceptedCommandId: null,
      failureReason: '',
    })),
  },
});

export const liteRecoveryFlowLabels = {
  idle: 'Recovery ready',
  checkingReadiness: 'Checking readiness…',
  ready: 'Recovery ready',
  backupRequested: 'Getting ready',
  backupQueued: 'Backup queued',
  backupRunning: 'Working',
  backupDone: 'Backup saved',
  verifyRequested: 'Getting ready',
  verifyQueued: 'Verification queued',
  verifying: 'Checking',
  verified: 'Backup verified',
  previewRequested: 'Getting ready',
  previewQueued: 'Preview queued',
  previewReady: 'Preview ready',
  restoreConfirmationRequired: 'Confirmation required',
  restoreRequested: 'Getting ready',
  restoreQueued: 'Restore queued',
  checkpointCreating: 'Safe restore point',
  restoring: 'Working',
  validatingHealth: 'Health passed',
  complete: 'Done',
  savedStateOnly: 'Restore cannot continue from saved state only',
  previewRequired: 'Preview required',
  verificationRequired: 'Verification required',
  explicitBackupRequired: 'Choose a backup first',
  confirmationMissing: 'Confirmation required before restore',
  restoreBlocked: 'Restore blocked',
  blocked: 'Needs attention',
  failed: 'Needs attention',
  cancelled: 'Cancelled',
};

export function recoveryFlowIsBusy(value = '') {
  return !TERMINAL_ACTION_STATES.has(String(value || 'ready')) && !['idle', 'ready', 'checkingReadiness'].includes(String(value || 'ready'));
}

export function recoveryFlowSteps(value) {
  const v = String(value || 'idle');
  return [
    {
      id: 'backup',
      label: 'Backup saved',
      state: v.includes('backup') && v !== 'backupDone'
        ? 'active'
        : ['backupDone', 'verifyRequested', 'verifyQueued', 'verifying', 'verified', 'previewRequested', 'previewQueued', 'previewReady', 'restoreConfirmationRequired', 'restoreRequested', 'restoreQueued', 'checkpointCreating', 'restoring', 'validatingHealth', 'complete'].includes(v)
          ? 'done'
          : 'waiting',
    },
    {
      id: 'verify',
      label: 'Backup verified',
      state: ['verifyRequested', 'verifyQueued', 'verifying'].includes(v)
        ? 'active'
        : ['verified', 'previewRequested', 'previewQueued', 'previewReady', 'restoreConfirmationRequired', 'restoreRequested', 'restoreQueued', 'checkpointCreating', 'restoring', 'validatingHealth', 'complete'].includes(v)
          ? 'done'
          : 'waiting',
    },
    {
      id: 'preview',
      label: 'Preview ready',
      state: ['previewRequested', 'previewQueued'].includes(v)
        ? 'active'
        : ['previewReady', 'restoreConfirmationRequired', 'restoreRequested', 'restoreQueued', 'checkpointCreating', 'restoring', 'validatingHealth', 'complete'].includes(v)
          ? 'done'
          : 'waiting',
    },
    {
      id: 'restore',
      label: 'Restore protected',
      state: ['restoreConfirmationRequired', 'restoreRequested', 'restoreQueued', 'checkpointCreating', 'restoring', 'validatingHealth'].includes(v)
        ? 'active'
        : v === 'complete'
          ? 'done'
          : ['blocked', 'failed', 'restoreBlocked'].includes(v)
            ? 'failed'
            : 'waiting',
    },
  ];
}
