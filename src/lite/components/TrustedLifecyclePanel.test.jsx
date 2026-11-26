// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { LifecycleContent, ReleaseTrustSummary, ChangeImpactReview } from './TrustedLifecyclePanel.jsx';

afterEach(cleanup);
const data = { owner_authority: true, preferences: { revision: 0, profile: 'notify' }, release_trust: { historical_identity_verified: true, installed_tag: 'lite-2026.11.26.2' }, capabilities: [], grants: [] };
describe('Trusted Lifecycle presentation', () => {
  it('distinguishes historic release identity from publisher trust', () => {
    render(<ReleaseTrustSummary trust={data.release_trust} />);
    expect(screen.getByText('Trust setup required')).toBeTruthy();
    expect(screen.getByText(/not publisher authentication/i)).toBeTruthy();
  });
  it('does not equate preferences with activation', () => {
    render(<LifecycleContent data={data} onReview={vi.fn()} />);
    expect(screen.getByText('Not enabled by this foundation')).toBeTruthy();
    expect(screen.getByText(/saving a preference does not enable/i)).toBeTruthy();
  });
  it('shows unknown impact instead of claiming compatibility', () => {
    render(<ChangeImpactReview />);
    expect(screen.getByText('Impact not confirmed')).toBeTruthy();
  });
  it('keeps managed consent unavailable', () => {
    render(<LifecycleContent data={{ ...data, enterprise_managed: true }} />);
    expect(screen.getByText('Enterprise managed')).toBeTruthy();
    expect(screen.queryByText('Review Recommended')).toBeNull();
  });
});

it('blocks non-Owner changes and leaves historical trust separate', () => {
  render(<LifecycleContent data={{ ...data, owner_authority: false }} onReview={vi.fn()} />);
  expect(screen.getByRole('button', { name: 'Review Recommended' }).disabled).toBe(true);
  expect(screen.getByText(/only the current owner/i)).toBeTruthy();
});
it('shows expired evidence without installation eligibility', () => {
  render(<LifecycleContent data={{ ...data, release_trust: { state: 'metadata_expired' }, assessment: { impact: 'U4' } }} />);
  expect(screen.getByText('Metadata expired')).toBeTruthy();
  expect(screen.getByText('Additional permissions require review')).toBeTruthy();
  expect(screen.getByText('Not enabled by this foundation')).toBeTruthy();
});

it('offers an independent revoke without selecting the other permission', () => {
  const onReview = vi.fn();
  render(<LifecycleContent data={{ ...data, grants: [
    { grant_id: 'a'.repeat(32), purpose: 'release-reconciler', status: 'within_recorded_boundary' },
    { grant_id: 'b'.repeat(32), purpose: 'policy-reconciler', status: 'within_recorded_boundary' },
  ] }} onReview={onReview} />);
  fireEvent.click(screen.getByRole('button', { name: 'Revoke Release verification review' }));
  expect(onReview).toHaveBeenCalledWith({ kind: 'revoke', value: 'a'.repeat(32), label: 'Revoke Release verification review' });
  expect(screen.getByRole('button', { name: 'Revoke Safety Rules review' })).toBeTruthy();
});
it('distinguishes unconfirmed current trust from historical evidence', () => {
  render(<LifecycleContent data={{ ...data, release_trust: { state: 'current_trust_unconfirmed', current_review_eligible: false } }} />);
  expect(screen.getByText('Current trust not confirmed')).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Review release verification review' })).toBeNull();
  expect(screen.getByText('Not enabled by this foundation')).toBeTruthy();
});
