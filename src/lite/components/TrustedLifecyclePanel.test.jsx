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


it('shows scoped candidate evidence without any activation controls', () => {
  const candidate_review = { release_tag: 'lite-2026.11.27.1', source_package: { state: 'verified_for_review' },
    policy_review: { state: 'unknown_semantic_impact' }, policy_runtime_observation: { state: 'modules_match' },
    migration_review: { state: 'review_required' },
    capability_review: { total: 1, changes: [{ id: 'fixture.capability', impact: 'U4', changed_fields: 'targets' }] } };
  render(<LifecycleContent data={{ ...data, candidate_review }} />);
  expect(screen.getByText('Verified for review')).toBeTruthy();
  expect(screen.getByText('Policy change requires review')).toBeTruthy();
  expect(screen.getByText('Loaded Rego matched at recorded check')).toBeTruthy();
  expect(screen.getByText('Migration qualification required')).toBeTruthy();
  expect(screen.queryByRole('button', { name: /activate|install/i })).toBeNull();
});

it('does not expose owner candidate detail in a non-Owner view', () => {
  render(<LifecycleContent data={{ ...data, owner_authority: false, candidate_review: { release_tag: 'fixture' } }} />);
  expect(screen.queryByText('Candidate evidence')).toBeNull();
});

it('keeps isolated policy execution distinct from standing review consent', () => {
  const onReview = vi.fn();
  const metadata = 'a'.repeat(64);
  render(<LifecycleContent data={{ ...data, policy_execution_qualification_enabled: true,
    policy_execution_review_available: true, candidate_review: { metadata_sha256: metadata } }} onReview={onReview} />);
  fireEvent.click(screen.getByRole('button', { name: 'Review isolated policy activation' }));
  expect(onReview).toHaveBeenCalledWith({ kind: 'policy-execution', value: metadata, label: 'Review isolated policy activation' });
  expect(screen.getByText(/Production activation remains disabled/)).toBeTruthy();
});


it('shows preparation and offline rehearsal without implying production installation', () => {
  const onReview = vi.fn();
  const metadata = 'a'.repeat(64);
  render(<LifecycleContent data={{...data, release_preparation_qualification_enabled:true,
    release_preparation_review_available:true,candidate_review:{metadata_sha256:metadata},
    release_preparations:[{grant_id:'b'.repeat(32),state:'rehearsed'}]}} onReview={onReview}/>);
  expect(screen.getByText('Offline cutover rehearsed')).toBeTruthy();
  expect(screen.getByText(/Production installation remains disabled/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'Review isolated update preparation'}));
  expect(onReview).toHaveBeenCalledWith({kind:'release-preparation',value:metadata,label:'Review isolated update preparation'});
});

it('does not offer release preparation controls from stale state', () => {
  render(<LifecycleContent readOnly data={{...data,release_preparation_qualification_enabled:true,
    release_preparation_review_available:true,candidate_review:{metadata_sha256:'a'.repeat(64)}}}/>);
  expect(screen.getByRole('button',{name:'Review isolated update preparation'}).disabled).toBe(true);
});
