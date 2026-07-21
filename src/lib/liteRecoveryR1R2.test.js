import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const recoverySource = readFileSync(new URL('../lite/LiteRecovery.jsx', import.meta.url), 'utf8');
const manageSource = readFileSync(new URL('../lite/recovery/RecoveryManageSheetLazy.jsx', import.meta.url), 'utf8');
const detailsSource = readFileSync(new URL('../lite/recovery/RecoveryActionDetailsLazy.jsx', import.meta.url), 'utf8');
const cssSource = readFileSync(new URL('../index.css', import.meta.url), 'utf8');

describe('Pocket Lab Lite Recovery R1/R2 UI', () => {
  it('keeps the default Recovery screen summary-first', () => {
    expect(recoverySource).toContain('data-recovery-r1-summary="true"');
    expect(recoverySource).toContain('Back Up Now');
    expect(recoverySource).toContain('Manage Recovery');
    expect(recoverySource).toContain('Protection');
    expect(recoverySource).toContain('Recent activity');
    expect(recoverySource).not.toContain('lite-recovery-flip-shell');
    expect(recoverySource).not.toContain('<RecoveryBackupHistory');
  });

  it('uses one shared Manage shell with focused sections', () => {
    expect(recoverySource).toContain("React.lazy(() => import('./recovery/RecoveryManageSheetLazy.jsx'))");
    expect(recoverySource).toContain('variant="manage"');
    for (const label of ['Backup', 'Restore', 'Protection', 'History']) {
      expect(manageSource).toContain(`label: '${label}'`);
    }
    expect(manageSource).toContain('lite-recovery-manage-action-row');
    expect(manageSource).toContain('RecoveryBackupHistory');
  });

  it('keeps details progressive and backend-owned', () => {
    expect(recoverySource).toContain('RecoveryActionDetailsLazy');
    expect(recoverySource).toContain('RecoveryDatabaseDetailsLazy');
    expect(recoverySource).toContain('window.confirm');
    expect(detailsSource).toContain('The browser did not run recovery commands.');
    expect(detailsSource).toContain('lite-recovery-action-details-shell');
  });

  it('preserves mobile, safe-area, touch, and reduced-motion behavior', () => {
    expect(cssSource).toContain('.lite-recovery-manage-sheet');
    expect(cssSource).toContain('.lite-recovery-manage-tabs');
    expect(cssSource).toContain('touch-action: manipulation');
    expect(cssSource).toContain('@media (max-width: 560px)');
    expect(cssSource).toContain('@media (prefers-reduced-motion: reduce)');
    expect(cssSource).toContain('env(safe-area-inset-bottom');
  });
});
