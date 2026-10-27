import { describe, expect, it } from 'vitest';
import {
  isRecoveryLocationReady,
  recoveryOverviewFacts,
  recoveryPremiumHero,
  recoveryJourneyStatus,
  recoveryPremiumActivity,
  recoveryRestoreImpact,
} from './recoveryPremiumView.js';
import { recoveryHistoryEligibility, recoveryHistoryItems } from './RecoveryBackupHistory.jsx';

// Synthetic fixtures: no backup payloads, filesystem writes, authorization tokens or secrets.
const backup = Object.freeze({ backup_id: 'synthetic-a', created_at: '2026-10-10T10:00:00Z', verification_status: 'verified' });
const preview = Object.freeze({ preview_id: 'synthetic-preview-a', backup_id: backup.backup_id, status: 'ready', change_count: 2, included_components: ['workspace settings'], excluded_components: ['media'] });
const readyLocation = Object.freeze({ location_id: 'approved-a', display_name: 'Protected storage', status: 'ready', ready: true, available: true });
const facts = (options = {}) => recoveryOverviewFacts({
  backup, preview, locations: { selected_location: readyLocation }, ...options,
});
const eligibility = (options = {}) => recoveryHistoryEligibility({
  backup, selectedBackupId: backup.backup_id, preview, ...options,
});

describe('Azure Horizon Recovery semantic overview', () => {
  it('projects precisely latest backup, destination, preview without conflating restore authority', () => {
    const result = facts();
    expect(result.map((item) => item.id)).toEqual(['backup', 'destination', 'preview']);
    expect(result.map((item) => item.label)).toEqual(['Verified', 'Ready', 'Preview ready']);
    expect(recoveryPremiumHero({ backup, preview }).statusLabel).toBe('Verified backup');
  });
  it.each([
    ['empty', null, 'No backup'],
    ['unverified', { ...backup, verification_status: 'pending' }, 'Needs verification'],
    ['verified', backup, 'Verified'],
  ])('%s backup does not invent verification', (_title, value, expected) => {
    expect(facts({ backup: value })[0].label).toBe(expected);
  });
  it.each([
    ['ready', 'Ready'],
    ['available', 'Available'],
    ['low_space', 'Low space'],
    ['read_only', 'Read-only'],
    ['missing', 'Missing'],
    ['unavailable', 'Unavailable'],
    ['unknown', 'Unknown'],
  ])('preserves destination state %s independently', (status, expected) => {
    expect(facts({ locations: { selected_location: { ...readyLocation, status } } })[1].label).toBe(expected);
  });
  it('does not equate available with ready for a protected restore', () => {
    expect(isRecoveryLocationReady({ status: 'available' })).toBe(false);
    expect(isRecoveryLocationReady(readyLocation)).toBe(true);
    expect(recoveryRestoreImpact({ backup, preview, location: { status: 'available' } }).ready).toBe(false);
  });
  it('requires a matching preview identity and a verified backup', () => {
    expect(facts({ preview: { ...preview, backup_id: 'other' } })[2].label).toBe('Different backup');
    expect(facts({ preview: null })[2].label).toBe('Preview required');
    expect(facts({ preview: { ...preview, status: 'expired' } })[2].label).toBe('Preview expired');
    expect(facts({ backup: { ...backup, verification_status: 'pending' } })[2].label).toBe('Preview required');
    expect(facts({ preview: { ...preview, restore_allowed: false } })[2].label).toBe('Preview required');
  });
  it.each([{ saved: true }, { stale: true }, { reachable: false }])('does not present live authority in a saved or unavailable state %o', (state) => {
    expect(facts(state).every((item) => item.label === 'Not confirmed')).toBe(true);
    expect(recoveryPremiumHero({ backup, preview, ...state }).disabled).toBe(true);
  });
  it('does not synthesize preview counts or change inclusion scope', () => {
    const projected = recoveryRestoreImpact({ backup, preview: { ...preview, change_count: undefined } });
    expect(projected.count).toBeNull();
    expect(projected.included).toEqual(['workspace settings']);
    expect(projected.excluded).toEqual(['media']);
  });
  it('keeps educational stages independent from a restore command acceptance', () => {
    expect(recoveryJourneyStatus({ backup, preview, restore: { restore_id: 'r', status: 'accepted' } }).restore).not.toBe('completed');
    expect(recoveryJourneyStatus({ backup, preview, restore: { restore_id: 'r', status: 'running' } }).restore).toBe('in_progress');
    expect(recoveryJourneyStatus({ backup, preview, restore: { restore_id: 'r', status: 'failed' } }).restore).toBe('failed');
    expect(recoveryJourneyStatus({ backup, preview, restore: { restore_id: 'r', status: 'rolled_back' } }).restore).toBe('failed');
  });
  it('keeps rollback outcomes visibly distinct from a committed restore', () => {
    const hero = recoveryPremiumHero({ backup, preview, data: { last_restore: { status: 'rolled_back', summary: 'Rollback completed.' } } });
    expect(hero.state).toBe('failed');
    expect(hero.statusLabel).toBe('Needs attention');
    const activity = recoveryPremiumActivity({ restore: { restore_id: 'r', status: 'rolled_back', summary: 'Rollback completed.' } });
    expect(activity[0].state).toBe('failed');
  });
  it('retains event versus current-record provenance and unknown time', () => {
    const snapshot = recoveryPremiumActivity({ backup })[0];
    expect(snapshot.origin).toBe('snapshot');
    const event = recoveryPremiumActivity({ activity: [{ id: 'i', kind: 'backup', status: 'accepted' }] })[0];
    expect(event.origin).toBe('event');
    expect(event.state).toBe('in_progress');
    expect(event.time).toBe('');
  });
});

describe('Azure Horizon Recovery history eligibility stays per selected backup', () => {
  it('projects preview readiness only onto the matching backup row', () => {
    const other = { ...backup, backup_id: 'synthetic-other' };
    const items = recoveryHistoryItems([backup, other], preview);
    expect(items[0].meta).toContain('Preview ready');
    expect(items[1].meta).not.toContain('Preview ready');
  });
  it('permits only a verified, selected, matching, current restore preview', () => {
    expect(eligibility().canRecover).toBe(true);
    expect(eligibility({ backup: { ...backup, verification_status: 'pending' } }).canRecover).toBe(false);
    expect(eligibility({ selectedBackupId: 'other' }).canRecover).toBe(false);
    expect(eligibility({ preview: { ...preview, backup_id: 'other' } }).canRecover).toBe(false);
    expect(eligibility({ preview: { ...preview, status: 'expired' } }).canRecover).toBe(false);
    expect(eligibility({ preview: { ...preview, restore_allowed: false } }).canRecover).toBe(false);
    expect(eligibility({ saved: true }).canRecover).toBe(false);
  });
  it.each(['missing', 'read_only', 'low_space', 'unavailable'])('blocks unavailable destination %s', (status) => {
    const location = { status };
    expect(eligibility({ backup: { ...backup, location } }).canRecover).toBe(false);
  });
  it('returns a non-color-only prerequisite reason', () => {
    expect(eligibility({ preview: null }).reason).toMatch(/fresh matching restore preview/);
    expect(eligibility({ saved: true }).reason).toMatch(/Live recovery/);
  });
});
