import React, { useRef, useState } from 'react';
import { ShieldCheck } from 'lucide-react';
import { LiteActionRow, LiteButton, StateSurface } from '../LiteUi.jsx';
import { useLiteQuery } from '../../hooks/useLiteQuery.js';
import { liteApi } from '../../lib/liteApi.js';
import { getLitePasskey, webAuthnAvailable } from '../../lib/liteWebAuthn.js';

const profiles = [
  ['recommended', 'Recommended', 'Prepare for compatible stable updates. New permissions still require review.'],
  ['security', 'Security updates only', 'Prefer compatible security updates. Unknown changes still require review.'],
  ['notify', 'Notify me', 'Review releases before taking action. No new standing consent.'],
];
const names = { recommended: 'Recommended', security: 'Security updates only', notify: 'Notify me', enterprise_managed: 'Enterprise managed' };
const purposes = { 'release-reconciler': 'Release verification review', 'policy-reconciler': 'Safety Rules review' };
const dispositions = { within_recorded_boundary: 'Recorded consent', review_required: 'Review required', revoked: 'Revoked', expired: 'Expired' };
const facts = { verified: 'Verified at the recorded check', failed: 'Verification failed', unknown: 'Not confirmed' };

export function ReleaseTrustSummary({ trust }) {
  const receipt = trust?.receipt;
  return <div className="lite-system-health-detail-block">
    <h4><ShieldCheck size={18} aria-hidden="true" /> Release trust</h4>
    <LiteActionRow label="Installed release" value={trust?.installed_tag || 'Not confirmed'}
      summary={trust?.historical_identity_verified ? 'Verified under the existing release identity contract. This is not publisher authentication.' : 'Installed identity is not confirmed.'} />
    <LiteActionRow label="Publisher trust" value={({historical_evidence: 'Historical evidence', verification_failed: 'Verification failed', metadata_unavailable: 'Trusted metadata unavailable', trust_setup_required: 'Trust setup required'})[trust?.state] || 'Not confirmed'}
      summary="A checksum alone does not establish publisher trust. No fresh verification is claimed here." />
    <details>
      <summary>View verification details</summary>
      {receipt ? <>
        <LiteActionRow label="Recorded release" value={receipt.release_tag || 'Not confirmed'} />
        <LiteActionRow label="Metadata signature" value={facts[receipt.authenticity] || 'Not confirmed'} />
        <LiteActionRow label="Artifact integrity" value={facts[receipt.integrity] || 'Not confirmed'} />
        <LiteActionRow label="Build provenance" value={facts[receipt.provenance] || 'Not confirmed'} />
        <LiteActionRow label="Recorded check" value={receipt.checked_at || 'Not confirmed'} />
        <LiteActionRow label="Metadata expiry" value={receipt.expires || 'Not confirmed'} />
      </> : <p>New signed release evidence is not available. Historical releases remain distinct from authenticated releases.</p>}
    </details>
  </div>;
}

export function ChangeImpactReview({ assessment }) {
  const descriptions = {
    U0: 'Presentation-only change', U1: 'Structured permissions unchanged',
    U2: 'Restrictive change', U3: 'Optional capability review',
    U4: 'Additional permissions require review', U5: 'Trust or ownership change requires review',
    UX: 'Impact not confirmed',
  };
  const impact = assessment?.impact || 'UX';
  return <div className="lite-system-health-detail-block">
    <h4>Review changes</h4>
    <LiteActionRow label={descriptions[impact] || descriptions.UX}
      summary="Compatibility and permission review do not authorize installation." />
    {['added', 'removed', 'changed'].map(key => Array.isArray(assessment?.[key]) && assessment[key].length > 0 &&
      <LiteActionRow key={key} label={key === 'added' ? 'Added capabilities' : key === 'removed' ? 'Removed capabilities' : 'Changed capabilities'} value={String(assessment[key].length)} />)}
  </div>;
}

