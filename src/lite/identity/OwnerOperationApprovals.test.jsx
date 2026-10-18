// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import OwnerOperationApprovals from './OwnerOperationApprovals.jsx';

afterEach(cleanup);

const pending = {
  operation_id: 'oo-test-pending',
  status: 'pending_approval',
  requester_display_name: 'Registered qualification client',
  target_label: 'Secondary Phone',
  destination: 'PhotoPrism on this server',
  reason: 'Production Photo Backup acceptance',
  approval_deadline: '2026-10-18T12:15:00Z',
  disclosures: ['Target: Secondary Phone.', 'One generated synthetic test photo may remain in the destination.'],
};

describe('Owner-approved Photo Backup surface', () => {
  it('stays absent when the server reports no pending operations', () => {
    const { container } = render(<OwnerOperationApprovals operations={[]} fresh />);
    expect(container.firstChild).toBeNull();
  });

  it('discloses the immutable bounded scope and calls the decision handlers', () => {
    const approve = vi.fn();
    const reject = vi.fn();
    render(<OwnerOperationApprovals operations={[pending]} fresh onApprove={approve} onReject={reject} />);

    expect(screen.getByRole('heading', { name: 'Pending approvals' })).toBeInTheDocument();
    expect(screen.getByText('Secondary Phone')).toBeInTheDocument();
    expect(screen.getByText(/one generated synthetic test photo may remain/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Approve' }));
    fireEvent.click(screen.getByRole('button', { name: 'Reject' }));
    expect(approve).toHaveBeenCalledWith(pending);
    expect(reject).toHaveBeenCalledWith(pending);
  });

  it('keeps all decision controls disabled when the projection is stale', () => {
    render(<OwnerOperationApprovals operations={[pending]} fresh={false} />);
    expect(screen.getByText('Live approval data unavailable')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Approve' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Reject' })).toBeDisabled();
  });

  it('disables every decision while one approval is being submitted', () => {
    render(<OwnerOperationApprovals operations={[pending]} fresh busy="approve:oo-test-pending" />);
    expect(screen.getByRole('button', { name: 'Approving…' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Reject' })).toBeDisabled();
  });

  it('does not offer approval controls for terminal or executing states', () => {
    render(<OwnerOperationApprovals operations={[
      { ...pending, operation_id: 'oo-completed', status: 'completed' },
      { ...pending, operation_id: 'oo-executing', status: 'executing' },
      { ...pending, operation_id: 'oo-expired', status: 'expired', terminal_reason: 'Approval window expired.' },
    ]} fresh />);
    expect(screen.queryAllByRole('button', { name: 'Approve' })).toHaveLength(0);
    expect(screen.queryAllByRole('button', { name: 'Reject' })).toHaveLength(0);
    expect(screen.getByText('Approval window expired.')).toBeInTheDocument();
  });
});
