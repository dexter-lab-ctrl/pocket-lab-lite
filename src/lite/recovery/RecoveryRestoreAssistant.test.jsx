// @vitest-environment jsdom
// NOT RUN — implementation-only session
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import RecoveryRestoreAssistant from './RecoveryRestoreAssistant.jsx';
import RecoveryJourney from './RecoveryJourney.jsx';
import RecoveryPremiumTimeline from './RecoveryPremiumTimeline.jsx';
import { recoveryJourneyStatus, recoveryPremiumActivity, recoveryPremiumHero, recoveryRestoreImpact } from './recoveryPremiumView.js';

afterEach(cleanup);
const backup = { backup_id: 'synthetic-backup', created_at: '2026-10-10T12:00:00Z', verification_status: 'verified' };
const preview = { preview_id: 'synthetic-preview', backup_id: backup.backup_id, status: 'ready', restore_allowed: true, change_count: 0 };

describe('Recovery Center native experience — qualification authored only', () => {
  it('keeps stage navigation presentation-only; clicking never calls an operation', () => {
    const onStepChange = vi.fn();
    const onRestore = vi.fn();
    render(<RecoveryRestoreAssistant step="choose" onStepChange={onStepChange}>
      <button onClick={onRestore} type="button">Explicit restore action</button>
    </RecoveryRestoreAssistant>);
    fireEvent.click(screen.getByRole('button', { name: /Step 3: Review safety checks/ }));
    expect(onStepChange).toHaveBeenCalledWith('safety');
    expect(onRestore).not.toHaveBeenCalled();
    expect(screen.getByText(/selection never starts recovery/i)).toBeInTheDocument();
  });
  it('does not describe an unavailable or mismatched preview as ready', () => {
    const wrong = { ...preview, backup_id: 'another-backup' };
    expect(recoveryRestoreImpact({ backup, preview: wrong }).ready).toBe(false);
    expect(recoveryJourneyStatus({ backup, preview: wrong }).preview).toBe('needs_action');
    expect(recoveryPremiumHero({ backup, preview: wrong }).previewReady).toBe(false);
  });
  it('provides explicit safety warnings for saved or unverified states', () => {
    render(<RecoveryRestoreAssistant step="confirm" verified={false} previewReady={false} writeBlocked onStepChange={vi.fn()}/>);
    expect(screen.getByText(/Live recovery authority is unavailable/)).toBeInTheDocument();
    expect(screen.getByText(/matching backend preview are required/)).toBeInTheDocument();
  });
  it('does not promote selected readiness to backend completion', () => {
    const actual = { backup: 'completed', verify: 'needs_action', preview: 'blocked', restore: 'unknown' };
    render(<RecoveryJourney stages={actual} saved />);
    expect(screen.getByText('Recovery Readiness')).toBeInTheDocument();
    expect(screen.getAllByText('Unknown')).toHaveLength(4);
  });
  it('limits overview activity to one backend record without dropping the event/snapshot distinction', () => {
    const events = recoveryPremiumActivity({ activity: [
      { id: '1', kind: 'backup', status: 'completed', occurred_at: '2026-10-10T12:00:00Z' },
      { id: '2', kind: 'verify', status: 'completed', occurred_at: '2026-10-10T13:00:00Z' },
    ] });
    render(<RecoveryPremiumTimeline items={events} onViewActivity={vi.fn()}/>);
    expect(screen.getByText('Backup verification')).toBeInTheDocument();
    expect(screen.queryByText('Backup recorded')).not.toBeInTheDocument();
    expect(recoveryPremiumActivity({ backup })[0].origin).toBe('snapshot');
  });
  it('keeps missing impact count distinct from zero and never supplies browser-side authority', () => {
    expect(recoveryRestoreImpact({ backup, preview: { ...preview, change_count: undefined } }).count).toBeNull();
    expect(recoveryRestoreImpact({ backup, preview }).count).toBe(0);
    expect(recoveryPremiumHero({ backup, preview, saved: true }).disabled).toBe(true);
    expect(recoveryPremiumHero({ backup, preview, stale: true }).disabled).toBe(true);
  });
});
