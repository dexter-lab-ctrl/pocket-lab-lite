// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import RecoveryJourney from './RecoveryJourney.jsx';
import RecoveryPremiumTimeline from './RecoveryPremiumTimeline.jsx';
import RecoveryBackupLocation from './RecoveryBackupLocation.jsx';
import RecoveryDatabaseDetailsLazy from './RecoveryDatabaseDetailsLazy.jsx';
import RecoveryConfirmSheetLazy from './RecoveryConfirmSheetLazy.jsx';

afterEach(() => cleanup());
const backup = { backup_id: 'synthetic-recovery-backup', created_at: '2026-10-10T10:00:00Z', verification_status: 'verified' };
const preview = { preview_id: 'synthetic-preview', backup_id: backup.backup_id, status: 'ready', restore_allowed: true, included_components: ['Lite settings'], excluded_components: ['photos'] };
const selected = { location_id: 'approved', display_name: 'Protected local storage', status: 'ready', repository_present: true };

describe('Azure Horizon Recovery accessible compositions', () => {
  it('renders all four instructional stages and allows keyboard activation without dispatching actions', () => {
    render(<RecoveryJourney stages={{ backup: 'completed', verify: 'completed', preview: 'needs_action', restore: 'blocked' }} />);
    expect(screen.getAllByRole('button')).toHaveLength(4);
    const button = screen.getByRole('button', { name: /Preview Needs action/i });
    button.focus();
    fireEvent.click(button);
    expect(button.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByText(/A preview never applies/)).toBeTruthy();
  });
  it('marks saved activity as unconfirmed instead of fabricating an event', () => {
    render(<RecoveryPremiumTimeline items={[]} saved onViewActivity={vi.fn()} />);
    expect(screen.getByText(/cannot be confirmed/i)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'View Activity' })).toBeTruthy();
  });
  it('distinguishes available and ready destination and preserves approved location actions', () => {
    const onSelect = vi.fn();
    render(<RecoveryBackupLocation locations={{
      selected_location: { ...selected, status: 'available' },
      locations: [{ ...selected }, { location_id: 'approved-b', display_name: 'Second approved storage', status: 'available' }],
    }} onSelect={onSelect} />);
    expect(screen.getByText('Available')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Change backup location' }));
    fireEvent.click(screen.getByRole('button', { name: /Second approved storage/i }));
    expect(onSelect).toHaveBeenCalledWith('approved-b');
  });
  it('shows explicit protected confirmation, preview linkage and cancel', () => {
    const cancel = vi.fn();
    const confirm = vi.fn();
    render(<RecoveryConfirmSheetLazy backup={backup} preview={preview} onCancel={cancel} onConfirm={confirm} />);
    expect(screen.getByText(/Confirmed for this backup/i)).toBeTruthy();
    expect(screen.getByText(/Lite settings/i)).toBeTruthy();
    expect(within(screen.getByRole('region', { name: 'Restore scope' })).getByText('photos')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(cancel).toHaveBeenCalledOnce();
    expect(confirm).not.toHaveBeenCalled();
  });
  it('does not enable restore for a mismatched or expired preview', () => {
    render(<RecoveryConfirmSheetLazy backup={backup} preview={{ ...preview, backup_id: 'different' }} onCancel={vi.fn()} onConfirm={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Restore Backup' }).disabled).toBe(true);
    expect(screen.getByRole('alert')).toHaveTextContent(/matching preview/);
  });
  it('only renders recorded database phases and never labels rollback as successful restore', () => {
    render(<RecoveryDatabaseDetailsLazy databaseProtection={{
      summary: 'Database backup recorded',
      backup_history: [],
    }} latestBackup={backup} lastRestore={{
      phase: 'rolled_back',
      stage_history: ['checkpointing', 'checkpoint_ready', 'rollback_started', 'rolled_back'],
    }} />);
    expect(within(screen.getByRole('region', { name: 'Database recovery progress' })).getByText(/Rolled back — restore not committed/i)).toBeTruthy();
    expect(screen.queryByText('Restore committed')).toBeNull();
    expect(screen.getByRole('region', { name: 'Database recovery progress' })).toBeTruthy();
  });
  it('requires a matching database preview and refuses a restore without it', () => {
    render(<RecoveryDatabaseDetailsLazy latestBackup={backup} latestPreview={{ ...preview, backup_id: 'different' }} />);
    expect(screen.getByRole('button', { name: 'Restore Pocket Lab' }).disabled).toBe(true);
  });
});
