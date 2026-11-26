import React from 'react';
import { LifecycleContent } from './TrustedLifecyclePanel.jsx';

const base = { schema_version: 1, preferences: { profile: 'notify', revision: 0 },
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
