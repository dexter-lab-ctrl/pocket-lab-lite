import React, { useEffect, useMemo, useState } from 'react';
import { Activity, FileSearch, FlaskConical, HeartPulse, History, ShieldCheck, TimerReset } from 'lucide-react';
import { useLiteResource } from '../hooks/useLiteStatus.js';
import { formatLiteTime, liteApi } from '../lib/liteApi.js';
import { getLitePasskey } from '../lib/liteWebAuthn.js';
import {
  getApprovalPresentation,
  buildLiteEnterpriseRulesOverview,
  getLiteReasonPresentation,
  getLiteRulesActionLabel,
  getLiteStatusPresentation,
  shortRevision,
} from '../lib/identityRulesPresentation.js';
import {
  GlassCard,
  LiteButton,
  LoadingCard,
  StateSurface,
  StatusBadge,
  LiteOperationalStory,
  copyTextToClipboard,
} from './LiteUi.jsx';

const SECTIONS = [
  ['active', 'Protection'],
  ['simulate', 'Test a change'],
  ['decisions', 'Activity'],
  ['approvals', 'Requests'],
  ['exceptions', 'Temporary access'],
];
const SIMULATE_ROLES = new Set(['Owner', 'Admin', 'Operator']);
const ANALYSIS_ROLES = new Set(['Owner', 'Admin', 'Auditor']);
const EXCEPTION_READ_ROLES = new Set(['Owner', 'Admin', 'Auditor']);
const EXCEPTION_WRITE_ROLES = new Set(['Owner', 'Admin']);

function RevisionValue({ value, label }) {
  if (!value) return <span>Unavailable</span>;
  return (
    <span className="lite-rules-revision-value">
      <code title={value}>{shortRevision(value)}</code>
      <button type="button" onClick={() => copyTextToClipboard(value)} aria-label={`Copy ${label} revision`}>Copy</button>
    </span>
  );
}

function RoleUnavailable({ title, role, description }) {
  return <StateSurface tone="neutral" title={title} description={description || `${role || 'Your current role'} does not have access to this Enterprise Rules action.`} />;
}

function SimulationResult({ result }) {
  if (!result) return null;
  const reason = getLiteReasonPresentation(result.reason_code, result.reason_code || 'Simulation completed.');
  const allowed = result.outcome === 'allow';
  const title = allowed ? 'Allowed in this simulation' : result.outcome === 'step_up_required' ? 'Passkey confirmation required' : 'Blocked in this simulation';
  return (
    <div className="lite-rules-simulation-result" role="status" aria-live="polite">
      <StateSurface tone={allowed ? 'healthy' : result.outcome === 'step_up_required' ? 'neutral' : 'degraded'} title={title} description={reason.message} />
      <dl className="lite-rules-detail-list">
        <div><dt>Outcome</dt><dd>{allowed ? 'Allow' : result.outcome === 'step_up_required' ? 'Step-up required' : 'Block'}</dd></div>
        <div><dt>Constraints</dt><dd>{(result.constraints || []).join(', ') || 'None returned'}</dd></div>
        <div><dt>Required assurance</dt><dd>{result.required_assurance || 'None'}</dd></div>
        <div><dt>Required role</dt><dd>{result.required_role || 'No additional role returned'}</dd></div>
        <div><dt>Rules revision</dt><dd><RevisionValue value={result.policy_revision} label="evaluated" /></dd></div>
        <div><dt>Evaluated</dt><dd>{result.evaluated_at ? formatLiteTime(result.evaluated_at) : 'Just now'}</dd></div>
      </dl>
      <details className="lite-rules-advanced-details"><summary>Technical reason</summary><code>{result.reason_code || 'none'}</code></details>
    </div>
  );
}

