import React from 'react';
import { LifecycleContent } from './TrustedLifecyclePanel.jsx';

const base = { schema_version: 1, owner_authority: true, preferences: { profile: 'notify', revision: 0 },
  release_trust: { historical_identity_verified: true, installed_tag: 'lite-2026.11.26.2' }, grants: [], capabilities: [] };
export default { title: 'Pocket Lab Lite/Azure Horizon/Updates and protection', component: LifecycleContent,
  args: { data: base, readOnly: true } };
export const HistoricalRelease = {};
export const Managed = { args: { data: { ...base, enterprise_managed: true } } };
export const UnknownImpact = { args: { data: { ...base, assessment: { impact: 'UX' } } } };
export const RecordedConsent = { args: { data: { ...base, preferences: { profile: 'recommended', revision: 1 },
  grants: [{ grant_id: 'fixture', purpose: 'release-reconciler', status: 'within_recorded_boundary' }] } } };
export const Review = { args: { pending: { kind: 'revoke', label: 'Revoke standing consent' } } };

export const ExpiredEvidence = { args: { data: { ...base, release_trust: { state: 'metadata_expired' } } } };
export const FailedVerification = { args: { data: { ...base, release_trust: { state: 'verification_failed' } } } };
export const ExpandedPermissions = { args: { data: { ...base, assessment: { impact: 'U4', added: ['fixture'] } } } };
export const NonOwner = { args: { data: { ...base, owner_authority: false } } };

export const IndependentPermissions = { args: { data: { ...base, preferences: { profile: 'recommended', revision: 2 },
  grants: [
    { grant_id: 'a'.repeat(32), purpose: 'release-reconciler', status: 'within_recorded_boundary' },
    { grant_id: 'b'.repeat(32), purpose: 'policy-reconciler', status: 'within_recorded_boundary' },
  ] } } };
export const SecurityOnly = { args: { data: { ...base, preferences: { profile: 'security', revision: 3 } } } };
export const RevokedPermission = { args: { data: { ...base, grants: [
  { grant_id: 'a'.repeat(32), purpose: 'release-reconciler', status: 'revoked' },
] } } };

export const CurrentTrustUnconfirmed = { args: { data: { ...base, release_trust: { state: 'current_trust_unconfirmed', current_review_eligible: false } } } };


export const CoordinatedCandidateReview = { args: { data: { ...base, candidate_review: {
  release_tag: 'lite-2026.11.27.1', checked_at: '2026-11-27T00:00:00Z',
  source_package: { state: 'verified_for_review' }, policy_review: { state: 'unknown_semantic_impact' },
  policy_runtime_observation: { state: 'modules_match' }, migration_review: { state: 'review_required' },
  capability_review: { total: 1, changes: [{ id: 'fixture.capability', impact: 'U4', changed_fields: ['targets', 'network'] }] },
} } } };
export const CandidateWithoutSource = { args: { data: { ...base, candidate_review: {
  release_tag: 'lite-2026.11.27.1', source_package: { state: 'not_delivered' },
  capability_review: { total: 0, changes: [] },
} } } };
