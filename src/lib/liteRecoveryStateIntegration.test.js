import { afterEach, describe, expect, it } from 'vitest';
import { createActor } from 'xstate';
import fs from 'node:fs';
import { liteRecoveryFlowMachine } from '../machines/liteRecoveryFlowMachine.js';
import { useLiteUiStore } from '../stores/liteUiStore.js';
import {
  getLiteRecoveryMutationInvalidations,
  selectRecoveryHistorySnapshotView,
} from './liteViewModels.js';
import { normalizeLiteSnapshotPath } from './liteSafeSnapshots.js';

const recoverySource = fs.readFileSync('src/lite/LiteRecovery.jsx', 'utf8');
const actionsSource = fs.readFileSync('src/hooks/useLiteRecoveryActions.js', 'utf8');
const historySource = fs.readFileSync('src/lite/recovery/RecoveryBackupHistory.jsx', 'utf8');
const offlineSource = fs.readFileSync('src/lib/liteOfflineDb.js', 'utf8');

function hasKey(keys, wanted) {
  return keys.some((key) => JSON.stringify(key) === JSON.stringify(wanted));
}

afterEach(() => {
  useLiteUiStore.getState().resetRecoveryUi();
});

describe('Recovery state integration hardening', () => {
  it('uses one guarded TanStack mutation runner and focused invalidation', () => {
    expect(recoverySource).toContain('useLiteRecoveryActions');
    expect(actionsSource).toContain('useLiteMutation');
    expect(actionsSource).toContain('getLiteRecoveryActionInvalidations');
    expect(actionsSource).toContain('invalidateOnSuccess: true');
    expect(actionsSource).toContain('LITE_RECOVERY_ACTIONS_SINGLE_FLIGHT');
    expect(actionsSource).toContain('operationBusy');
    expect(recoverySource).not.toContain('setBackupResult');
    expect(recoverySource).not.toContain('setVerifyResult');
    expect(recoverySource).not.toContain('refreshRecovery');

    const previewKeys = getLiteRecoveryMutationInvalidations('preview_restore_recovery');
    expect(hasKey(previewKeys, ['lite', 'recovery', 'summary'])).toBe(true);
    expect(hasKey(previewKeys, ['lite', 'recovery', 'details'])).toBe(true);
    expect(hasKey(previewKeys, ['lite', 'recovery', 'history'])).toBe(false);

    for (const action of ['backup_now', 'verify_backup', 'recovery_restore', 'database_backup']) {
      expect(hasKey(getLiteRecoveryMutationInvalidations(action), ['lite', 'recovery', 'history'])).toBe(true);
    }
  });

  it('keeps only normalized Recovery shell state in Zustand', () => {
    const store = useLiteUiStore.getState();
    store.setRecoveryManageOpen(true);
    store.setActiveRecoveryManageSection('not-a-section');
    store.setActiveRecoveryDetailsPanel('not-a-panel');
    store.setRecoveryRestoreConfirmation('not-a-confirmation');

    let state = useLiteUiStore.getState();
    expect(state.recoveryManageOpen).toBe(true);
    expect(state.activeRecoveryManageSection).toBe('backup');
    expect(state.activeRecoveryDetailsPanel).toBeNull();
    expect(state.recoveryRestoreConfirmation).toBeNull();
    expect(state).not.toHaveProperty('recoveryPayload');
    expect(state).not.toHaveProperty('backupResult');

    state.setActiveRecoveryDetailsPanel('verify');
    state.setRecoveryEvidenceOpen(true);
    state.setRecoveryRestoreConfirmation('lite');
    state.setRecoveryManageOpen(false);
    state = useLiteUiStore.getState();
    expect(state.activeRecoveryDetailsPanel).toBeNull();
    expect(state.recoveryEvidenceOpen).toBe(false);
    expect(state.recoveryRestoreConfirmation).toBeNull();
  });

  it('persists only a sanitized bounded first history page', () => {
    const payload = {
      backups: Array.from({ length: 14 }, (_, index) => ({
        backup_id: `backup-${index}`,
        snapshot_id: `snapshot-${index}`,
        created_at: `2026-07-2${index % 10}T10:00:00Z`,
        verification_status: 'verified',
        size_bytes: 1024 + index,
        manifest_checksum: 'must-not-persist',
        receipt_id: 'must-not-persist',
        raw_log: 'must-not-persist',
      })),
      next_cursor: 'private-next-page',
      has_more: true,
    };
    const snapshot = selectRecoveryHistorySnapshotView(payload);

    expect(snapshot.backups).toHaveLength(10);
    expect(snapshot.has_more).toBe(false);
    expect(snapshot.next_cursor).toBe('');
    expect(snapshot.offline_first_page_only).toBe(true);
    expect(snapshot.backups[0]).not.toHaveProperty('manifest_checksum');
    expect(snapshot.backups[0]).not.toHaveProperty('receipt_id');
    expect(snapshot.backups[0]).not.toHaveProperty('raw_log');
    expect(normalizeLiteSnapshotPath('/api/lite/recovery/backups?limit=10')).toBe('/api/lite/recovery/backups/index');
    expect(normalizeLiteSnapshotPath('/api/lite/recovery/backups?limit=10&cursor=abc')).toBe('/api/lite/recovery/backups');
    expect(historySource).toContain('cursor ? undefined : selectRecoveryHistorySnapshotView');
    expect(historySource).toContain('!query.savedStateOnly');
    expect(offlineSource).toContain('maxHistorySnapshotBytes: 32 * 1024');
    expect(offlineSource).toContain('pruneRecoveryHistorySnapshots');
  });

  it('keeps accepted work queued until query state confirms completion', () => {
    const actor = createActor(liteRecoveryFlowMachine).start();
    actor.send({ type: 'REQUEST_BACKUP' });
    expect(actor.getSnapshot().value).toBe('backupRequested');
    expect(actor.getSnapshot().context.backupId).toBeNull();

    actor.send({ type: 'ACCEPTED', payload: { status: 'accepted', command_id: 'command-a' } });
    expect(actor.getSnapshot().value).toBe('backupQueued');
    expect(actor.getSnapshot().context.activeActionId).toBe('backup_now');

    actor.send({ type: 'REQUEST_VERIFY' });
    expect(actor.getSnapshot().value).toBe('backupQueued');

    actor.send({ type: 'DONE', payload: { backup_id: 'backup-new', status: 'verified' } });
    expect(actor.getSnapshot().value).toBe('backupDone');
    expect(actor.getSnapshot().context.activeActionId).toBe('');
    expect(actor.getSnapshot().context.lastCompletedActionId).toBe('backup_now');

    actor.send({ type: 'REQUEST_BACKUP' });
    expect(actor.getSnapshot().value).toBe('backupRequested');
    actor.stop();
  });
});
