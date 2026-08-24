import './identityRules.css';
import React from 'react';
import { FileCheck, ShieldCheck } from 'lucide-react';
import { useLiteResource } from '../hooks/useLiteStatus.js';
import { formatLiteTime, liteApi } from '../lib/liteApi.js';
import { getLiteReasonPresentation } from '../lib/identityRulesPresentation.js';
import {
  GlassCard,
  StatusBadge,
  StateSurface,
  PageHeader,
  LiteRefreshButton,
  LoadingCard,
} from './LiteUi.jsx';
import LiteRulesEnterprise from './LiteRulesEnterprise.jsx';

function actionLabel(action = '') {
  return ({
    'catalog.install': 'Install an app',
    'device.remove': 'Remove a device',
    'identity.passkey.revoke': 'Remove a passkey',
  })[action] || String(action || '').replaceAll('.', ' · ');
}

export default function RulesScreen() {
  const {
    data,
    loading,
    error,
    refresh,
    cacheStatus,
    refreshing,
    savedStateOnly,
    backendReachable,
    lastUpdatedLabel,
    isExpired,
    backendDegraded,
  } = useLiteResource(liteApi.policy, []);
  const enterprise = useLiteResource(liteApi.enterpriseIdentity, []);
  const [advancedOpen, setAdvancedOpen] = React.useState(false);
  const enterpriseEnabled = Boolean(enterprise.data?.enabled);
  const ready = data?.status === 'ready' && data?.engine?.healthy && data?.engine?.loopback_only;
  const recent = Array.isArray(data?.recent_decisions) ? data.recent_decisions.slice(0, 4) : [];
  const templates = Array.isArray(data?.templates) ? data.templates : [];
  const degraded = getLiteReasonPresentation(data?.degraded_reason, data?.summary || 'Safety Rules need attention.');

  return (
    <>
      <PageHeader
        eyebrow="Rules"
        title="Safety Rules"
        description="See which protected changes are covered, what Pocket Lab may ask you to confirm, and why a sensitive action was allowed or blocked."
        actions={<LiteRefreshButton scope="rules" refresh={refresh} cacheStatus={cacheStatus} error={error} refreshing={refreshing} />}
      />

      <section className="lite-rules-hero" aria-labelledby="rules-posture-title">
        <div className="lite-rules-hero-copy">
          <div className="lite-home-pill"><span className="lite-ready-dot" />{ready ? 'Rules ready' : 'Safety Rules need attention'}</div>
          <h2 id="rules-posture-title">{ready ? 'Protected changes are covered.' : 'Protected changes stay blocked until Rules recover.'}</h2>
          <p>{ready ? 'Pocket Lab checks sensitive changes on the server and fails closed when Rules are unavailable.' : degraded.message}</p>
        </div>
        <div className="lite-rules-status-card">
          <div className="lite-rules-icon"><FileCheck className="h-7 w-7" /></div>
          <span>Safety Rules</span>
          <strong>{ready ? 'Ready' : 'Needs attention'}</strong>
          <StatusBadge status={ready ? 'healthy' : 'degraded'}>{ready ? 'Protected' : 'Changes blocked'}</StatusBadge>
        </div>
      </section>

      {loading ? <LoadingCard label="Checking Safety Rules..." /> : null}
      {error && !data ? <StateSurface tone="degraded" title="Safety Rules are unavailable" description={String(error)} className="mb-5" /> : null}
      {savedStateOnly ? <StateSurface tone="neutral" title="Showing saved Rules state" description={`${isExpired ? 'This saved state is old. ' : ''}${lastUpdatedLabel || 'Pocket Lab will refresh it when the backend is reachable.'} Protected write actions must still be verified by the server.`} className="mb-5" /> : null}
      {backendDegraded && backendReachable ? <StateSurface tone="degraded" title="Safety Rules need attention" description={degraded.message} className="mb-5" /> : null}

      {!loading && data ? (
        <div className="lite-rules-grid lite-rules-personal-grid">
          <GlassCard className="lite-rules-card lite-rules-primary-card">
            <div className="lite-rules-card-head"><div className="lite-rules-mini-icon"><ShieldCheck className="h-5 w-5" /></div><StatusBadge status={ready ? 'healthy' : 'degraded'}>{ready ? 'Active' : 'Blocked'}</StatusBadge></div>
            <h2>Protections active</h2>
            <p>These sensitive actions are evaluated by Pocket Lab before they continue.</p>
            <div className="lite-rules-list">
              {(data?.policy_groups || []).map((group, index) => (
                <div key={group.id}>
                  <span>{index + 1}</span>
                  <p><strong>{group.label}</strong><small>{(group.actions || []).map(actionLabel).join(' · ')}</small></p>
                </div>
              ))}
            </div>
          </GlassCard>

          <GlassCard className="lite-rules-card lite-rules-guide-card">
            <div className="lite-rules-card-head"><div className="lite-rules-mini-icon"><FileCheck className="h-5 w-5" /></div><span className="lite-rules-soft-badge">What to expect</span></div>
            <h2>Sensitive changes stay deliberate</h2>
            <div className="lite-identity-checklist">
              <div><span className="lite-check-dot" /><strong>Server check first</strong><small>Pocket Lab evaluates the protected action before it is accepted.</small></div>
              <div><span className="lite-check-dot" /><strong>Passkey when needed</strong><small>Some changes require recent passkey confirmation.</small></div>
              <div><span className="lite-check-dot" /><strong>Fail closed</strong><small>If Rules cannot prove a safe decision, the protected change stays blocked.</small></div>
            </div>
          </GlassCard>
        </div>
      ) : null}

      {!loading && data ? (
        <GlassCard className="lite-rules-card mt-5">
          <div className="lite-rules-card-head"><div className="lite-rules-mini-icon"><ShieldCheck className="h-5 w-5" /></div><span className="lite-rules-soft-badge">Safe templates</span></div>
          <h2>How Pocket Lab protects changes</h2>
          <p>Safeguards are server-owned and intentionally bounded. The browser cannot grant itself a role, assurance, approval or exception.</p>
          <div className="lite-rules-template-grid">
            {templates.map((template) => (
              <div key={template.id} className="lite-rules-template-card">
                <div><strong>{template.label}</strong><StatusBadge status={template.status === 'active' ? 'healthy' : 'neutral'}>{template.status === 'active' ? 'Active' : 'Available'}</StatusBadge></div>
                <p>{template.summary}</p>
              </div>
            ))}
            {!templates.length ? <StateSurface tone="neutral" title="No safeguard summaries" description="Pocket Lab will show the current safe templates here when the backend returns them." /> : null}
          </div>
          <details
            className="lite-rules-advanced-details mt-4"
            onToggle={(event) => setAdvancedOpen(event.currentTarget.open)}
          >
            <summary>Advanced diagnostics</summary>
            {advancedOpen ? (
              <div className="mt-3">
                <div className="lite-rules-facts">
                  <div><span>Policy engine</span><strong>{data?.engine?.name || 'Local policy runtime'}</strong></div>
                  <div><span>Runtime version</span><strong>{data?.engine?.version || 'unknown'}</strong></div>
                  <div><span>Network boundary</span><strong>{data?.engine?.loopback_only ? 'Local only' : 'Needs attention'}</strong></div>
                  <div><span>Browser access</span><strong>{data?.engine?.endpoint_exposed_to_browser ? 'Unexpected exposure' : 'Not exposed'}</strong></div>
                  <div><span>Rules package</span><strong>{data?.active_policy?.bundle_ready ? 'Ready' : 'Not ready'}</strong></div>
                  <div><span>Revision</span><strong className="lite-mono-value">{data?.active_policy?.revision || 'unavailable'}</strong></div>
                </div>
                {data?.degraded_reason ? <p>Reason code: <code>{data.degraded_reason}</code></p> : null}
              </div>
            ) : null}
          </details>
        </GlassCard>
      ) : null}

      {!loading && data ? (
        <GlassCard className="lite-rules-card mt-5">
          <div className="lite-rules-card-head"><div className="lite-rules-mini-icon"><FileCheck className="h-5 w-5" /></div><span className="lite-rules-soft-badge">Recent activity</span></div>
          <h2>Recent protected decisions</h2>
          <p>Only bounded metadata is shown. Raw policy input is not exposed; credentials, authenticator data and command payloads remain hidden.</p>
          <div className="lite-rules-decision-list">
            {recent.length ? recent.map((decision) => {
              const reason = getLiteReasonPresentation(decision.reason_code, decision.reason_code || 'Decision recorded');
              return (
                <div key={decision.decision_id} className="lite-rules-decision-row lite-rules-personal-decision">
                  <StatusBadge status={decision.allow ? 'healthy' : 'degraded'}>{decision.allow ? 'Allowed' : 'Blocked'}</StatusBadge>
                  <div><strong>{actionLabel(decision.action_id)}</strong><span>{decision.target_type}: {decision.target_id}</span><small>{reason.title}</small></div>
                  <div className="lite-rules-decision-meta"><span>{decision.occurred_at ? formatLiteTime(decision.occurred_at) : 'Recent'}</span></div>
                </div>
              );
            }) : <StateSurface tone="neutral" title="No protected decisions yet" description="A decision will appear after a protected app install, device removal, or passkey removal is evaluated." />}
          </div>
        </GlassCard>
      ) : null}

      {enterpriseEnabled ? (
        <div className="mt-6">
          <LiteRulesEnterprise role={enterprise.data?.current_membership?.role || ''} />
        </div>
      ) : null}
    </>
  );
}