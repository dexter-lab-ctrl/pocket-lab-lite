import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { selectRecoverySummaryView } from './liteViewModels.js';

const recoverySource = readFileSync(new URL('../lite/LiteRecovery.jsx', import.meta.url), 'utf8');
const manageSource = readFileSync(new URL('../lite/recovery/RecoveryManageSheetLazy.jsx', import.meta.url), 'utf8');
const historySource = readFileSync(new URL('../lite/recovery/RecoveryBackupHistory.jsx', import.meta.url), 'utf8');
const virtualListSource = readFileSync(new URL('../lite/components/LiteVirtualList.jsx', import.meta.url), 'utf8');
const confirmSource = readFileSync(new URL('../lite/recovery/RecoveryConfirmSheetLazy.jsx', import.meta.url), 'utf8');
const overlaySource = readFileSync(new URL('../lite/LiteOverlay.jsx', import.meta.url), 'utf8');
const apiSource = readFileSync(new URL('./liteApi.js', import.meta.url), 'utf8');
const snapshotSource = readFileSync(new URL('./liteSafeSnapshots.js', import.meta.url), 'utf8');
const cssSource = readFileSync(new URL('../index.css', import.meta.url), 'utf8');


describe('Pocket Lab Lite Recovery R3/R4', () => {
  it('uses a compact summary for first paint and details only on demand', () => {
    expect(recoverySource).toContain('liteApi.recoverySummary');
    expect(recoverySource).toContain('liteApi.recoveryDetails');
    expect(recoverySource).toContain('enabled: detailsNeeded');
    expect(recoverySource).toContain('selectRecoverySummaryView');
    expect(apiSource).toContain("conditionalGet('/api/lite/recovery/summary')");
    expect(apiSource).toContain("conditionalGet('/api/lite/recovery/details')");
    expect(snapshotSource).toContain("'/api/lite/recovery/summary'");
  });

  it('loads bounded cursor history only when History is mounted', () => {
    expect(manageSource).toContain("activeSection === 'history'");
    expect(historySource).toContain('liteApi.recoveryHistory(10, cursor)');
    expect(historySource).toContain('recoveryHistoryPage');
    expect(historySource).toContain('onLoadMore={loadMore}');
    expect(historySource).toContain('hasMore={hasMore}');
    expect(virtualListSource).toContain("loadMoreLabel = 'Load more'");
    expect(virtualListSource).toContain('{loadMoreLabel}');
    expect(apiSource).toContain('cursor');
  });

  it('adds native confirmation, haptics, focus containment, and roving tabs', () => {
    expect(recoverySource).toContain('RecoveryConfirmSheetLazy');
    expect(recoverySource).toContain("triggerLiteHaptic('confirm')");
    expect(recoverySource).not.toContain('window.confirm');
    expect(confirmSource).toContain('data-recovery-native-confirm="true"');
    expect(overlaySource).toContain('useFocusTrap');
    expect(manageSource).toContain("event.key === 'ArrowRight'");
    expect(manageSource).toContain('aria-controls');
    expect(manageSource).toContain('role="tabpanel"');
  });

  it('preserves mobile safe areas, dynamic viewport, touch, and reduced motion', () => {
    expect(cssSource).toContain('--lite-visual-viewport-height');
    expect(cssSource).toContain('env(safe-area-inset-bottom)');
    expect(cssSource).toContain('-webkit-overflow-scrolling: touch');
    expect(cssSource).toContain('-webkit-tap-highlight-color: transparent');
    expect(cssSource).toContain('@media (prefers-reduced-motion: reduce)');
    expect(cssSource).toContain('.lite-recovery-native-confirm');
  });

  it('keeps compact summary fields sanitized', () => {
    const view = selectRecoverySummaryView({
      view_model: 'recovery-summary-r3-v1',
      status: 'healthy',
      last_backup: {
        backup_id: 'backup-a',
        verification_status: 'verified',
        raw_path: '/private/backup',
        manifest_checksum: 'hidden-from-summary',
      },
      database_protection: {
        status: 'healthy',
        latest_backup: {
          backup_id: 'db-a',
          verification_status: 'verified',
          database_sha256: 'hidden',
        },
      },
      recent_activity: [{ id: 'backup-a', kind: 'backup', summary: 'Backup verified', raw_log: 'hidden' }],
    });

    expect(view.last_backup.backup_id).toBe('backup-a');
    expect(view.last_backup).not.toHaveProperty('raw_path');
    expect(view.database_protection.latest_backup).not.toHaveProperty('database_sha256');
    expect(view.recent_activity[0]).not.toHaveProperty('raw_log');
  });
});
