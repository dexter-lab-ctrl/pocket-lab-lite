// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import TrustedAutomationClients from './TrustedAutomationClients.jsx';

afterEach(cleanup);

const fingerprint = 'sha256:0c0b0319cbdc382555faeb3dfd0d465870c6e6c287b2e81acd425f34ce6cf39d';
const pending = {
  pairing_id: 'ocp-mock-pending',
  client_id: 'registered-qualification-client',
  display_name: 'Registered qualification client',
  public_key_fingerprint: fingerprint,
  capabilities: ['photo_backup.bounded_acceptance.v1'],
  status: 'pending',
  expires_at: '2026-10-19T12:15:00Z',
};
const active = {
  client_id: 'registered-qualification-client',
  display_name: 'Registered qualification client',
  public_key_fingerprint: fingerprint,
  capabilities: ['photo_backup.bounded_acceptance.v1'],
  status: 'active',
  created_at: '2026-10-19T12:00:00Z',
};

describe('Trusted automation client enrollment surface', () => {
  it('shows the exact pending identity and fixed capability without key material', () => {
    const approve = vi.fn();
    const reject = vi.fn();
    render(<TrustedAutomationClients pairings={[pending]} fresh onApprove={approve} onReject={reject} />);

    expect(screen.getByRole('heading', { name: 'Trusted automation clients' })).toBeInTheDocument();
    expect(screen.getByText('Pending client registration')).toBeInTheDocument();
    expect(screen.getByText(fingerprint)).toBeInTheDocument();
    expect(screen.getByText('photo_backup.bounded_acceptance.v1')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Register client' }));
    fireEvent.click(screen.getByRole('button', { name: 'Reject registration' }));
    expect(approve).toHaveBeenCalledWith(pending);
    expect(reject).toHaveBeenCalledWith(pending);
    expect(screen.queryByText(/private key|signing payload/i)).not.toBeInTheDocument();
  });

  it('keeps registration and revocation disabled for stale saved state', () => {
    const approve = vi.fn();
    const revoke = vi.fn();
    render(<TrustedAutomationClients clients={[active]} pairings={[pending]} fresh={false} onApprove={approve} onRevoke={revoke} />);

    expect(screen.getByText('Live client data unavailable')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Register client' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Revoke client' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Register client' }));
    fireEvent.click(screen.getByRole('button', { name: 'Revoke client' }));
    expect(approve).not.toHaveBeenCalled();
    expect(revoke).not.toHaveBeenCalled();
  });

  it('shows terminal pairings as evidence and only offers revocation for active clients', () => {
    const revoke = vi.fn();
    render(<TrustedAutomationClients clients={[active]} pairings={[{ ...pending, pairing_id: 'ocp-expired', status: 'expired', terminal_reason: 'Pairing window expired.' }]} fresh onRevoke={revoke} />);
    expect(screen.getByText('Pairing window expired.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Revoke client' })).toBeEnabled();
    fireEvent.click(screen.getByRole('button', { name: 'Revoke client' }));
    expect(revoke).toHaveBeenCalledWith(active);
    expect(screen.queryByRole('button', { name: 'Register client' })).not.toBeInTheDocument();
  });
});
