import './identityRules.css';
import React, { useEffect, useState } from 'react';
import { FileCheck, ShieldCheck } from 'lucide-react';
import { useLiteResource } from '../hooks/useLiteStatus.js';
import { formatLiteTime, liteApi } from '../lib/liteApi.js';
import { getLitePasskey } from '../lib/liteWebAuthn.js';
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
  const [simulation, setSimulation] = useState({ revision_id: '', action_id: 'catalog.install', target_id: '', mode: 'real_derived', scenario: {} });
  const [simulationResult, setSimulationResult] = useState(null);
  const [simulationError, setSimulationError] = useState('');
  const [simulationBusy, setSimulationBusy] = useState(false);
  const [decisionFilter, setDecisionFilter] = useState('');
  const enterprise = useLiteResource(liteApi.enterpriseIdentity, []);
  const enterpriseEnabled = Boolean(enterprise.data?.enabled);
  const enterpriseHealth = useLiteResource(liteApi.enterpriseRulesHealth, [], { enabled: enterpriseEnabled });
  const enterpriseAnalysis = useLiteResource(liteApi.enterpriseRulesAnalysis, [], { enabled: enterpriseEnabled });
  const enterpriseRevisions = useLiteResource(liteApi.enterpriseRuleRevisions, [], { enabled: enterpriseEnabled });
  const enterpriseDecisions = useLiteResource(() => liteApi.enterpriseRuleDecisions(decisionFilter), [decisionFilter], { enabled: enterpriseEnabled });
  const enterpriseApprovals = useLiteResource(liteApi.enterpriseRuleApprovals, [], { enabled: enterpriseEnabled });
  const enterpriseExceptions = useLiteResource(liteApi.enterpriseRuleExceptions, [], { enabled: enterpriseEnabled });
  const [continuationBusy, setContinuationBusy] = useState('');
  const [continuationError, setContinuationError] = useState('');
  const [exceptionDraft, setExceptionDraft] = useState({ app_id: '', device_id: '', human_id: '', reason: '', duration_minutes: 15 });
  const [approvalDetail, setApprovalDetail] = useState(null);
  useEffect(() => {
    const firstRevision = enterpriseRevisions.data?.revisions?.[0]?.revision_id;
    if (firstRevision && !simulation.revision_id) setSimulation((value) => ({ ...value, revision_id: firstRevision }));
  }, [enterpriseRevisions.data, simulation.revision_id]);
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

  async function runSimulation(event) {
    event.preventDefault();
    setSimulationBusy(true); setSimulationError(''); setSimulationResult(null);
    try {
      setSimulationResult(await liteApi.simulateEnterpriseRule({ ...simulation, scenario: simulation.mode === 'synthetic' ? simulation.scenario : undefined }));
    } catch (simulationFailure) {
      setSimulationError(simulationFailure?.message || 'Simulation is unavailable. No changes were made.');
    } finally { setSimulationBusy(false); }
  }

  async function transitionApproval(approvalId, action) {
    setContinuationBusy(`${approvalId}:${action}`); setContinuationError('');
    try {
      try {
        await liteApi.transitionEnterpriseRuleApproval(approvalId, action);
      } catch (failure) {
        const reason = failure?.payload?.detail?.reason_code || failure?.payload?.reason_code || '';
        if (action !== 'approve' || (failure?.status !== 428 && reason !== 'approval_step_up_required')) throw failure;
        const purpose = 'policy.approval.device.remove';
        const options = await liteApi.passkeyStepUpOptions(purpose);
        const credential = await getLitePasskey(options);
        await liteApi.verifyPasskeyStepUp({ purpose, challenge: options.publicKey.challenge, credential });
        await liteApi.transitionEnterpriseRuleApproval(approvalId, action);
      }
      await enterpriseApprovals.refresh();
    } catch (failure) {
      setContinuationError(failure?.message || 'Approval update is unavailable. No device removal started.');
    } finally { setContinuationBusy(''); }
  }

  async function openApproval(approvalId) {
    setContinuationBusy(`${approvalId}:detail`); setContinuationError('');
    try { setApprovalDetail(await liteApi.enterpriseRuleApproval(approvalId)); }
    catch (failure) { setContinuationError(failure?.message || 'Approval history is unavailable.'); }
    finally { setContinuationBusy(''); }
  }

  async function revokeException(exceptionId) {
    setContinuationBusy(`${exceptionId}:revoke`); setContinuationError('');
    try {
      await liteApi.revokeEnterpriseRuleException(exceptionId);
      await enterpriseExceptions.refresh();
    } catch (failure) {
      setContinuationError(failure?.message || 'Exception revocation is unavailable.');
    } finally { setContinuationBusy(''); }
  }

  async function createException(event) {
    event.preventDefault(); setContinuationBusy('exception:create'); setContinuationError('');
    try {
      await liteApi.createEnterpriseRuleException({ ...exceptionDraft, duration_minutes: Number(exceptionDraft.duration_minutes) });
      setExceptionDraft({ app_id: '', device_id: '', human_id: '', reason: '', duration_minutes: 15 });
      await enterpriseExceptions.refresh();
    } catch (failure) {
      setContinuationError(failure?.message || 'Exception creation is unavailable. No policy was broadened.');
    } finally { setContinuationBusy(''); }
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

      {enterpriseEnabled ? (
        <section className="mt-5" aria-label="Enterprise Rules">
          <PageHeader eyebrow="Enterprise Rules" title="Policy health, simulation and evidence" description="Simulation only — no changes will be made. Results use server-derived facts unless labelled synthetic." />
          {enterpriseHealth.loading ? <LoadingCard label="Loading Enterprise Rules health..." /> : null}
          {enterpriseHealth.error ? <StateSurface tone="degraded" title="Enterprise Rules unavailable" description={enterpriseHealth.error} /> : null}
          {enterpriseHealth.data ? <div className="lite-rules-grid"><GlassCard className="lite-rules-card"><h2>Policy health</h2><StatusBadge status={enterpriseHealth.data.consistency_state === 'ready' ? 'healthy' : 'degraded'}>{enterpriseHealth.data.consistency_state || 'unavailable'}</StatusBadge><div className="lite-rules-facts mt-3"><div><span>Active</span><strong className="lite-mono-value">{enterpriseHealth.data.db_active_revision || 'none'}</strong></div><div><span>Known good</span><strong className="lite-mono-value">{enterpriseHealth.data.known_good_revision || 'none'}</strong></div><div><span>OPA observed</span><strong className="lite-mono-value">{enterpriseHealth.data.opa_observed_revision || 'unavailable'}</strong></div><div><span>Activation</span><strong>{enterpriseHealth.data.activation_operation_state || 'none'}</strong></div><div><span>Analysis</span><strong>{enterpriseHealth.data.analysis_status || 'inconclusive'}</strong></div></div>{enterpriseHealth.data.degraded_reason ? <p className="mt-3">{enterpriseHealth.data.degraded_reason}</p> : null}</GlassCard><GlassCard className="lite-rules-card"><h2>Deterministic analysis</h2><p>{enterpriseAnalysis.data?.proof_rule || 'Analysis is loading.'}</p><div className="lite-rules-facts"><div><span>Registered actions</span><strong>{(enterpriseAnalysis.data?.registered_protected_actions || []).length}</strong></div><div><span>Represented</span><strong>{(enterpriseAnalysis.data?.represented_actions || []).length}</strong></div><div><span>Unmapped</span><strong>{(enterpriseAnalysis.data?.unmapped_actions || []).length}</strong></div></div><p className="mt-3">Not deterministically provable with the current template model: {(enterpriseAnalysis.data?.unsupported_categories || []).join(', ') || 'none'}.</p></GlassCard></div> : null}

          <GlassCard className="lite-rules-card mt-5"><h2>Simulate</h2><p><strong>Simulation only — no changes will be made.</strong> Raw policy input is never shown.</p><form onSubmit={runSimulation} className="lite-rules-facts"><label><span>Revision</span><select value={simulation.revision_id} onChange={(event) => setSimulation((value) => ({ ...value, revision_id: event.target.value }))}>{(enterpriseRevisions.data?.revisions || []).map((revision) => <option key={revision.revision_id} value={revision.revision_id}>{revision.revision_id}</option>)}</select></label><label><span>Action</span><select value={simulation.action_id} onChange={(event) => setSimulation((value) => ({ ...value, action_id: event.target.value }))}>{(enterpriseHealth.data?.registered_protected_actions || []).map((action) => <option key={action} value={action}>{action}</option>)}</select></label><label><span>Target reference</span><input required value={simulation.target_id} onChange={(event) => setSimulation((value) => ({ ...value, target_id: event.target.value }))} /></label><label><span>Input mode</span><select value={simulation.mode} onChange={(event) => setSimulation((value) => ({ ...value, mode: event.target.value }))}><option value="real_derived">Real-derived</option><option value="synthetic">Synthetic scenario</option></select></label>{simulation.mode === 'synthetic' ? <label><span>Synthetic confirmation</span><select value={String(Boolean(simulation.scenario.confirmed))} onChange={(event) => setSimulation((value) => ({ ...value, scenario: { confirmed: event.target.value === 'true' } }))}><option value="false">Not confirmed</option><option value="true">Confirmed</option></select></label> : null}<LiteButton type="submit" disabled={simulationBusy || !simulation.revision_id}>{simulationBusy ? 'Simulating…' : 'Run simulation'}</LiteButton></form>{simulation.mode === 'synthetic' ? <p className="mt-3"><StatusBadge status="neutral">Synthetic scenario</StatusBadge></p> : null}{simulationError ? <StateSurface tone="degraded" title="Simulation unavailable" description={simulationError} className="mt-3" /> : null}{simulationResult ? <StateSurface tone={simulationResult.outcome === 'allow' ? 'healthy' : 'degraded'} title={simulationResult.outcome === 'step_up_required' ? 'Step-up required' : simulationResult.outcome} description={`${simulationResult.reason_code} · ${simulationResult.policy_revision}`} className="mt-3" /> : null}</GlassCard>

          <GlassCard className="lite-rules-card mt-5"><h2>Decision explorer</h2><label><span>Action filter</span><input value={decisionFilter} onChange={(event) => setDecisionFilter(event.target.value ? `action_id=${encodeURIComponent(event.target.value)}` : '')} placeholder="catalog.install" /></label><div className="lite-rules-decision-list mt-3">{(enterpriseDecisions.data?.decisions || []).map((decision) => <div key={decision.decision_id} className="lite-rules-decision-row"><StatusBadge status={decision.allow ? 'healthy' : 'degraded'}>{decision.allow ? 'Allowed' : 'Blocked'}</StatusBadge><div><strong>{decision.action_id}</strong><span>{decision.target_type}: {decision.target_id}</span></div><div className="lite-rules-decision-meta"><span>{decision.reason_code}</span><small>{decision.evaluation_ms} ms</small></div><LiteButton variant="secondary" onClick={() => openDecision(decision.decision_id)}>Detail</LiteButton></div>)}</div></GlassCard>

          <GlassCard className="lite-rules-card mt-5"><h2>Independent approvals</h2><p>Enterprise device removals never execute from an approval click. A distinct active Owner or Admin must complete purpose-bound passkey step-up, then the requester retries the original removal.</p>{enterpriseApprovals.loading ? <LoadingCard label="Loading approvals..." /> : null}<div className="lite-rules-decision-list mt-3">{(enterpriseApprovals.data?.approvals || []).map((approval) => <div key={approval.approval_id} className="lite-rules-decision-row"><StatusBadge status={approval.status === 'approved' ? 'healthy' : approval.status === 'pending' ? 'neutral' : 'degraded'}>{approval.status}</StatusBadge><div><strong>{approval.action_id}</strong><span>Device: {approval.target_id} · requested {formatLiteTime(approval.created_at)} · expires {formatLiteTime(approval.expires_at)}</span></div><div className="lite-rules-decision-meta"><span>{approval.required_assurance}</span><small>{approval.policy_revision}</small></div><LiteButton variant="secondary" onClick={() => openApproval(approval.approval_id)} disabled={Boolean(continuationBusy)}>History</LiteButton>{approval.status === 'pending' ? <div className="flex gap-2"><LiteButton variant="secondary" onClick={() => transitionApproval(approval.approval_id, 'approve')} disabled={Boolean(continuationBusy)}>Approve after passkey step-up</LiteButton><LiteButton variant="secondary" onClick={() => transitionApproval(approval.approval_id, 'reject')} disabled={Boolean(continuationBusy)}>Reject</LiteButton><LiteButton variant="secondary" onClick={() => transitionApproval(approval.approval_id, 'cancel')} disabled={Boolean(continuationBusy)}>Cancel request</LiteButton></div> : null}</div>)}</div>{approvalDetail ? <StateSurface tone="neutral" title="Approval history" description={(approvalDetail.history || []).map((entry) => `${entry.event_type}: ${entry.summary}`).join(' · ') || 'No approval history is available.'} className="mt-3" /> : null}{!(enterpriseApprovals.data?.approvals || []).length && !enterpriseApprovals.loading ? <StateSurface tone="neutral" title="No independent approvals" description="A qualifying Enterprise device-removal request will create a short-lived, reviewable approval here." /> : null}</GlassCard>

          <GlassCard className="lite-rules-card mt-5"><h2>Temporary exceptions</h2><p>Exceptions are exact-scope and expire server-side within 60 minutes. They cannot bypass hard device-retirement safeguards or broaden access.</p><form onSubmit={createException} className="lite-rules-facts mt-3"><label><span>App ID</span><input required value={exceptionDraft.app_id} onChange={(event) => setExceptionDraft((value) => ({ ...value, app_id: event.target.value }))} /></label><label><span>Target device ID</span><input required value={exceptionDraft.device_id} onChange={(event) => setExceptionDraft((value) => ({ ...value, device_id: event.target.value }))} /></label><label><span>Requesting identity ID</span><input required value={exceptionDraft.human_id} onChange={(event) => setExceptionDraft((value) => ({ ...value, human_id: event.target.value }))} /></label><label><span>Expires in minutes</span><input required type="number" min="1" max="60" value={exceptionDraft.duration_minutes} onChange={(event) => setExceptionDraft((value) => ({ ...value, duration_minutes: event.target.value }))} /></label><label><span>Reason</span><input required maxLength="240" value={exceptionDraft.reason} onChange={(event) => setExceptionDraft((value) => ({ ...value, reason: event.target.value }))} /></label><LiteButton type="submit" disabled={Boolean(continuationBusy)}>Create exact exception</LiteButton></form><div className="lite-rules-decision-list mt-3">{(enterpriseExceptions.data?.exceptions || []).map((exception) => <div key={exception.exception_id} className="lite-rules-decision-row"><StatusBadge status={exception.status === 'active' ? 'healthy' : 'neutral'}>{exception.status}</StatusBadge><div><strong>{exception.action_id}</strong><span>{exception.app_id} on {exception.device_id} · expires {formatLiteTime(exception.expires_at)}</span></div><div className="lite-rules-decision-meta"><span>{exception.reason}</span><small>{exception.policy_revision}</small></div>{exception.status === 'active' ? <LiteButton variant="secondary" onClick={() => revokeException(exception.exception_id)} disabled={Boolean(continuationBusy)}>Revoke</LiteButton> : null}</div>)}</div>{!(enterpriseExceptions.data?.exceptions || []).length && !enterpriseExceptions.loading ? <StateSurface tone="neutral" title="No temporary exceptions" description="Only active Enterprise Owners and Admins can create exact app, device, identity, revision and expiry-scoped exceptions here." /> : null}{continuationError ? <StateSurface tone="degraded" title="Rules continuation unavailable" description={continuationError} className="mt-3" /> : null}</GlassCard>
        </section>
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
