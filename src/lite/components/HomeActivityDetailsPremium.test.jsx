// @vitest-environment jsdom
import React from 'react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import HomeActivityDetails from './HomeActivityDetails.jsx';
import { selectHomeActivityEvidence } from '../homeActivityEvidence.js';

afterEach(cleanup);
const activity = selectHomeActivityEvidence({
  history_available: true, counts_available: true,
  active_operations: 1, queued_operations: 2, recent_completed: 12,
  attention_required: 0, historical_failures: 3, stale_operations: 1,
  running_window_minutes: 45, history_window_days: 5,
  attention_scope: 'explicit_active_flags_only',
  recent_events: [
    { domain: 'devices', label: 'Device command', status: 'failed',
      needs_attention: false, occurred_at_epoch_ms: 1780000000000 },
    { domain: 'recovery', label: 'Backup', status: 'running',
      is_fresh_running: true, occurred_at_epoch_ms: 1780000001000 },
  ],
});

describe('Premium Recent Activity', () => {
  it('uses backend-reported time windows and separates history from active attention', () => {
    render(<HomeActivityDetails activity={activity} onNavigate={vi.fn()} />);
    expect(screen.getByLabelText('Activity time window')).toHaveTextContent('last 45 minutes');
    expect(screen.getByLabelText('Activity time window')).toHaveTextContent('last 5 days');
    expect(screen.getByLabelText('How attention is counted')).toHaveTextContent('Historical failures');
    fireEvent.click(screen.getByRole('button', { name: 'History', exact: true }));
    expect(screen.getByLabelText('Historical failures')).toHaveTextContent('3');
    expect(screen.getByText('Failed')).toBeTruthy();
  });
  it('shows bounded empty/unavailable states without fabricating a success', () => {
    const { rerender } = render(<HomeActivityDetails activity={null} />);
    expect(screen.getByText('Activity unavailable')).toBeTruthy();
    rerender(<HomeActivityDetails activity={activity} />);
    expect(screen.getByText(/No attention events in this sample/i)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Recent', exact: true }));
    expect(screen.getByRole('button', { name: /Open Devices for Device command/i })).toBeTruthy();
  });
  it('makes review positions private and never submits while saved or busy', () => {
    const review = vi.fn();
    render(<HomeActivityDetails activity={activity} saved cursor={{ changed_since_review: true }}
      onMarkReviewed={review} />);
    fireEvent.click(screen.getByRole('button', { name: 'History', exact: true }));
    const card = screen.getByLabelText('Personal activity review');
    expect(within(card).getByText('Something changed since your last review.')).toBeTruthy();
    expect(within(card).getByText(/does not resolve an issue, approve work, clear audit history or retry an action/)).toBeTruthy();
    const button = within(card).getByRole('button', { name: 'Mark activity reviewed' });
    expect(button.disabled).toBe(true);
    fireEvent.click(button);
    expect(review).not.toHaveBeenCalled();
  });
  it('shows review read failures as a semantic unavailable state and preserves keyboard actions', () => {
    render(<HomeActivityDetails activity={activity} cursorError="Review history couldn't be loaded." />);
    fireEvent.click(screen.getByRole('button', { name: 'History', exact: true }));
    expect(screen.getByText('Review history unavailable')).toBeTruthy();
    expect(screen.getByText("Review history couldn't be loaded.")).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Mark activity reviewed' })).toBeNull();
  });
  it('avoids exceptions on missing and malformed timestamps', () => {
    render(<HomeActivityDetails activity={{ ...activity, events: [{ domain: 'apps', label: 'App operation',
      statusLabel: 'Completed', status: 'completed', at: 'not-a-time' }] }} />);
    fireEvent.click(screen.getByRole('button', { name: 'History', exact: true }));
    expect(screen.getByText('Time not available')).toBeTruthy();
  });
});
