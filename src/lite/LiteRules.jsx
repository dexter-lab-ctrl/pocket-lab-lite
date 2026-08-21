import './identityRules.css';
import React, { useState } from 'react';
import { FileCheck, ShieldCheck } from 'lucide-react';
import { useLiteResource } from '../hooks/useLiteStatus.js';
import { formatLiteTime, liteApi } from '../lib/liteApi.js';
import {
  GlassCard,
  StatusBadge,
  StateSurface,
  PageHeader,
  LiteButton,
  LiteRefreshButton,
  LoadingCard,
} from './LiteUi.jsx';

export default function RulesScreen() {
  const { data, loading, error, refresh, cacheStatus, refreshing } = useLiteResource(liteApi.policy, []);
  const [decisionDetail, setDecisionDetail] = useState(null);
  const [decisionError, setDecisionError] = useState('');
  const [decisionBusy, setDecisionBusy] = useState('');
  const ready = data?.status === 'ready' && data?.engine?.healthy && data?.engine?.loopback_only;
  const recent = Array.isArray(data?.recent_decisions) ? data.recent_decisions : [];
  const templates = Array.isArray(data?.templates) ? data.templates : [];

  async function openDecision(decisionId) {
    setDecisionBusy(decisionId);
    setDecisionError('');
    try {
      setDecisionDetail(await liteApi.policyDecision(decisionId));
    } catch (detailError) {
      setDecisionError(detailError?.message || 'Pocket Lab could not load that decision.');
    } finally {
      setDecisionBusy('');
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Rules"
        title="Safety Rules"
        description="Review the local policy engine, active safeguards, and bounded allow/block explanations. FastAPI remains the trust boundary and protected actions fail closed when Rules are unavailable."
        actions={<LiteRefreshButton scope="rules" refresh={refresh} cacheStatus={cacheStatus} error={error} refreshing={refreshing} />}
      />

      <section className="lite-rules-hero">
        <div className="lite-rules-hero-copy">
          <div className="lite-home-pill"><span className="lite-ready-dot" />{ready ? 'Rules ready' : 'Protected changes paused'}</div>
          <h2>{ready ? 'Safety Rules are active for protected changes.' : 'Safety Rules are not ready, so protected changes fail closed.'}</h2>
          <p>{data?.summary || 'Pocket Lab is checking its local policy engine.'}</p>
        </div>
        <div className="lite-rules-status-card">
          <div className="lite-rules-icon"><FileCheck className="h-7 w-7" /></div>
          <span>Policy engine</span>
          <strong>{ready ? 'Ready' : 'Unavailable'}</strong>
          <StatusBadge status={ready ? 'healthy' : 'degraded'}>{ready ? 'Local + fail closed' : 'Changes blocked'}</StatusBadge>
        </div>
      </section>

      {loading ? <LoadingCard label="Loading rules..." /> : null}
      {error ? <StateSurface tone="degraded" title="Rules need a moment" description={error} className="mb-5" /> : null}

      {!loading ? (
        <div className="lite-rules-grid">
          <GlassCard className="lite-rules-card">
            <div className="lite-rules-card-head"><div className="lite-rules-mini-icon"><ShieldCheck className="h-5 w-5" /></div><StatusBadge status={ready ? 'healthy' : 'degraded'}>{ready ? 'Healthy' : 'Not ready'}</StatusBadge></div>
            <h2>Policy engine</h2>
            <div className="lite-rules-facts">
              <div><span>Engine</span><strong>{data?.engine?.name || 'Open Policy Agent'}</strong></div>
              <div><span>Version</span><strong>{data?.engine?.version || 'unknown'}</strong></div>
              <div><span>Network</span><strong>{data?.engine?.loopback_only ? 'Loopback only' : 'Blocked: non-local endpoint'}</strong></div>
              <div><span>Browser access</span><strong>{data?.engine?.endpoint_exposed_to_browser ? 'Unexpected' : 'Not exposed'}</strong></div>
              <div><span>Policy package</span><strong>{data?.active_policy?.bundle_ready ? 'Ready' : 'Not ready'}</strong></div>
              <div><span>Policy revision</span><strong className="lite-mono-value">{data?.active_policy?.revision || 'unavailable'}</strong></div>
              <div><span>Last decision</span><strong>{data?.last_decision_at ? formatLiteTime(data.last_decision_at) : 'None yet'}</strong></div>
              {!ready && data?.degraded_reason ? <div><span>Reason</span><strong className="lite-mono-value">{data.degraded_reason}</strong></div> : null}
            </div>
          </GlassCard>

          <GlassCard className="lite-rules-card lite-rules-guide-card">
            <div className="lite-rules-card-head"><div className="lite-rules-mini-icon"><FileCheck className="h-5 w-5" /></div><span className="lite-rules-soft-badge">Active scope</span></div>
            <h2>Protected actions</h2>
            <p>The scope stays intentionally small. Browser-supplied identity, role, assurance or approval state is never trusted.</p>
            <div className="lite-rules-list">
              {(data?.policy_groups || []).map((group, index) => (
                <div key={group.id}><span>{index + 1}</span><p><strong>{group.label}</strong><small>{(group.actions || []).join(', ')}</small></p></div>
              ))}
            </div>
          </GlassCard>
        </div>
      ) : null}

      {!loading ? (
        <GlassCard className="lite-rules-card mt-5">
          <div className="lite-rules-card-head"><div className="lite-rules-mini-icon"><ShieldCheck className="h-5 w-5" /></div><span className="lite-rules-soft-badge">Safe templates</span></div>
          <h2>Safeguards</h2>
          <p>Lite uses server-owned safeguards, not free-form browser Rego editing. Hard FastAPI protections remain outside OPA.</p>
          <div className="lite-rules-template-grid">
            {templates.map((template) => (
              <div key={template.id} className="lite-rules-template-card">
                <div><strong>{template.label}</strong><StatusBadge status={template.status === 'active' ? 'healthy' : 'neutral'}>{template.status}</StatusBadge></div>
                <p>{template.summary}</p>
                <small>{template.enforcement}</small>
              </div>
            ))}
          </div>
        </GlassCard>
      ) : null}

      {!loading ? (
        <GlassCard className="lite-rules-card mt-5">
          <div className="lite-rules-card-head"><div className="lite-rules-mini-icon"><FileCheck className="h-5 w-5" /></div><span className="lite-rules-soft-badge">Decision evidence</span></div>
          <h2>Recent decisions</h2>
          <p>Only bounded metadata is shown. Policy input, credentials, authenticator data, command payloads and secrets stay hidden.</p>
          <div className="lite-rules-decision-list">
            {recent.length ? recent.map((decision) => (
              <div key={decision.decision_id} className="lite-rules-decision-row">
                <StatusBadge status={decision.allow ? 'healthy' : 'degraded'}>{decision.allow ? 'Allowed' : 'Blocked'}</StatusBadge>
                <div><strong>{decision.action_id}</strong><span>{decision.target_type}: {decision.target_id}</span></div>
                <div className="lite-rules-decision-meta"><span>{decision.reason_code}</span><small>{formatLiteTime(decision.occurred_at)}</small></div>
                <LiteButton variant="secondary" onClick={() => openDecision(decision.decision_id)} disabled={Boolean(decisionBusy)}>{decisionBusy === decision.decision_id ? 'Loading...' : 'Explain'}</LiteButton>
              </div>
            )) : <StateSurface tone="neutral" title="No policy decisions yet" description="A decision will appear after a protected app install, device removal, or passkey removal is evaluated." />}
          </div>
          {decisionError ? <StateSurface tone="degraded" title="Decision unavailable" description={decisionError} className="mt-4" /> : null}
          {decisionDetail ? (
            <div className="lite-rules-decision-detail mt-4">
              <div className="lite-rules-card-head"><strong>Decision explanation</strong><LiteButton variant="secondary" onClick={() => setDecisionDetail(null)}>Close</LiteButton></div>
              <div className="lite-rules-facts">
                <div><span>Result</span><strong>{decisionDetail.allow ? 'Allowed' : 'Blocked'}</strong></div>
                <div><span>Reason</span><strong>{decisionDetail.reason_code}</strong></div>
                <div><span>Action</span><strong>{decisionDetail.action_id}</strong></div>
                <div><span>Target</span><strong>{decisionDetail.target_type}: {decisionDetail.target_id}</strong></div>
                <div><span>Policy revision</span><strong className="lite-mono-value">{decisionDetail.policy_revision}</strong></div>
                <div><span>Evaluation</span><strong>{decisionDetail.evaluation_ms} ms</strong></div>
                <div><span>Correlation</span><strong className="lite-mono-value">{decisionDetail.correlation_id}</strong></div>
                <div><span>Constraints</span><strong>{(decisionDetail.constraints || []).join(', ') || 'None'}</strong></div>
              </div>
              <p className="mt-3">Raw policy input is not exposed by this API.</p>
            </div>
          ) : null}
        </GlassCard>
      ) : null}
    </>
  );
}
