// @vitest-environment jsdom
import React from 'react';
import {describe,expect,it,vi,afterEach} from 'vitest';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import RecoveryConfirmSheetLazy from './RecoveryConfirmSheetLazy.jsx';
afterEach(()=>cleanup());
const backup={backup_id:'backup-a',created_at:'2026-10-10T10:00:00Z',verification_status:'verified'};
const preview={preview_id:'preview-a',backup_id:'backup-a',status:'ready',included_components:['settings'],excluded_components:['media']};
describe('protected restore impact confirmation',()=>{
  it('does not synthesize a zero impact count',()=>{
    render(<RecoveryConfirmSheetLazy backup={backup} preview={preview} onCancel={()=>{}} onConfirm={()=>{}} />);
    expect(screen.getByText('Impact not reported')).toBeTruthy();
    expect(screen.getByText(/excluded and unchanged/i)).toBeTruthy();
    expect(screen.getByRole('button',{name:'Restore Backup'})).toBeTruthy();
  });
  it('requires a deliberate click and respects busy double-submit protection',()=>{
    const confirm=vi.fn();
    const {rerender}=render(<RecoveryConfirmSheetLazy backup={backup} preview={preview} onCancel={()=>{}} onConfirm={confirm} busy />);
    expect(screen.getByRole('button',{name:'Restoring…'}).disabled).toBe(true);
    expect(confirm).not.toHaveBeenCalled();
    rerender(<RecoveryConfirmSheetLazy backup={backup} preview={preview} onCancel={()=>{}} onConfirm={confirm} />);
    fireEvent.click(screen.getByRole('button',{name:'Restore Backup'}));
    expect(confirm).toHaveBeenCalledTimes(1);
  });
});
