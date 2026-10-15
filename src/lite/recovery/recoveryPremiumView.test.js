import { describe, expect, it } from 'vitest';
import { recoveryPremiumHero, recoveryJourneyStatus, recoveryPremiumActivity, recoveryRestoreImpact } from './recoveryPremiumView.js';

const verified = { backup_id: 'backup-a', created_at: '2026-10-10T10:00:00Z', verification_status: 'verified' };
const preview = { preview_id: 'preview-a', backup_id: 'backup-a', status: 'ready', change_count: 0, included_components: ['settings'] };

describe('Recovery premium presentation is backend-truthful', () => {
  it('does not confuse saved, verified and restore-ready', () => {
    expect(recoveryPremiumHero({ backup: { backup_id:'backup-a' } }).backup.label).toBe('Verification needed');
    expect(recoveryPremiumHero({ backup: verified }).restore.label).toBe('Preview required');
    const hero = recoveryPremiumHero({ backup: verified, preview });
    expect(hero.verified).toBe(true);
    expect(hero.previewReady).toBe(true);
    expect(hero.restore.label).toBe('Preview ready');
  });
  it('fails closed for unavailable, stale, unknown and database guard states', () => {
    const saved = recoveryPremiumHero({ backup: verified, preview, saved: true });
    expect(saved.restore.label).toBe('Not confirmed');
    expect(saved.disabled).toBe(true);
    expect(recoveryPremiumHero({ stale: true, backup: verified }).state).toBe('unknown');
    expect(recoveryPremiumHero({ reachable: false, backup: verified }).disabled).toBe(true);
    expect(recoveryPremiumHero({ database: { restore_guard: { unresolved: true } } }).state).toBe('blocked');
    expect(recoveryPremiumHero({ repository: { ready: false } }).state).toBe('blocked');
    expect(recoveryPremiumHero({ database: { latest_backup: { backup_id:'db-a' } } }).safety.label).toBe('Database backed up');
  });
  it('keeps educational stage selection separate from backend states', () => {
    const statuses = recoveryJourneyStatus({ backup: verified, preview });
    expect(statuses).toMatchObject({ backup:'completed', verify:'completed', preview:'completed', restore:'available' });
    expect(recoveryJourneyStatus({ backup:verified, preview: { ...preview, backup_id:'other' } }).preview).toBe('needs_action');
    expect(recoveryJourneyStatus({ backup:verified, preview, saved:true }).restore).toBe('unknown');
    expect(recoveryJourneyStatus({ restore: { restore_id:'r-a', status:'accepted' } }).restore).not.toBe('completed');
    expect(recoveryJourneyStatus({ restore: { restore_id:'r-a', status:'failed' } }).restore).toBe('failed');
    expect(recoveryJourneyStatus({ backup:verified, busy:'verify' }).verify).toBe('in_progress');
  });
  it('uses event facts only, deduplicates stable IDs and keeps absent timestamps unknown', () => {
    const activity = recoveryPremiumActivity({ activity:[
      { id:'1', kind:'backup', status:'completed', summary:'Saved', occurred_at:'2026-10-08T10:00:00Z' },
      { id:'1', kind:'backup', status:'completed', summary:'duplicate', occurred_at:'2026-10-08T10:00:00Z' },
      { id:'2', kind:'restore', status:'failed', summary:'Unsuccessful' },
      { id:'3', kind:'preview', status:'pending', summary:'Checking', occurred_at:'2026-10-09T10:00:00Z' },
      { id:'4', kind:'arbitrary', summary:'Not a supported event' },
    ]});
    expect(activity).toHaveLength(3);
    expect(activity[0].id).toBe('preview:3');
    expect(activity.find(x=>x.id==='restore:2').time).toBe('');
    expect(activity.find(x=>x.id==='restore:2').state).toBe('failed');
    expect(activity.every(x=>x.origin==='event')).toBe(true);
  });
  it('marks backup fallback as a current snapshot, not a manufactured event', () => {
    const list = recoveryPremiumActivity({ backup:verified });
    expect(list).toHaveLength(1);
    expect(list[0].origin).toBe('snapshot');
    expect(recoveryPremiumActivity({ backup:verified, unavailable:true })).toEqual([]);
  });
  it('does not turn an absent preview change count into zero', () => {
    expect(recoveryRestoreImpact({backup: verified,preview:{...preview,change_count: undefined}}).count).toBeNull();
    expect(recoveryRestoreImpact({backup: verified,preview}).count).toBe(0);
    expect(recoveryRestoreImpact({backup: verified,preview:{...preview,backup_id:'wrong'}}).ready).toBe(false);
    expect(recoveryRestoreImpact({backup: verified,preview,location:{available:false}}).ready).toBe(false);
  });
});