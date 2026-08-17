import './identityRules.css';
import React from 'react';
import { FileCheck, ShieldCheck } from 'lucide-react';
import { useLiteResource } from '../hooks/useLiteStatus.js';
import { formatLiteTime, liteApi } from '../lib/liteApi.js';
import {
  GlassCard,
  StatusBadge,
  StateSurface,
  PageHeader,
  LiteRefreshButton,
  LoadingCard,
} from './LiteUi.jsx';

export default function RulesScreen() {
  const { data, loading, error, refresh, cacheStatus, refreshing } = useLiteResource(liteApi.policy, []);
  const ready = data?.status === 'ready' && data?.engine?.healthy;
  const recent = Array.isArray(data?.recent_decisions) ? data.recent_decisions : [];

  return (
    <>
      <PageHeader
        eyebrow="Rules"
        title="Safety Rules"
        description="Review the policy engine, the active repository policy, and recent allow or block decisions. Rules add protection; hard device and recovery safeguards remain enforced by FastAPI."
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
          <StatusBadge status={ready ? 'healthy' : 'degraded'}>{ready ? 'Fail-closed ready' : 'Changes blocked'}</StatusBadge>
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
              <div><span>Network</span><strong>{data?.engine?.loopback_only ? 'Local only' : 'Needs review'}</strong></div>
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
            <p>This first enforcement cut is intentionally small and testable.</p>
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
          <div className="lite-rules-card-head"><div className="lite-rules-mini-icon"><FileCheck className="h-5 w-5" /></div><span className="lite-rules-soft-badge">Decision evidence</span></div>
          <h2>Recent decisions</h2>
          <p>Only bounded metadata is shown. Policy input, credentials, command payloads, and secrets stay hidden.</p>
          <div className="lite-rules-decision-list">
            {recent.length ? recent.map((decision) => (
              <div key={decision.decision_id} className="lite-rules-decision-row">
                <StatusBadge status={decision.allow ? 'healthy' : 'degraded'}>{decision.allow ? 'Allowed' : 'Blocked'}</StatusBadge>
                <div><strong>{decision.action_id}</strong><span>{decision.target_type}: {decision.target_id}</span></div>
                <div className="lite-rules-decision-meta"><span>{decision.reason_code}</span><small>{formatLiteTime(decision.occurred_at)}</small></div>
              </div>
            )) : <StateSurface tone="neutral" title="No policy decisions yet" description="A decision will appear after a protected app install or old-device removal is evaluated." />}
          </div>
        </GlassCard>
      ) : null}
    </>
  );
}