export default function LiteRulesEnterprise({ role = '' }) {
  const canSimulate = SIMULATE_ROLES.has(role);
  const canAnalyze = ANALYSIS_ROLES.has(role);
  const canReadExceptions = EXCEPTION_READ_ROLES.has(role);
  const canWriteExceptions = EXCEPTION_WRITE_ROLES.has(role);
  const [section, setSection] = useState('active');
  const [decisionFilter, setDecisionFilter] = useState('');
  const [decisionDetail, setDecisionDetail] = useState(null);
  const [approvalDetail, setApprovalDetail] = useState(null);
  const [detailBusy, setDetailBusy] = useState('');
  const [continuationBusy, setContinuationBusy] = useState('');
  const [continuationNotice, setContinuationNotice] = useState(null);
  const [simulationBusy, setSimulationBusy] = useState(false);
  const [simulationError, setSimulationError] = useState(null);
  const [simulationResult, setSimulationResult] = useState(null);
  const [simulation, setSimulation] = useState({
    revision_id: '', action_id: 'catalog.install', target_id: '', mode: 'real_derived',
    scenario: { confirmed: false, revision_validated: false, protected_server_host: false, assurance_recent: false },
  });
  const [exceptionDraft, setExceptionDraft] = useState({ app_id: 'photoprism', device_id: '', human_id: '', reason: '', duration_minutes: 15 });

  const health = useLiteResource(liteApi.enterpriseRulesHealth, []);
  const analysis = useLiteResource(liteApi.enterpriseRulesAnalysis, [], { enabled: canAnalyze });
  const revisions = useLiteResource(liteApi.enterpriseRuleRevisions, []);
  const decisions = useLiteResource(() => liteApi.enterpriseRuleDecisions(decisionFilter), [decisionFilter]);
  const approvals = useLiteResource(liteApi.enterpriseRuleApprovals, []);
  const exceptions = useLiteResource(liteApi.enterpriseRuleExceptions, [], { enabled: canReadExceptions });
  const fleet = useLiteResource(liteApi.fleet, [], { enabled: section === 'exceptions' && canWriteExceptions });

  const rulesReady = health.data?.consistency_state === 'ready';
  const enterpriseReadOnly = health.savedStateOnly || !health.backendReachable;
  const activeRevision = health.data?.db_active_revision || '';
  const knownGoodRevision = health.data?.known_good_revision || '';
  const people = exceptions.data?.eligible_people || [];
  const devices = useMemo(() => (fleet.data?.devices || []).filter((device) => device?.device_id && !device?.protected_server_host), [fleet.data]);
  const enterpriseOverview = useMemo(() => buildLiteEnterpriseRulesOverview({
    health: health.data,
    approvals: approvals.data?.approvals || [],
    exceptions: exceptions.data?.exceptions || [],
  }), [health.data, approvals.data, exceptions.data]);

  useEffect(() => {
    const firstRevision = revisions.data?.revisions?.find((revision) => revision.revision_id === activeRevision)?.revision_id || revisions.data?.revisions?.[0]?.revision_id;
    if (firstRevision && !simulation.revision_id) setSimulation((value) => ({ ...value, revision_id: firstRevision }));
  }, [activeRevision, revisions.data, simulation.revision_id]);
  useEffect(() => {
    if (!exceptionDraft.human_id && people[0]?.human_id) setExceptionDraft((value) => ({ ...value, human_id: people[0].human_id }));
  }, [exceptionDraft.human_id, people]);
  useEffect(() => {
    if (!exceptionDraft.device_id && devices[0]?.device_id) setExceptionDraft((value) => ({ ...value, device_id: devices[0].device_id }));
  }, [devices, exceptionDraft.device_id]);

  async function runSimulation(event) {
    event.preventDefault();
    setSimulationBusy(true); setSimulationError(null); setSimulationResult(null);
    try {
      setSimulationResult(await liteApi.simulateEnterpriseRule({
        revision_id: simulation.revision_id,
        action_id: simulation.action_id,
        target_id: simulation.target_id,
        mode: simulation.mode,
        scenario: simulation.mode === 'synthetic' ? simulation.scenario : undefined,
      }));
    } catch (error) {
      const code = error?.payload?.detail?.reason_code || error?.payload?.reason_code || '';
      setSimulationError(getLiteReasonPresentation(code, error?.message || 'Simulation is unavailable. No changes were made.'));
    } finally { setSimulationBusy(false); }
  }

  async function openDecision(decisionId) {
    setDetailBusy(`decision:${decisionId}`);
    try { setDecisionDetail(await liteApi.enterpriseRuleDecision(decisionId)); }
    catch (error) { setContinuationNotice({ error: true, ...getLiteReasonPresentation(error?.payload?.detail?.reason_code, error?.message || 'Decision details are unavailable.') }); }
    finally { setDetailBusy(''); }
  }

  async function openApproval(approvalId) {
    setDetailBusy(`approval:${approvalId}`);
    try { setApprovalDetail(await liteApi.enterpriseRuleApproval(approvalId)); }
    catch (error) { setContinuationNotice({ error: true, ...getLiteReasonPresentation(error?.payload?.detail?.reason_code, error?.message || 'Approval history is unavailable.') }); }
    finally { setDetailBusy(''); }
  }

  async function transitionApproval(approval, action) {
    setContinuationBusy(`${approval.approval_id}:${action}`);
    setContinuationNotice({ title: 'Waiting for Pocket Lab', message: 'No device removal starts from this approval action.' });
    try {
      try { await liteApi.transitionEnterpriseRuleApproval(approval.approval_id, action); }
      catch (error) {
        const reason = error?.payload?.detail?.reason_code || error?.payload?.reason_code || '';
        if (action !== 'approve' || (error?.status !== 428 && reason !== 'approval_step_up_required')) throw error;
        setContinuationNotice({ title: 'Confirm with your passkey', message: 'Passkey confirmation is required before the server can approve this request.' });
        const purpose = 'policy.approval.device.remove';
        const options = await liteApi.passkeyStepUpOptions(purpose);
        const credential = await getLitePasskey(options);
        await liteApi.verifyPasskeyStepUp({ purpose, challenge: options.publicKey.challenge, credential });
        await liteApi.transitionEnterpriseRuleApproval(approval.approval_id, action);
      }
      setContinuationNotice({ title: 'Verifying approval state', message: 'The server accepted the transition. Refreshing current approval truth.' });
      await approvals.refresh();
      setContinuationNotice({ title: 'Approval state updated', message: action === 'approve' ? 'Approved. The requester must retry the exact protected action to continue.' : action === 'reject' ? 'The request was rejected.' : 'The request was cancelled.' });
    } catch (error) {
      const code = error?.payload?.detail?.reason_code || error?.payload?.reason_code || '';
      setContinuationNotice({ error: true, ...getLiteReasonPresentation(code, error?.message || 'Approval update is unavailable. No device removal started.') });
    } finally { setContinuationBusy(''); }
  }

  async function createException(event) {
    event.preventDefault(); setContinuationBusy('exception:create');
    setContinuationNotice({ title: 'Waiting for Pocket Lab', message: 'The exception is not active until the server validates its exact scope.' });
    try {
      await liteApi.createEnterpriseRuleException({ ...exceptionDraft, duration_minutes: Number(exceptionDraft.duration_minutes) });
      setContinuationNotice({ title: 'Verifying exception', message: 'The server accepted the bounded exception. Refreshing its status.' });
      await exceptions.refresh();
      setContinuationNotice({ title: 'Temporary exception active', message: 'The exception is narrow, revision-bound and will expire automatically.' });
      setExceptionDraft((value) => ({ ...value, reason: '' }));
    } catch (error) {
      const code = error?.payload?.detail?.reason_code || error?.payload?.reason_code || '';
      setContinuationNotice({ error: true, ...getLiteReasonPresentation(code, error?.message || 'Exception creation is unavailable. No policy was broadened.') });
    } finally { setContinuationBusy(''); }
  }

  async function revokeException(exceptionId) {
    setContinuationBusy(`${exceptionId}:revoke`);
    try {
      await liteApi.revokeEnterpriseRuleException(exceptionId); await exceptions.refresh();
      setContinuationNotice({ title: 'Exception revoked', message: 'The server confirmed this temporary exception is no longer active.' });
    } catch (error) {
      const code = error?.payload?.detail?.reason_code || error?.payload?.reason_code || '';
      setContinuationNotice({ error: true, ...getLiteReasonPresentation(code, error?.message || 'Exception revocation is unavailable.') });
    } finally { setContinuationBusy(''); }
  }

  return (
    <section className="lite-rules-enterprise" aria-labelledby="enterprise-rules-heading">
      <div className="lite-rules-enterprise-head">
        <div><span>Enterprise Mode</span><h2 id="enterprise-rules-heading">Rules governance</h2><p>Advanced capabilities stay organized by purpose and respect the current server-resolved {role || 'Enterprise'} role.</p></div>
        <StatusBadge status={rulesReady ? 'healthy' : 'degraded'}>{rulesReady ? 'Rules ready' : 'Needs attention'}</StatusBadge>
      </div>
      <LiteOperationalStory
        className="lite-rules-enterprise-story"
        story={enterpriseOverview.workspaceStory}
        primaryAction={enterpriseOverview.workspaceStory.nextAction?.id === 'requests' ? { label: 'Review requests', onClick: () => setSection('approvals') } : enterpriseOverview.workspaceStory.nextAction?.id === 'exceptions' ? { label: 'Review temporary access', onClick: () => setSection('exceptions') } : enterpriseOverview.workspaceStory.nextAction?.id === 'protection' ? { label: 'Review Rules health', onClick: () => setSection('health') } : null}
      />
      <nav className="lite-rules-section-tabs" aria-label="Enterprise Safety Rules sections">
        {SECTIONS.map(([id, label]) => <button key={id} type="button" className={section === id ? 'is-active' : ''} aria-current={section === id ? 'page' : undefined} onClick={() => setSection(id)}>{label}</button>)}
      </nav>
      {health.loading ? <LoadingCard label="Loading Enterprise Rules..." /> : null}
      {health.error ? <StateSurface tone="degraded" title="Enterprise Rules are unavailable" description={String(health.error)} /> : null}

      {section === 'active' ? <div className="lite-rules-section-stack">
        <div className="lite-rules-posture-grid">
          <GlassCard className="lite-rules-card lite-rules-posture-card"><div className="lite-rules-card-head"><HeartPulse className="h-5 w-5" /><StatusBadge status={rulesReady ? 'healthy' : 'degraded'}>{rulesReady ? 'Ready' : 'Degraded'}</StatusBadge></div><h3>Active Rules</h3><strong>{rulesReady ? 'Protected changes are covered' : 'Protected changes remain fail-closed'}</strong><p>{rulesReady ? 'Pocket Lab proved the active, known-good and runtime-observed Rules state.' : getLiteReasonPresentation(health.data?.degraded_reason, 'Rules health needs attention.').message}</p></GlassCard>
          <GlassCard className="lite-rules-card lite-rules-posture-card"><div className="lite-rules-card-head"><ShieldCheck className="h-5 w-5" /><span className="lite-rules-soft-badge">Revision</span></div><h3>Current revision</h3><RevisionValue value={activeRevision} label="active" /><p>{activeRevision && activeRevision === knownGoodRevision ? 'Active and known-good match.' : 'Active and known-good do not currently match.'}</p></GlassCard>
          <GlassCard className="lite-rules-card lite-rules-posture-card"><div className="lite-rules-card-head"><FileSearch className="h-5 w-5" /><span className="lite-rules-soft-badge">Analysis</span></div><h3>Deterministic checks</h3><strong>{health.data?.deterministic_findings_count ?? 0} findings</strong><p>Registered protected actions are checked. The current typed model does not prove every possible rule conflict.</p></GlassCard>
        </div>
        <GlassCard className="lite-rules-card"><div className="lite-rules-card-head"><History className="h-5 w-5" /><span className="lite-rules-soft-badge">Revisions</span></div><h3>Rules revisions</h3><p>Revision IDs remain secondary evidence rather than the primary user-facing label.</p><div className="lite-rules-revision-list">{(revisions.data?.revisions || []).map((revision) => { const isActive = revision.revision_id === activeRevision; const isKnown = revision.revision_id === knownGoodRevision; const state = getLiteStatusPresentation(revision.validation_status || (isActive ? 'active' : 'inactive')); return <div key={revision.revision_id} className="lite-rules-revision-row"><div><strong>{isActive ? 'Active Rules' : isKnown ? 'Known-good Rules' : revision.summary || 'Rules revision'}</strong><span>{revision.created_at ? formatLiteTime(revision.created_at) : 'Saved revision'} · {revision.validation_status || 'validation unknown'}</span></div><div className="lite-rules-revision-tags">{isActive ? <StatusBadge status="healthy">Active</StatusBadge> : null}{isKnown ? <StatusBadge status="healthy">Known-good</StatusBadge> : null}<StatusBadge status={state.tone}>{state.label}</StatusBadge></div><RevisionValue value={revision.revision_id} label="Rules" /></div>; })}</div></GlassCard>
        <StateSurface tone="neutral" title="Analysis boundary" description="Registered protected actions are represented. Ordered-rule contradiction, shadowing, unreachable-rule, overly-broad-allow and stale-rule categories are not proved by the current typed template model." />
        <LiteButton variant="secondary" onClick={() => setSection('health')}>Health details</LiteButton>
      </div> : null}

      {section === 'simulate' ? <GlassCard className="lite-rules-card"><div className="lite-rules-card-head"><FlaskConical className="h-5 w-5" /><span className="lite-rules-soft-badge">What-if only</span></div><h3>Simulate a protected action</h3>{!canSimulate ? <RoleUnavailable title="Simulation is not available to this role" role={role} description="Owners, Admins and Operators can run bounded Rules simulations. This view never changes server authority." /> : <><StateSurface tone="neutral" title="This does not execute the action" description={simulation.mode === 'real_derived' ? 'Real-derived simulation uses server-derived identity, role and session context. The browser supplies only a bounded action and target.' : 'Synthetic simulation is hypothetical. Only the four supported boolean facts below can change.'} /><form onSubmit={runSimulation} className="lite-rules-form-grid mt-4"><label><span>Rules revision</span><select value={simulation.revision_id} onChange={(event) => setSimulation((value) => ({ ...value, revision_id: event.target.value }))}>{(revisions.data?.revisions || []).map((revision) => <option key={revision.revision_id} value={revision.revision_id}>{revision.revision_id === activeRevision ? 'Active Rules' : shortRevision(revision.revision_id)}</option>)}</select></label><label><span>Protected action</span><select value={simulation.action_id} onChange={(event) => setSimulation((value) => ({ ...value, action_id: event.target.value }))}>{(health.data?.registered_protected_actions || []).map((action) => <option key={action} value={action}>{action}</option>)}</select></label><label><span>Target reference</span><input required value={simulation.target_id} onChange={(event) => setSimulation((value) => ({ ...value, target_id: event.target.value }))} /></label><label><span>Simulation context</span><select value={simulation.mode} onChange={(event) => setSimulation((value) => ({ ...value, mode: event.target.value }))}><option value="real_derived">Real server-derived context</option><option value="synthetic">Synthetic what-if</option></select></label>{simulation.mode === 'synthetic' ? <fieldset className="lite-rules-synthetic-facts"><legend>Supported hypothetical facts</legend>{[['confirmed','Action confirmed'],['revision_validated','Target revision validated'],['protected_server_host','Target is protected server host'],['assurance_recent','Recent passkey assurance']].map(([key,label]) => <label key={key}><input type="checkbox" checked={Boolean(simulation.scenario[key])} onChange={(event) => setSimulation((value) => ({ ...value, scenario: { ...value.scenario, [key]: event.target.checked } }))} /><span>{label}</span></label>)}</fieldset> : null}<LiteButton type="submit" disabled={simulationBusy || !simulation.revision_id}>{simulationBusy ? 'Testing safely…' : 'Run simulation'}</LiteButton></form>{simulationError ? <StateSurface tone="degraded" title={simulationError.title} description={simulationError.message} className="mt-4" /> : null}<SimulationResult result={simulationResult} /></>}</GlassCard> : null}

      {section === 'decisions' ? <GlassCard className="lite-rules-card"><div className="lite-rules-card-head"><Activity className="h-5 w-5" /><span className="lite-rules-soft-badge">Sanitized evidence</span></div><h3>Decision explorer</h3>{decisions.error ? <StateSurface tone="degraded" title="Decisions are unavailable to this role" description={String(decisions.error)} /> : <><label className="lite-rules-filter-field"><span>Filter by action</span><input value={decisionFilter ? decodeURIComponent(decisionFilter.replace('action_id=', '')) : ''} onChange={(event) => setDecisionFilter(event.target.value ? `action_id=${encodeURIComponent(event.target.value)}` : '')} placeholder="catalog.install" /></label><div className="lite-rules-decision-list">{(decisions.data?.decisions || []).map((decision) => { const reason = getLiteReasonPresentation(decision.reason_code, decision.reason_code || 'Decision recorded'); return <div key={decision.decision_id} className="lite-rules-decision-row"><StatusBadge status={decision.allow ? 'healthy' : 'degraded'}>{decision.allow ? 'Allowed' : 'Blocked'}</StatusBadge><div><strong>{getLiteRulesActionLabel(decision.action_id) || 'Protected action'}</strong><span>{decision.target_type}: {decision.target_id}</span><small>{reason.title}</small></div><div className="lite-rules-decision-meta"><span>{decision.occurred_at ? formatLiteTime(decision.occurred_at) : 'Recent'}</span><small>{decision.evaluation_ms} ms</small></div><LiteButton variant="secondary" onClick={() => openDecision(decision.decision_id)} disabled={Boolean(detailBusy)}>{detailBusy === `decision:${decision.decision_id}` ? 'Loading…' : 'Details'}</LiteButton></div>; })}</div>{!(decisions.data?.decisions || []).length && !decisions.loading ? <StateSurface tone="neutral" title="No decisions match" description="Protected-action decisions appear here without raw policy input, session material or authenticator data." /> : null}{decisionDetail ? <div className="lite-rules-focus-detail"><div className="lite-rules-card-head"><strong>Decision details</strong><LiteButton variant="secondary" onClick={() => setDecisionDetail(null)}>Close</LiteButton></div><dl className="lite-rules-detail-list"><div><dt>Result</dt><dd>{decisionDetail.allow ? 'Allowed' : 'Blocked'}</dd></div><div><dt>Reason</dt><dd>{getLiteReasonPresentation(decisionDetail.reason_code).title}</dd></div><div><dt>Action</dt><dd>{getLiteRulesActionLabel(decisionDetail.action_id) || 'Protected action'}</dd></div><div><dt>Target</dt><dd>{decisionDetail.target_type}: {decisionDetail.target_id}</dd></div><div><dt>Rules revision</dt><dd><RevisionValue value={decisionDetail.policy_revision} label="decision" /></dd></div><div><dt>Evaluation</dt><dd>{decisionDetail.evaluation_ms} ms</dd></div><div><dt>Constraints</dt><dd>{(decisionDetail.constraints || []).join(', ') || 'None'}</dd></div></dl><p>Raw policy input, session material, actor identity and assurance details are intentionally omitted from this detail projection.</p><details className="lite-rules-advanced-details"><summary>Evidence reference</summary><p>Correlation: <code>{decisionDetail.correlation_id || 'unavailable'}</code></p><p>Reason code: <code>{decisionDetail.reason_code || 'none'}</code></p></details></div> : null}</>}</GlassCard> : null}

      {section === 'approvals' ? <GlassCard className="lite-rules-card"><div className="lite-rules-card-head"><ShieldCheck className="h-5 w-5" /><span className="lite-rules-soft-badge">Independent approval</span></div><h3>Device removal approvals</h3><p>Approval is exact-target, exact-Rules-revision, short-lived and one-time. Approval never removes a device by itself.</p>{approvals.error ? <StateSurface tone="degraded" title="Approvals are unavailable" description={String(approvals.error)} /> : <div className="lite-rules-decision-list">{(approvals.data?.approvals || []).map((approval) => { const presentation = getApprovalPresentation(approval); return <div key={approval.approval_id} className="lite-rules-approval-card"><div className="lite-rules-approval-head"><StatusBadge status={presentation.tone === 'blocked' ? 'degraded' : presentation.tone}>{presentation.label}</StatusBadge><strong>{approval.action_id === 'device.remove' ? 'Remove device' : approval.action_id}</strong></div><p>{presentation.guidance}</p><dl className="lite-rules-compact-meta"><div><dt>Device</dt><dd>{approval.target_id}</dd></div><div><dt>Requested</dt><dd>{formatLiteTime(approval.created_at)}</dd></div><div><dt>Expires</dt><dd>{formatLiteTime(approval.expires_at)}</dd></div></dl><div className="lite-rules-inline-actions"><LiteButton variant="secondary" onClick={() => openApproval(approval.approval_id)} disabled={Boolean(detailBusy)}>History</LiteButton>{approval.viewer_actions?.approve ? <LiteButton onClick={() => transitionApproval(approval, 'approve')} disabled={Boolean(continuationBusy) || enterpriseReadOnly}>Approve</LiteButton> : null}{approval.viewer_actions?.reject ? <LiteButton variant="secondary" onClick={() => transitionApproval(approval, 'reject')} disabled={Boolean(continuationBusy) || enterpriseReadOnly}>Reject</LiteButton> : null}{approval.viewer_actions?.cancel ? <LiteButton variant="secondary" onClick={() => transitionApproval(approval, 'cancel')} disabled={Boolean(continuationBusy) || enterpriseReadOnly}>Cancel request</LiteButton> : null}</div>{approval.status === 'pending' && approval.viewer_relationship === 'requester' && Number(approval.eligible_approver_count || 0) === 0 ? <StateSurface tone="neutral" title="Another Owner or Admin is required" description="There is currently no other active eligible approver. This is a topology limitation, not an approval failure." /> : null}<details className="lite-rules-advanced-details"><summary>Exact scope</summary><p>Rules revision: <code>{approval.policy_revision}</code></p><p>Required roles: {(approval.required_approver_roles || []).join(', ') || 'Owner, Admin'}</p><p>Required assurance: passkey confirmation</p></details></div>; })}</div>}{!(approvals.data?.approvals || []).length && !approvals.loading && !approvals.error ? <StateSurface tone="neutral" title="No independent approvals" description="A qualifying Enterprise device-removal request will create a short-lived approval here." /> : null}{approvalDetail ? <div className="lite-rules-focus-detail"><div className="lite-rules-card-head"><strong>Approval history</strong><LiteButton variant="secondary" onClick={() => setApprovalDetail(null)}>Close</LiteButton></div><ol className="lite-rules-history-list">{(approvalDetail.history || []).map((entry,index) => <li key={`${entry.occurred_at}-${index}`}><strong>{getLiteStatusPresentation(entry.event_type?.split('.').pop()).label}</strong><span>{entry.summary}</span><small>{formatLiteTime(entry.occurred_at)}</small></li>)}</ol></div> : null}</GlassCard> : null}

      {section === 'exceptions' ? <GlassCard className="lite-rules-card"><div className="lite-rules-card-head"><TimerReset className="h-5 w-5" /><span className="lite-rules-soft-badge">Temporary + narrow</span></div><h3>Temporary exceptions</h3>{!canReadExceptions ? <RoleUnavailable title="Temporary exceptions are not available to this role" role={role} description="Owners and Admins can create or revoke exact temporary exceptions. Auditors can review them. Operators and Viewers do not receive this continuation surface." /> : <><StateSurface tone="neutral" title="Expires automatically" description="Exceptions are limited to one app, one device, one active person and the current Rules revision. Wildcards and global scope remain blocked by the server." />{canWriteExceptions ? <form onSubmit={createException} className="lite-rules-form-grid mt-4"><label><span>App</span><select value={exceptionDraft.app_id} onChange={(event) => setExceptionDraft((value) => ({ ...value, app_id: event.target.value }))}><option value="photoprism">PhotoPrism</option></select></label><label><span>Device</span><select required value={exceptionDraft.device_id} onChange={(event) => setExceptionDraft((value) => ({ ...value, device_id: event.target.value }))}><option value="">Select a device</option>{devices.map((device) => <option key={device.device_id} value={device.device_id}>{device.display_name || device.name || 'Pocket Lab device'}</option>)}</select></label><label><span>Person</span><select required value={exceptionDraft.human_id} onChange={(event) => setExceptionDraft((value) => ({ ...value, human_id: event.target.value }))}><option value="">Select a person</option>{people.map((person) => <option key={person.human_id} value={person.human_id}>{person.display_name} · {person.role}</option>)}</select></label><label><span>Expires in</span><select value={String(exceptionDraft.duration_minutes)} onChange={(event) => setExceptionDraft((value) => ({ ...value, duration_minutes: Number(event.target.value) }))}><option value="5">5 minutes</option><option value="15">15 minutes</option><option value="30">30 minutes</option><option value="60">60 minutes</option></select></label><label className="lite-rules-form-wide"><span>Reason</span><input required maxLength="240" value={exceptionDraft.reason} onChange={(event) => setExceptionDraft((value) => ({ ...value, reason: event.target.value }))} /></label><LiteButton type="submit" disabled={Boolean(continuationBusy) || enterpriseReadOnly || !exceptionDraft.device_id || !exceptionDraft.human_id}>Create temporary exception</LiteButton></form> : <StateSurface tone="neutral" title="Read-only exception view" description="Auditors can review exact scope and lifecycle but cannot create or revoke temporary exceptions." className="mt-3" />}{canWriteExceptions && !people.length && !exceptions.loading ? <StateSurface tone="neutral" title="No eligible people available" description="A server-resolved active person is required before an exception can be created." className="mt-3" /> : null}<div className="lite-rules-decision-list mt-4">{(exceptions.data?.exceptions || []).map((exception) => { const status = getLiteStatusPresentation(exception.status); return <div key={exception.exception_id} className="lite-rules-exception-row"><StatusBadge status={status.tone}>{status.label}</StatusBadge><div><strong>{exception.app_id} on {exception.device_id}</strong><span>{exception.reason}</span><small>Expires {formatLiteTime(exception.expires_at)}</small></div>{canWriteExceptions && exception.status === 'active' ? <LiteButton variant="secondary" onClick={() => revokeException(exception.exception_id)} disabled={Boolean(continuationBusy) || enterpriseReadOnly}>Revoke</LiteButton> : null}<details className="lite-rules-advanced-details"><summary>Exact scope</summary><p>Action: {exception.action_id}</p><p>Rules revision: <code>{exception.policy_revision}</code></p></details></div>; })}</div>{!(exceptions.data?.exceptions || []).length && !exceptions.loading ? <StateSurface tone="neutral" title="No temporary exceptions" description="There are no active or historical temporary exceptions to show." /> : null}</>}</GlassCard> : null}

      {section === 'health' ? <div className="lite-rules-section-stack"><GlassCard className="lite-rules-card"><div className="lite-rules-card-head"><HeartPulse className="h-5 w-5" /><StatusBadge status={rulesReady ? 'healthy' : 'degraded'}>{rulesReady ? 'Ready' : 'Degraded'}</StatusBadge></div><h3>Rules health</h3><dl className="lite-rules-detail-list"><div><dt>Active Rules</dt><dd><RevisionValue value={activeRevision} label="active" /></dd></div><div><dt>Known-good Rules</dt><dd><RevisionValue value={knownGoodRevision} label="known-good" /></dd></div><div><dt>Runtime observed</dt><dd><RevisionValue value={health.data?.opa_observed_revision} label="runtime-observed" /></dd></div><div><dt>Manifest integrity</dt><dd>{health.data?.manifest_integrity ? 'Verified' : 'Needs attention'}</dd></div><div><dt>Protected-action coverage</dt><dd>{(health.data?.represented_protected_actions || []).length} of {(health.data?.registered_protected_actions || []).length}</dd></div><div><dt>Analysis</dt><dd>{health.data?.analysis_status || 'Inconclusive'}</dd></div><div><dt>Deterministic findings</dt><dd>{health.data?.deterministic_findings_count ?? 0}</dd></div><div><dt>Checked</dt><dd>{health.data?.checked_at ? formatLiteTime(health.data.checked_at) : 'Unknown'}</dd></div></dl>{rulesReady ? <StateSurface tone="healthy" title="Rules are ready" description="Active, known-good and runtime-observed state are consistent for protected actions." /> : <StateSurface tone="degraded" title={getLiteReasonPresentation(health.data?.degraded_reason, 'Safety Rules need attention').title} description={getLiteReasonPresentation(health.data?.degraded_reason, 'Safety Rules need attention').message} />}<details className="lite-rules-advanced-details"><summary>Advanced diagnostics</summary><p>Consistency state: <code>{health.data?.consistency_state || 'unknown'}</code></p><p>Activation state: <code>{health.data?.activation_operation_state || 'none'}</code></p><p>Runtime loopback configured: {health.data?.opa_loopback_configured ? 'yes' : 'no'}</p><p>Runtime reachable: {health.data?.opa_reachable ? 'yes' : 'no'}</p>{health.data?.degraded_reason ? <p>Reason code: <code>{health.data.degraded_reason}</code></p> : null}</details></GlassCard>{canAnalyze ? <GlassCard className="lite-rules-card"><div className="lite-rules-card-head"><FileSearch className="h-5 w-5" /><span className="lite-rules-soft-badge">Analysis boundary</span></div><h3>Deterministic analysis</h3><p>{analysis.data?.proof_rule || 'Analysis is loading.'}</p><dl className="lite-rules-detail-list"><div><dt>Registered actions</dt><dd>{(analysis.data?.registered_protected_actions || []).length}</dd></div><div><dt>Represented</dt><dd>{(analysis.data?.represented_actions || []).length}</dd></div><div><dt>Unmapped</dt><dd>{(analysis.data?.unmapped_actions || []).length}</dd></div></dl><StateSurface tone="neutral" title="Not all conflicts are analyzable by this model" description="The typed template model does not prove ordered-rule contradiction, shadowing, unreachable-rule, overly-broad-allow or stale-rule categories. This limitation is not itself a degraded health state." /></GlassCard> : <RoleUnavailable title="Advanced analysis is not available to this role" role={role} description="Owners, Admins and Auditors can review deterministic static-analysis details. Health remains visible without broadening role authority." />}</div> : null}

      {continuationNotice ? <div className="mt-4" role="status" aria-live="polite"><StateSurface tone={continuationNotice.error ? 'degraded' : 'neutral'} title={continuationNotice.title} description={continuationNotice.message} /></div> : null}
    </section>
  );
}
