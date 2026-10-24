import { describe, expect, it } from 'vitest';
import { selectPhotoBackupFacts, selectSupplementalActionNotices } from './appsOperationalView.js';

const device = (changes = {}) => ({
  node_label: 'Test phone', ready: true, photo_storage_access: true, destination_ready: true,
  updated_at: '2026-10-20T10:00:00Z', summary: 'Ready to back up photos.', ...changes,
});

describe('Azure Apps backend-truthful photo backup facts — AUTHORED NOT EXECUTED', () => {
  it('does not claim a transfer occurred solely because a device is connected', () => {
    const value = selectPhotoBackupFacts([device()]);
    expect(value.statusLabel).toBe('Ready');
    expect(value.transfer.state).toBe('Not reported');
    expect(value.latestTransfer).toBe('Not reported');
    expect(value.destination.state).toBe('Ready');
  });
  it('does not synthesize destination readiness when evidence is missing', () => {
    const value = selectPhotoBackupFacts([device({ destination_ready: undefined })]);
    expect(value.destination.state).toBe('Not reported');
    expect(value.transfer.state).toBe('Not reported');
  });
  it('distinguishes a recorded zero from an unreported transfer count', () => {
    const value = selectPhotoBackupFacts([device({ latest_backup: { status:'completed', items_transferred:0, completed_at:'2026-10-19T10:00:00Z' } })]);
    expect(value.latestTransfer).toBe('0 items');
    expect(value.transfer.state).toBe('Completed');
  });
  it.each(['queued','planning','waiting','transferring','cancelling'])('marks %s as live but not complete', (status) => {
    const value = selectPhotoBackupFacts([device({ latest_backup:{status,items_transferred:null} })]);
    expect(value.transfer.state).toBe('Running / waiting');
    expect(value.latestTransfer).toBe('Not reported');
  });
  it.each(['failed','partial','partial_storage_limit','interrupted','blocked'])('reports %s as review', (status) => {
    const value = selectPhotoBackupFacts([device({ latest_backup:{status,summary:'Review current device.'} })]);
    expect(value.tone).toBe('review');
    expect(value.transfer.state).toBe('Needs review');
    expect(value.requiresAttention).toBe(true);
  });
  it('makes saved information read-only and never asserts live success', () => {
    const value = selectPhotoBackupFacts([device({latest_backup:{status:'completed'}})], true);
    expect(value.statusLabel).toBe('Saved / offline');
    expect(value.reason).toContain('saved information');
  });
  it('fails transparently for absent or malformed device projection', () => {
    const unknown = selectPhotoBackupFacts(null);
    expect(unknown.statusLabel).toBe('Unavailable');
    expect(unknown.destination.state).toBe('Not reported');
    expect(unknown.reason).toContain('No device');
  });
  it('shows backend-reported source and failure reason without destination URL', () => {
    const value = selectPhotoBackupFacts([device({ ready:false, photo_storage_access:false, destination_ready:false, summary:'Remote access not ready.' })]);
    expect(value.source.state).toBe('Not ready');
    expect(value.reason).toBe('Remote access not ready.');
    expect(value.nextStep).toContain('Devices');
  });
});

describe('supplemental notices — AUTHORED NOT EXECUTED', () => {
  const row = (id, reason, status='not_ready') => ({
    actionId:id, action:{label:id, enabled:false, status, disabled_reason:reason}
  });
  it('deduplicates by canonical action and normalized reason', () => {
    const value = selectSupplementalActionNotices([row('import_photos','No source'),row('import_photos','No source')]);
    expect(value).toHaveLength(1);
  });
  it('excludes active rows to avoid duplicate visible warnings', () => {
    expect(selectSupplementalActionNotices([row('import_photos','No source')],['import_photos'])).toEqual([]);
  });
  it('does not fabricate warnings for ready, completed or enabled actions', () => {
    const value = selectSupplementalActionNotices([
      row('repair_app','Historical reason','completed'),
      {actionId:'backup_app',action:{label:'Back up',enabled:true,reason:'Not ready'}}
    ]);
    expect(value).toEqual([]);
  });
  it('retains backend-derived reason and next step', () => {
    const value = selectSupplementalActionNotices([{actionId:'preview_restore',action:{label:'Preview restore',enabled:false,status:'blocked',disabled_reason:'No verified app backup.',next_step:'Create an app-record backup.'}}]);
    expect(value).toEqual([{id:'preview_restore',label:'Preview restore',status:'Unavailable',reason:'No verified app backup.',next:'Create an app-record backup.'}]);
  });
});
