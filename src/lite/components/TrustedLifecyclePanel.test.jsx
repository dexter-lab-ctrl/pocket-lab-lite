// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { LifecycleContent, ReleaseTrustSummary, ChangeImpactReview } from './TrustedLifecyclePanel.jsx';

afterEach(cleanup);
const data = { preferences: { revision: 0, profile: 'notify' }, release_trust: { historical_identity_verified: true, installed_tag: 'lite-2026.11.26.2' }, capabilities: [], grants: [] };
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