export function LifecycleContent({ data, readOnly = false, busy = false, pending, onReview, onConfirm, onCancel, message }) {
  const prefs = data?.preferences;
  const managed = data?.enterprise_managed === true;
  const blocked = readOnly || busy || !prefs;
  const canGrant = !managed && prefs?.profile === 'recommended' && data?.release_trust?.state === 'historical_evidence' && data?.release_trust?.receipt != null;
  const grants = Array.isArray(data?.grants) ? data.grants : [];
  return <section className="lite-system-health-manage-section" aria-label="Updates & protection">
    <div className="lite-system-health-manage-intro"><h3>Updates &amp; protection</h3>
      <p>Review release trust, choose update preferences and manage recorded permissions.</p></div>
    <ReleaseTrustSummary trust={data?.release_trust} />
    <div className="lite-system-health-detail-block">
      <h4>Update preferences</h4>
      <LiteActionRow label="Saved preference" value={managed ? 'Enterprise managed' : names[prefs?.profile] || 'Not confirmed'}
        summary="Saving a preference does not enable unattended installation, policy activation or maintenance." />
      {managed && <p>Broader managed consent requires a separately qualified governance workflow.</p>}
      {!managed && profiles.map(([id, name, description]) => <LiteActionRow key={id} label={name} summary={description}
        value={prefs?.profile === id ? 'Selected' : undefined}
        action={prefs?.profile !== id ? { label: 'Review ' + name, haptic: true, disabled: blocked || Boolean(pending), onClick: () => !blocked && !pending && onReview({ kind: 'profile', value: id, label: name }) } : undefined} />)}
      {prefs?.profile !== 'notify' && <LiteButton haptic tone="secondary" disabled={blocked || Boolean(pending)}
        onClick={() => onReview({ kind: 'profile', value: 'notify', label: 'Notify me' })}>Pause new standing consent</LiteButton>}
    </div>
    <div className="lite-system-health-detail-block">
      <h4>Your permissions</h4>
      <LiteActionRow label="Unattended execution" value="Not enabled by this foundation" />
      <LiteActionRow label="Safety Rules" value="Existing authority unchanged" />
      <LiteActionRow label="Routine maintenance and app updates" value="Existing controls unchanged" />
      <details>
        <summary>Review capability contracts</summary>
        {(data?.capabilities || []).map(cap => <LiteActionRow key={cap.id} label={cap.id}
          value={'Version ' + cap.version} summary="Descriptive contract only; no new execution rights." />)}
      </details>
      {grants.map(grant => <LiteActionRow key={grant.grant_id} label={purposes[grant.purpose] || 'Recorded permission'}
        value={dispositions[grant.status] || 'Review required'} summary="No executable service identity is issued." />)}
      {canGrant && Object.entries(purposes).map(([value, label]) =>
        <LiteButton key={value} haptic tone="secondary" disabled={blocked || Boolean(pending)}
          onClick={() => onReview({ kind: 'grant', value, label })}>Review {label.toLowerCase()}</LiteButton>)}
      {grants.some(grant => grant.status !== 'revoked') && <LiteButton haptic tone="secondary" disabled={blocked || Boolean(pending)}
        onClick={() => onReview({ kind: 'revoke', label: 'Revoke standing consent' })}>Revoke standing consent</LiteButton>}
      {!canGrant && <p>New standing consent requires a current Owner, the Recommended profile and recorded trusted release evidence.</p>}
    </div>
    <ChangeImpactReview assessment={data?.assessment} />
    {pending && <div className="lite-system-health-detail-block" role="group" aria-label="Review proposed change">
      <h4>{pending.label}</h4>
      <p>{pending.kind === 'grant' ? 'Record a limited, revocable review permission for 30 days. This replaces previous standing consent; it cannot start a service or install anything.'
        : pending.kind === 'revoke' ? 'Prevent new use of recorded consent. This does not claim to cancel existing work.'
        : 'Save this preference and revoke previous standing consent. Existing release and recovery settings are not changed.'}</p>
      <LiteButton haptic tone="primary" disabled={blocked} onClick={onConfirm}>{busy ? 'Submitting…' : 'Confirm'}</LiteButton>
      <LiteButton haptic tone="secondary" disabled={busy} onClick={onCancel}>Cancel</LiteButton>
    </div>}
    {message && <p role="status">{message}</p>}
  </section>;
}

export default function TrustedLifecyclePanel({ readOnly = false }) {
  const [pending, setPending] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const inFlight = useRef(false);
  const query = useLiteQuery({ queryKey: ['lite', 'lifecycle', 'owner-summary'], path: '/api/lite/lifecycle/summary',
    queryFn: liteApi.lifecycleSummary, enabled: !readOnly, staleTime: 0, gcTime: 0,
    refetchOnMount: 'always', pollingMode: 'off' });
  const data = query.data;
  const writable = !readOnly && !query.error && query.backendReachable === true && !query.refreshing && data?.schema_version === 1;
  async function exactPasskey(review) {
    if (!webAuthnAvailable()) throw new Error('passkey_unavailable');
    const options = await liteApi.passkeyStepUpOptions(review.purpose);
    const credential = await getLitePasskey(options);
    await liteApi.verifyPasskeyStepUp({ purpose: review.purpose, challenge: options.publicKey.challenge, credential });
  }
  async function confirm() {
    if (!pending || !writable || inFlight.current) return;
    inFlight.current = true; setBusy(true); setMessage('');
    try {
      if (pending.kind === 'profile') {
        const body = { expected_revision: pending.revision, profile: pending.value, confirm: true };
        if (pending.value !== 'notify') await exactPasskey(await liteApi.lifecycleReviewPreference(body));
        await liteApi.lifecyclePreference(body);
      } else if (pending.kind === 'grant') {
        const body = { expected_revision: pending.boundary, expected_profile_revision: pending.revision, purpose: pending.value, confirm: true };
        await exactPasskey(await liteApi.lifecycleReviewBoundary(body));
        await liteApi.lifecycleIssueBoundary(body);
      } else if (pending.kind === 'revoke') {
        await liteApi.lifecycleRevokeBoundary({ expected_revision: pending.boundary, confirm: true });
      }
      setMessage('Change recorded. Unattended execution remains disabled in this foundation.');
      await query.refresh();
    } catch {
      setMessage('The change was not confirmed. Review current information before trying again.');
      await query.refresh();
    } finally { setPending(null); setBusy(false); inFlight.current = false; }
  }
  if (readOnly || query.error || !data || data.schema_version !== 1) return <StateSurface
    tone={query.loading && !readOnly ? 'empty' : 'degraded'}
    title={query.loading && !readOnly ? 'Loading updates & protection' : 'Verification unavailable'}
    description="Reconnect and sign in as Owner to review current permissions. No change can be submitted." />;
  return <LifecycleContent data={data} readOnly={!writable} busy={busy} pending={pending} message={message}
    onReview={change => { if (writable && !busy) { setMessage(''); setPending({ ...change, revision: data.preferences.revision, boundary: data.boundary_revision }); } }}
    onConfirm={confirm} onCancel={() => setPending(null)} />;
}
