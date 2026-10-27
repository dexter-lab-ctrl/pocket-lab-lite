// @vitest-environment jsdom
import React from 'react';
import {describe,expect,it,vi,afterEach} from 'vitest';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import RecoveryConfirmSheetLazy from './RecoveryConfirmSheetLazy.jsx';
afterEach(()=>cleanup());
const backup={backup_id:'backup-a',created_at:'2026-10-10T10:00:00Z',verification_status:'verified'};
const preview={preview_id:'preview-a',backup_id:'backup-a',status:'ready',included_components:['settings'],excluded_components:['media']};
const location={location_id:'approved-a',status:'ready',ready:true,available:true,display_name:'Protected storage'};
describe('protected restore impact confirmation',()=>{
  it('does not synthesize a zero impact count',()=>{
    render(<RecoveryConfirmSheetLazy backup={backup} preview={preview} location={location} onCancel={()=>{}} onConfirm={()=>{}} />);
    expect(screen.getByText('Impact not reported')).toBeTruthy();
    expect(screen.getByText(/excluded and unchanged/i)).toBeTruthy();
    expect(screen.getByRole('button',{name:'Restore Backup'})).toBeTruthy();
  });
  it('requires a deliberate click and respects busy double-submit protection',()=>{
    const confirm=vi.fn();
    const {rerender}=render(<RecoveryConfirmSheetLazy backup={backup} preview={preview} location={location} onCancel={()=>{}} onConfirm={confirm} busy />);
    expect(screen.getByRole('button',{name:'Restoring…'}).disabled).toBe(true);
    expect(confirm).not.toHaveBeenCalled();
    rerender(<RecoveryConfirmSheetLazy backup={backup} preview={preview} location={location} onCancel={()=>{}} onConfirm={confirm} />);
    fireEvent.click(screen.getByRole('button',{name:'Restore Backup'}));
    expect(confirm).toHaveBeenCalledTimes(1);
  });
  it.each([null, {status:'available'}, {status:'unknown'}, {status:'missing'}])(
    'blocks workspace restore with unconfirmed location %#', (candidate) => {
      const confirm=vi.fn();
      render(<RecoveryConfirmSheetLazy backup={backup} preview={preview} location={candidate} onCancel={()=>{}} onConfirm={confirm} />);
      expect(screen.getByRole('button',{name:'Restore Backup'}).disabled).toBe(true);
      fireEvent.click(screen.getByRole('button',{name:'Restore Backup'}));
      expect(confirm).not.toHaveBeenCalled();
    });
  it('keeps database confirmation independent of workspace destination', () => {
    const confirm=vi.fn();
    render(<RecoveryConfirmSheetLazy kind="database" backup={backup} preview={preview} onCancel={()=>{}} onConfirm={confirm} />);
    const button=screen.getByRole('button',{name:'Restore Database'});
    expect(button.disabled).toBe(false);
    fireEvent.click(button);
    expect(confirm).toHaveBeenCalledOnce();
  });
  it('fails closed on a mismatched database preview', () => {
    render(<RecoveryConfirmSheetLazy kind="database" backup={backup} preview={{...preview,backup_id:'other'}} onCancel={()=>{}} onConfirm={vi.fn()} />);
    expect(screen.getByRole('button',{name:'Restore Database'}).disabled).toBe(true);
  });
});
