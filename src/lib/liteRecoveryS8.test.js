import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { isLiteRecoveryViewLive, selectRecoveryScreenView } from './liteViewModels.js';

const recoverySource = readFileSync(new URL('../lite/LiteRecovery.jsx', import.meta.url), 'utf8');
const detailsSource = readFileSync(new URL('../lite/recovery/RecoveryDatabaseDetailsLazy.jsx', import.meta.url), 'utf8');
const cssSource = readFileSync(new URL('../index.css', import.meta.url), 'utf8');

describe('Pocket Lab Lite Security S8 recovery UI', () => {
  it('keeps the database snapshot compact and sanitized', () => {
    const view = selectRecoveryScreenView({
      database_protection: {
        status: 'healthy',
        rollback_available: true,
        latest_backup: {
          backup_id: 'db-backup-a',
          status: 'verified',
          verification_status: 'verified',
          created_at: '2026-07-17T10:00:00Z',
          size_bytes: 4096,
          raw_path: '/private/database.sqlite3',
          database_sha256: 'not-for-normal-ui',
        },
        maintenance: { active: false, state: 'ready' },
      },
    });

    expect(view.database_protection.latest_backup.verification_status).toBe('verified');
    expect(view.database_protection.rollback_available).toBe(true);
    expect(view.database_protection.latest_backup).not.toHaveProperty('raw_path');
    expect(view.database_protection.latest_backup).not.toHaveProperty('database_sha256');
  });

  it('treats backend-owned database maintenance as live state', () => {
    expect(isLiteRecoveryViewLive({
      database_protection: {
        maintenance: { active: true, state: 'replacing' },
      },
      _snapshot: { source: 'saved' },
    })).toBe(true);
  });

  it('keeps first paint compact and lazy-loads database management', () => {
    expect(recoverySource).toContain("React.lazy(() => import('./recovery/RecoveryDatabaseDetailsLazy.jsx'))");
    expect(recoverySource).toContain('Back Up Pocket Lab');
    expect(recoverySource).toContain('Manage');
    expect(recoverySource).toContain('variant="security"');
    expect(recoverySource).toContain('window.confirm');
    expect(recoverySource).toContain('databaseWriteBlocked');
  });

  it('shows verified, preview, rollback, maintenance, history, and technical states', () => {
    for (const label of [
      'Backup verified',
      'Preview restore',
      'Rollback available',
      'Maintenance in progress',
      'Database backups',
      'Technical details',
    ]) {
      expect(detailsSource).toContain(label);
    }
    expect(detailsSource).not.toMatch(/\/data\/data\/com\.termux|nats:\/\/|restic password|private key/i);
  });

  it('preserves mobile sheet, desktop side-panel, and reduced-motion contracts', () => {
    expect(cssSource).toContain('.lite-recovery-database-manage-sheet');
    expect(cssSource).toContain('@media (max-width: 560px)');
    expect(cssSource).toContain('@media (prefers-reduced-motion: reduce)');
    expect(cssSource).toContain('.lite-security-overlay-surface');
    expect(cssSource).toMatch(/@media \(min-width: 7\d\dpx\)/);
  });
});
