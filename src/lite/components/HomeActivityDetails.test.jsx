// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen, fireEvent } from '@testing-library/react';
import { afterEach, describe, it, expect, vi } from 'vitest';
import HomeActivityDetails from './HomeActivityDetails.jsx';

afterEach(cleanup);

const activity = {
  active: 1, queued: 2, completed: 3, attention: 0, stale: 5, historicalFailures: 2,
  runningWindowMinutes: 30, historyWindowDays: 7,
  attentionScope: 'explicit_active_flags_only', grouped: [],
  events: [{ domain: 'devices', status: 'stale', statusLabel: 'Not confirmed running',
    at: 1700000000000, label: 'Device command' }],
};
describe('Activity details progressive disclosure', () => {
  it('keeps old unfinished work out of Running and available in History', () => {
    render(<HomeActivityDetails activity={activity} onNavigate={vi.fn()} />);
    expect(screen.getByText(/older unfinished records/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Running' }));
    expect(screen.queryByText('Not confirmed running')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'History' }));
    expect(screen.getByText('Not confirmed running')).toBeTruthy();
  });
  it('only offers personal Mark Reviewed in History and requires explicit click', () => {
    const onMarkReviewed = vi.fn();
    render(<HomeActivityDetails activity={activity} cursor={{ changed_since_review: true }}
      onNavigate={vi.fn()} onMarkReviewed={onMarkReviewed} />);
    expect(screen.queryByRole('button', { name: 'Mark activity reviewed' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'History' }));
    fireEvent.click(screen.getByRole('button', { name: 'Mark activity reviewed' }));
    expect(onMarkReviewed).toHaveBeenCalledTimes(1);
  });
  it('does not allow a saved snapshot to acknowledge a review', () => {
    const onMarkReviewed = vi.fn();
    render(<HomeActivityDetails activity={activity} saved cursor={{ changed_since_review: true }}
      onNavigate={vi.fn()} onMarkReviewed={onMarkReviewed} />);
    fireEvent.click(screen.getByRole('button', { name: 'History' }));
    const button = screen.getByRole('button', { name: 'Mark activity reviewed' });
    expect(button.disabled).toBe(true);
    fireEvent.click(button);
    expect(onMarkReviewed).not.toHaveBeenCalled();
  });
});
