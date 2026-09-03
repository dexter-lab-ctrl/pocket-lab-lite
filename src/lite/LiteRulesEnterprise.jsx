import './identityRulesGovernance.css';
import React, { useEffect, useMemo, useState } from 'react';
import { Activity, FileCheck2, FileSearch, FlaskConical, HeartPulse, History, ShieldCheck, TimerReset } from 'lucide-react';
import { useLiteResource } from '../hooks/useLiteStatus.js';
import { formatLiteTime, liteApi } from '../lib/liteApi.js';
import { liteEnterpriseApi } from '../lib/liteEnterpriseApi.js';
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
import LiteHelp, { LiteHelpHeading } from './LiteHelp.jsx';

const SECTIONS = [
  ['protection', 'Protection'],
  ['policies', 'Policies'],
  ['simulate', 'Test a change'],
  ['activity', 'Activity'],
  ['requests', 'Requests'],
  ['exceptions', 'Temporary access'],
];
const EXCEPTION_READ_ROLES = new Set(['Owner', 'Admin', 'Auditor']);
const TERMINAL_ACTIVATION_STATES = new Set(['active', 'failed', 'rolled_back']);

function errorCode(error) {
  return error?.payload?.detail?.reason_code || error?.payload?.reason_code || '';
}

function RevisionValue({ value, label }) {
  if (!value) return <span>Unavailable</span>;
  return (
    <span className="lite-rules-revision-value">
      <code title={value}>{shortRevision(value)}</code>
      <button type="button" onClick={() => copyTextToClipboard(value)} aria-label={`Copy ${label} revision`}>Copy</button>
    </span>
  );
}

function RoleUnavailable({ title, description }) {
  return <StateSurface tone="neutral" title={title} description={description} />;
}

function SimulationResult({ result }) {
  if (!result) return null;
  const reason = getLiteReasonPresentation(result.reason_code, result.reason_code || 'Simulation completed.');
  const allowed = result.outcome === 'allow';
  const title = allowed ? 'Allowed in this simulation' : result.outcome === 'step_up_required' ? 'Passkey confirmation would be required' : 'Blocked in this simulation';
  return (
    <div className="lite-rules-simulation-result" role="status" aria-live="polite">
      <StateSurface tone={allowed ? 'healthy' : result.outcome === 'step_up_required' ? 'neutral' : 'degraded'} title={title} description={reason.message} />
      <dl className="lite-rules-detail-list">
        <div><dt>Outcome</dt><dd>{allowed ? 'Allow' : result.outcome === 'step_up_required' ? 'Passkey' : 'Block'}</dd></div>
        <div><dt>Constraints</dt><dd>{(result.constraints || []).join(', ') || 'None returned'}</dd></div>
        <div><dt>Rules revision</dt><dd><RevisionValue value={result.policy_revision} label="evaluated" /></dd></div>
        <div><dt>Evaluated</dt><dd>{result.evaluated_at ? formatLiteTime(result.evaluated_at) : 'Just now'}</dd></div>
      </dl>
      <details className="lite-rules-advanced-details"><summary>Technical reason</summary><code>{result.reason_code || 'none'}</code></details>
    </div>
  );
}

export default function LiteRulesEnterprise({ role: roleProp = '', access: initialAccess = null }) {
  const [section, setSection] = useState('protection');
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState('');
  const [decisionFilter, setDecisionFilter] = useState('');
  const [decisionDetail, setDecisionDetail] = useState(null);
  const [approvalDetail, setApprovalDetail] = useState(null);
  const [activation, setActivation] = useState(null);
  const [candidateRevision, setCandidateRevision] = useState('');
  const [policyDraft, setPolicyDraft] = useState({ admin_device_remove_approval: true, operator_device_remove_approval: true, change_summary: '' });
  const [simulationResult, setSimulationResult] = useState(null);
  const [simulation, setSimulation] = useState({ revision_id: '', action_id: 'catalog.install', target_id: '', mode: 'real_derived', scenario: { confirmed: false, revision_validated: false, protected_server_host: false, assurance_recent: false } });
  const [exceptionDraft, setExceptionDraft] = useState({ app_id: 'photoprism', device_id: '', human_id: '', reason: '', duration_minutes: 15 });

  const access = useLiteResource(liteEnterpriseApi.access, []);
  const health = useLiteResource(liteEnterpriseApi.rulesHealth, []);
  const templates = useLiteResource(liteEnterpriseApi.ruleTemplates, []);
  const revisions = useLiteResource(liteEnterpriseApi.ruleRevisions, []);
  const decisions = useLiteResource(() => liteEnterpriseApi.rulesDecisions(decisionFilter), [decisionFilter]);
  const approvals = useLiteResource(liteEnterpriseApi.approvals, []);
  const resolvedRole = access.data?.current_role || initialAccess?.current_role || roleProp;
  const canAnalyze = ['Owner', 'Admin', 'Auditor'].includes(resolvedRole);
  const analysis = useLiteResource(liteEnterpriseApi.rulesAnalysis, [], { enabled: canAnalyze });
  const canReadExceptions = EXCEPTION_READ_ROLES.has(resolvedRole);
  const exceptions = useLiteResource(liteEnterpriseApi.exceptions, [], { enabled: canReadExceptions });
  const fleet = useLiteResource(liteApi.fleet, [], { enabled: section === 'exceptions' && Boolean(access.data?.capabilities?.['exceptions.manage']) });

  const accessData = access.data || initialAccess || {};
  const capabilities = accessData.capabilities || {};
  const canDraft = Boolean(capabilities['rules.draft']);
  const canActivate = Boolean(capabilities['rules.activate']);
  const canRollback = Boolean(capabilities['rules.rollback']);
  const canSimulate = Boolean(capabilities['rules.simulate']);
  const canReviewRequests = Boolean(capabilities['approvals.review']);
  const canManageExceptions = Boolean(capabilities['exceptions.manage']);
  const rulesReady = health.data?.consistency_state === 'ready';
  const enterpriseReadOnly = health.savedStateOnly || !health.backendReachable;
  const activeRevision = health.data?.db_active_revision || '';
  const knownGoodRevision = health.data?.known_good_revision || '';
  const people = exceptions.data?.eligible_people || [];
  const devices = useMemo(() => (fleet.data?.devices || []).filter((device) => (device?.device_id || device?.id) && !device?.protected_server_host && device?.role !== 'server_host'), [fleet.data]);
  const enterpriseOverview = useMemo(() => buildLiteEnterpriseRulesOverview({ health: health.data, approvals: approvals.data?.approvals || [], exceptions: exceptions.data?.exceptions || [] }), [health.data, approvals.data, exceptions.data]);

  useEffect(() => {
    const params = templates.data?.effective_parameters || accessData.policy_parameters;
    if (!params) return;
    setPolicyDraft((value) => ({
      ...value,
      admin_device_remove_approval: Boolean(Number(params.admin_device_remove_approval ?? 1)),
      operator_device_remove_approval: Boolean(Number(params.operator_device_remove_approval ?? 1)),
    }));
  }, [templates.data, accessData.policy_parameters]);

  useEffect(() => {
    const firstRevision = (revisions.data?.revisions || []).find((item) => item.revision_id === activeRevision)?.revision_id || revisions.data?.revisions?.[0]?.revision_id || '';
    if (firstRevision && !simulation.revision_id) setSimulation((value) => ({ ...value, revision_id: firstRevision }));
  }, [activeRevision, revisions.data, simulation.revision_id]);

  useEffect(() => {
    if (!exceptionDraft.human_id && people[0]?.human_id) setExceptionDraft((value) => ({ ...value, human_id: people[0].human_id }));
  }, [exceptionDraft.human_id, people]);

  useEffect(() => {
    const first = devices[0];
    const id = first?.device_id || first?.id || '';
    if (!exceptionDraft.device_id && id) setExceptionDraft((value) => ({ ...value, device_id: id }));
  }, [devices, exceptionDraft.device_id]);

  async function execute(name, callback, success, refreshers = []) {
    setBusy(name);
    setNotice({ title: 'Waiting for Pocket Lab', message: 'The current Rules authority stays unchanged until the server accepts this request.' });
    try {
      const result = await callback();
      setNotice({ title: 'Server accepted', message: 'Pocket Lab accepted the request. Refreshing current governance truth.' });
      await Promise.all(refreshers.map((fn) => fn?.()).filter(Boolean));
      setNotice({ title: 'Rules updated', message: result?.summary || success });
      return result;
    } catch (error) {
      const reason = getLiteReasonPresentation(errorCode(error), error?.message || 'Pocket Lab could not complete that Rules action.');
      setNotice({ error: true, title: reason.title, message: reason.message });
      return null;
    } finally { setBusy(''); }
  }

  async function ownerStepUp(purpose, callback) {
    try { return await callback(); }
    catch (firstError) {
      if (firstError?.status !== 428 && errorCode(firstError) !== 'owner_step_up_required') throw firstError;
      setNotice({ title: 'Confirm with your passkey', message: 'Owner is root-equivalent, but this root-level Rules change still requires recent passkey confirmation.' });
      const options = await liteApi.passkeyStepUpOptions(purpose);
      const credential = await getLitePasskey(options);
      await liteApi.verifyPasskeyStepUp({ purpose, challenge: options.publicKey.challenge, credential });
      return callback();
    }
  }

  async function createPolicyRevision(event) {
    event.preventDefault();
    const result = await execute('policy:draft', () => liteEnterpriseApi.createRuleRevision({
      template_id: 'enterprise_governance',
      parameters: {
        admin_device_remove_approval: policyDraft.admin_device_remove_approval,
        operator_device_remove_approval: policyDraft.operator_device_remove_approval,
      },
      change_summary: policyDraft.change_summary,
    }), 'Rules candidate created.', [revisions.refresh]);
    if (result?.revision?.revision_id) {
      setCandidateRevision(result.revision.revision_id);
      setPolicyDraft((value) => ({ ...value, change_summary: '' }));
    }
  }

  async function activateRevision(revisionId) {
    const result = await execute(`policy:activate:${revisionId}`, () => ownerStepUp('policy.rules.activate', () => liteEnterpriseApi.activateRuleRevision(revisionId)), 'Rules activation requested.', [health.refresh, revisions.refresh]);
    if (result?.operation) setActivation(result.operation);
  }

  async function rollbackRules() {
    const result = await execute('policy:rollback', () => ownerStepUp('policy.rules.rollback', () => liteEnterpriseApi.rollbackRules()), 'Known-good Rules restoration requested.', [health.refresh, revisions.refresh]);
    if (result?.operation) setActivation(result.operation);
  }

  async function refreshActivation() {
    if (!activation?.operation_id) return;
    const result = await execute('policy:activation-refresh', () => liteEnterpriseApi.ruleActivation(activation.operation_id), 'Activation state refreshed.', [health.refresh, revisions.refresh, access.refresh, templates.refresh]);
    if (result?.operation) setActivation(result.operation);
  }

  async function resolveUncertainActivation() {
    if (!activation?.operation_id) return;
    const result = await execute('policy:resolve', () => ownerStepUp('policy.rules.activate', () => liteEnterpriseApi.resolveRuleActivation(activation.operation_id)), 'Recovered Rules state proved and recorded.', [health.refresh, revisions.refresh, access.refresh, templates.refresh]);
    if (result?.operation) setActivation(result.operation);
  }

  async function runSimulation(event) {
    event.preventDefault();
    setSimulationResult(null);
    const result = await execute('simulation', () => liteEnterpriseApi.simulateRule({ revision_id: simulation.revision_id, action_id: simulation.action_id, target_id: simulation.target_id, mode: simulation.mode, scenario: simulation.mode === 'synthetic' ? simulation.scenario : undefined }), 'Simulation completed.', []);
    if (result) setSimulationResult(result);
  }

  async function openDecision(decisionId) {
    const result = await execute(`decision:${decisionId}`, () => liteEnterpriseApi.rulesDecision(decisionId), 'Decision details loaded.', []);
    if (result) setDecisionDetail(result);
  }

  async function openApproval(approvalId) {
    const result = await execute(`approval:${approvalId}`, () => liteEnterpriseApi.approval(approvalId), 'Request history loaded.', []);
    if (result) setApprovalDetail(result);
  }

  async function transitionApproval(approval, action) {
    const result = await execute(`approval:${approval.approval_id}:${action}`, async () => {
      try { return await liteEnterpriseApi.transitionApproval(approval.approval_id, action); }
      catch (firstError) {
        if (action !== 'approve' || (firstError?.status !== 428 && errorCode(firstError) !== 'approval_step_up_required')) throw firstError;
        const purpose = 'policy.approval.device.remove';
        setNotice({ title: 'Confirm this review with your passkey', message: 'Independent approval needs recent passkey confirmation from the reviewer.' });
        const options = await liteApi.passkeyStepUpOptions(purpose);
        const credential = await getLitePasskey(options);
        await liteApi.verifyPasskeyStepUp({ purpose, challenge: options.publicKey.challenge, credential });
        return liteEnterpriseApi.transitionApproval(approval.approval_id, action);
      }
    }, action === 'approve' ? 'Request approved. The original requester must retry the exact action.' : action === 'reject' ? 'Request rejected.' : 'Request cancelled.', [approvals.refresh]);
    return result;
  }

  async function createException(event) {
    event.preventDefault();
    await execute('exception:create', () => liteEnterpriseApi.createException({ ...exceptionDraft, duration_minutes: Number(exceptionDraft.duration_minutes) }), 'Temporary access is active for the exact scope and expiry shown.', [exceptions.refresh]);
    setExceptionDraft((value) => ({ ...value, reason: '' }));
  }

  async function revokeException(exceptionId) {
    await execute(`exception:${exceptionId}:revoke`, () => liteEnterpriseApi.revokeException(exceptionId), 'Temporary access revoked.', [exceptions.refresh]);
  }

  const policyParameters = templates.data?.effective_parameters || accessData.policy_parameters || {};
  const activeOperation = activation || (health.data?.activation_operation_state ? { state: health.data.activation_operation_state } : null);

  return (
    <section className="lite-rules-enterprise lite-governance-section" aria-labelledby="enterprise-rules-heading">
      <div className="lite-rules-enterprise-head">
        <div><span>Enterprise Mode</span><h2 id="enterprise-rules-heading">Rules governance</h2><p>Protection, policy changes, requests and evidence all use the same server-resolved {resolvedRole || 'Enterprise'} authority shown in Identity & Access.</p></div>
        <div className="lite-governance-inline-actions"><StatusBadge status={rulesReady ? 'healthy' : 'degraded'}>{rulesReady ? 'Rules ready' : 'Needs attention'}</StatusBadge><LiteHelp helpKey="rules.protection" /></div>
      </div>

      {notice ? <StateSurface tone={notice.error ? 'degraded' : 'neutral'} title={notice.title} description={notice.message} className="mt-4" /> : null}

      <LiteOperationalStory
        className="lite-rules-enterprise-story"
        story={enterpriseOverview.workspaceStory}
        primaryAction={enterpriseOverview.workspaceStory.nextAction?.id === 'requests' ? { label: 'Review requests', onClick: () => setSection('requests') } : enterpriseOverview.workspaceStory.nextAction?.id === 'exceptions' ? { label: 'Review temporary access', onClick: () => setSection('exceptions') } : { label: 'Review protection', onClick: () => setSection('protection') }}
      />

      <nav className="lite-rules-section-tabs lite-governance-nav" aria-label="Enterprise Safety Rules sections">
        {SECTIONS.map(([id, label]) => <button key={id} type="button" className={section === id ? 'is-active' : ''} aria-current={section === id ? 'page' : undefined} onClick={() => setSection(id)}>{label}</button>)}
      </nav>

      {health.loading ? <LoadingCard label="Loading Enterprise Rules..." /> : null}
      {health.error ? <StateSurface tone="degraded" title="Enterprise Rules are unavailable" description={String(health.error)} /> : null}

      {section === 'protection' ? (
        <div className="lite-rules-section-stack lite-governance-stack">
          <div className="lite-rules-posture-grid lite-governance-grid">
            <GlassCard className="lite-rules-card lite-rules-posture-card"><div className="lite-rules-card-head"><HeartPulse className="h-5 w-5" /><StatusBadge status={rulesReady ? 'healthy' : 'degraded'}>{rulesReady ? 'Ready' : 'Fail closed'}</StatusBadge></div><LiteHelpHeading title="Runtime protection" helpKey="rules.protection" as="h3" /><strong>{rulesReady ? 'Protected changes are covered' : 'Protected changes remain blocked'}</strong><p>{rulesReady ? 'Pocket Lab proved the database, filesystem and running OPA revision agree.' : getLiteReasonPresentation(health.data?.degraded_reason, 'Rules consistency needs attention.').message}</p></GlassCard>
            <GlassCard className="lite-rules-card lite-rules-posture-card"><div className="lite-rules-card-head"><ShieldCheck className="h-5 w-5" /><LiteHelp helpKey="rules.owner" /></div><h3>Your authority</h3><strong>{resolvedRole || 'Unknown role'}</strong><p>{resolvedRole === 'Owner' ? 'Owner does not need another human approval. Root-level Rules changes still require passkey confirmation.' : accessData.role?.summary || 'The server resolves this role before policy evaluation.'}</p></GlassCard>
            <GlassCard className="lite-rules-card lite-rules-posture-card"><div className="lite-rules-card-head"><FileSearch className="h-5 w-5" /><span className="lite-rules-soft-badge">Current policy</span></div><h3>Active revision</h3><RevisionValue value={activeRevision} label="active" /><p>{activeRevision && activeRevision === knownGoodRevision ? 'Active and known-good match.' : 'Active and known-good do not currently match.'}</p></GlassCard>
          </div>

          <GlassCard className="lite-rules-card">
            <div className="lite-rules-card-head"><LiteHelpHeading title="What each role can do" helpKey="identity.roles" as="h3" /><StatusBadge status="healthy">Same model as Identity</StatusBadge></div>
            <p>Direct means the role may perform the supported action without another person. Review means an independent Owner/Admin continuation is required. Passkey means root-level confirmation is required.</p>
            <div className="lite-governance-matrix">
              {(accessData.action_matrix || []).map((row) => <div className="lite-governance-matrix-row" key={row.action_id}><div><strong>{row.label}</strong><div className="lite-governance-muted">{row.summary}</div></div>{['Owner','Admin','Operator','Auditor','Viewer'].map((role) => <div key={role} className="lite-governance-matrix-cell"><strong>{role}</strong><br />{row.roles?.[role] === 'allow' ? 'Direct' : row.roles?.[role] === 'approval' ? 'Review' : row.roles?.[role] === 'step_up' ? 'Passkey' : 'Blocked'}</div>)}</div>)}
            </div>
          </GlassCard>

          <GlassCard className="lite-rules-card">
            <div className="lite-rules-card-head"><History className="h-5 w-5" /><span className="lite-rules-soft-badge">Evidence</span></div><h3>Runtime facts</h3><div className="lite-rules-facts"><div><span>Consistency</span><strong>{health.data?.consistency_state || 'unknown'}</strong></div><div><span>Known-good</span><strong>{knownGoodRevision ? shortRevision(knownGoodRevision) : 'Unavailable'}</strong></div><div><span>Running OPA</span><strong>{health.data?.opa_reachable ? 'Reachable' : 'Not proved'}</strong></div><div><span>Loopback boundary</span><strong>{health.data?.opa_loopback_configured ? 'Local only' : 'Needs attention'}</strong></div><div><span>Analysis</span><strong>{health.data?.analysis_status || 'unknown'}</strong></div><div><span>Findings</span><strong>{health.data?.deterministic_findings_count ?? 0}</strong></div></div>{analysis.data ? <StateSurface tone="neutral" title="Analysis boundary" description={analysis.data.proof_rule || 'Only the deterministic categories implemented by the typed model are claimed.'} className="mt-3" /> : null}</GlassCard>
        </div>
      ) : null}

      {section === 'policies' ? (
        <div className="lite-governance-stack">
          <GlassCard className="lite-rules-card">
            <div className="lite-rules-card-head"><LiteHelpHeading title="Policy settings" helpKey="rules.policies" as="h3" /><StatusBadge status={canDraft ? 'healthy' : 'neutral'}>{canDraft ? 'Draft allowed' : 'Read only'}</StatusBadge></div>
            <p>Pocket Lab exposes typed settings only. The browser cannot submit Rego source, change OPA pointers, restart OPA, or mark a candidate active.</p>
            <div className="lite-governance-policy-controls">
              <label><input type="checkbox" checked={policyDraft.admin_device_remove_approval} onChange={(event) => setPolicyDraft((value) => ({ ...value, admin_device_remove_approval: event.target.checked }))} disabled={!canDraft || Boolean(busy)} /><span><strong>Admin device removal needs independent review</strong><small>Current: {Number(policyParameters.admin_device_remove_approval ?? 1) ? 'Review required' : 'Direct delegated authority'}</small></span></label>
              <label><input type="checkbox" checked={policyDraft.operator_device_remove_approval} onChange={(event) => setPolicyDraft((value) => ({ ...value, operator_device_remove_approval: event.target.checked }))} disabled={!canDraft || Boolean(busy)} /><span><strong>Operator device removal needs independent review</strong><small>Current: {Number(policyParameters.operator_device_remove_approval ?? 1) ? 'Review required' : 'Direct delegated authority'}</small></span></label>
            </div>
            {canDraft ? <form className="lite-governance-form mt-4" onSubmit={createPolicyRevision}><label className="lite-governance-span-2"><span>Why are you changing this?</span><textarea required maxLength="240" value={policyDraft.change_summary} onChange={(event) => setPolicyDraft((value) => ({ ...value, change_summary: event.target.value }))} placeholder="Example: Allow Admins to retire stale lab devices without peer review." /></label><div className="lite-governance-actions"><LiteButton type="submit" disabled={Boolean(busy) || !policyDraft.change_summary.trim()}>{busy === 'policy:draft' ? 'Creating candidate…' : 'Create Rules candidate'}</LiteButton></div></form> : <RoleUnavailable title="Policy editing is not available to this role" description="You can review immutable revisions and effective protection, but only Owner/Admin can create typed candidates. Only Owner can activate or restore Rules." />}
          </GlassCard>

          {candidateRevision ? <StateSurface tone="neutral" title="Candidate created — not active" description={`Candidate ${shortRevision(candidateRevision)} exists as immutable server-owned intent. It does not change running protection until an Owner confirms activation and the supervisor proves the runtime revision.`} /> : null}

          {activeOperation ? <GlassCard className="lite-rules-card"><div className="lite-rules-card-head"><FileCheck2 className="h-5 w-5" /><StatusBadge status={TERMINAL_ACTIVATION_STATES.has(activeOperation.state) ? (activeOperation.state === 'active' ? 'healthy' : 'degraded') : 'review'}>{activeOperation.state || 'Pending'}</StatusBadge></div><h3>Activation progress</h3><p>{activeOperation.state === 'active' ? 'The supervisor proved the requested revision is running and known-good.' : activeOperation.state === 'uncertain' ? 'Pocket Lab cannot prove which revision is authoritative. Protected changes remain fail-closed until recovery is proved.' : 'FastAPI recorded intent. The supervisor owns staging, pointer switching, OPA restart, proof and rollback.'}</p><div className="lite-governance-actions">{activeOperation.operation_id ? <LiteButton variant="secondary" onClick={refreshActivation} disabled={Boolean(busy)}>Refresh activation</LiteButton> : null}{activeOperation.state === 'uncertain' && canActivate ? <LiteButton onClick={resolveUncertainActivation} disabled={Boolean(busy)}>Verify recovered Rules</LiteButton> : null}</div></GlassCard> : null}

          <GlassCard className="lite-rules-card">
            <div className="lite-rules-card-head"><History className="h-5 w-5" /><span className="lite-rules-soft-badge">Immutable history</span></div><h3>Rules revisions</h3>
            <div className="lite-rules-revision-list">{(revisions.data?.revisions || []).map((revision) => { const isActive = revision.revision_id === activeRevision; const isKnown = revision.revision_id === knownGoodRevision; const state = getLiteStatusPresentation(revision.lifecycle_status || revision.validation_status); return <div key={revision.revision_id} className="lite-rules-revision-row"><div><strong>{revision.change_summary || (isActive ? 'Active Rules' : 'Rules revision')}</strong><span>{revision.created_at ? formatLiteTime(revision.created_at) : 'Saved revision'} · {revision.template_id || 'typed policy'}</span></div><div className="lite-rules-revision-tags">{isActive ? <StatusBadge status="healthy">Active</StatusBadge> : null}{isKnown ? <StatusBadge status="healthy">Known-good</StatusBadge> : null}<StatusBadge status={state.tone}>{state.label}</StatusBadge></div><RevisionValue value={revision.revision_id} label="Rules" /><div className="lite-governance-actions">{canActivate && !isActive ? <LiteButton onClick={() => activateRevision(revision.revision_id)} disabled={Boolean(busy) || enterpriseReadOnly}>Activate</LiteButton> : null}</div></div>; })}</div>
            {!(revisions.data?.revisions || []).length && !revisions.loading ? <StateSurface tone="neutral" title="No Enterprise Rules revisions yet" description="Create a typed candidate to begin governed policy history." /> : null}
            {canRollback && knownGoodRevision ? <div className="lite-governance-actions"><LiteButton variant="secondary" onClick={rollbackRules} disabled={Boolean(busy) || enterpriseReadOnly}>Restore known-good Rules</LiteButton></div> : null}
          </GlassCard>
        </div>
      ) : null}

      {section === 'simulate' ? (
        <GlassCard className="lite-rules-card">
          <div className="lite-rules-card-head"><LiteHelpHeading title="Test a change" helpKey="rules.simulation" as="h3" /><span className="lite-rules-soft-badge">What-if only</span></div>
          {!canSimulate ? <RoleUnavailable title="Simulation is not available to this role" description="This role can review current protection but cannot run a bounded policy simulation." /> : <><StateSurface tone="neutral" title="This never executes the real action" description={simulation.mode === 'real_derived' ? 'Pocket Lab derives your identity, role and session on the server. You supply only a bounded action and target.' : 'Synthetic mode changes only the four supported boolean facts shown below.'} /><form onSubmit={runSimulation} className="lite-rules-form-grid mt-4"><label><span>Rules revision</span><select value={simulation.revision_id} onChange={(event) => setSimulation((value) => ({ ...value, revision_id: event.target.value }))}>{(revisions.data?.revisions || []).map((revision) => <option key={revision.revision_id} value={revision.revision_id}>{revision.revision_id === activeRevision ? 'Active Rules' : `${revision.change_summary || 'Candidate'} · ${shortRevision(revision.revision_id)}`}</option>)}</select></label><label><span>Protected action</span><select value={simulation.action_id} onChange={(event) => setSimulation((value) => ({ ...value, action_id: event.target.value }))}>{(health.data?.registered_protected_actions || []).map((action) => <option key={action} value={action}>{getLiteRulesActionLabel(action) || action}</option>)}</select></label><label><span>Target reference</span><input required value={simulation.target_id} onChange={(event) => setSimulation((value) => ({ ...value, target_id: event.target.value }))} placeholder="device-or-app-id" /></label><label><span>Context</span><select value={simulation.mode} onChange={(event) => setSimulation((value) => ({ ...value, mode: event.target.value }))}><option value="real_derived">Real server-derived context</option><option value="synthetic">Synthetic what-if</option></select></label>{simulation.mode === 'synthetic' ? <fieldset className="lite-rules-synthetic-facts"><legend>Supported hypothetical facts</legend>{[['confirmed','Action confirmed'],['revision_validated','Target revision validated'],['protected_server_host','Target is protected Server Host'],['assurance_recent','Recent passkey assurance']].map(([key,label]) => <label key={key}><input type="checkbox" checked={Boolean(simulation.scenario[key])} onChange={(event) => setSimulation((value) => ({ ...value, scenario: { ...value.scenario, [key]: event.target.checked } }))} /><span>{label}</span></label>)}</fieldset> : null}<LiteButton type="submit" disabled={Boolean(busy) || !simulation.revision_id}>{busy === 'simulation' ? 'Testing safely…' : 'Run simulation'}</LiteButton></form><SimulationResult result={simulationResult} /></>}
        </GlassCard>
      ) : null}

      {section === 'activity' ? (
        <GlassCard className="lite-rules-card">
          <div className="lite-rules-card-head"><LiteHelpHeading title="Rules activity" helpKey="rules.decisions" as="h3" /><span className="lite-rules-soft-badge">Sanitized evidence</span></div>
          <p>A Rules decision proves policy evaluation only. It does not claim the downstream app, device or identity change completed.</p>
          <label className="lite-rules-filter-field"><span>Filter by protected action</span><input value={decisionFilter ? decodeURIComponent(decisionFilter.replace('action_id=', '')) : ''} onChange={(event) => setDecisionFilter(event.target.value ? `action_id=${encodeURIComponent(event.target.value)}` : '')} placeholder="device.remove" /></label>
          {decisions.error ? <StateSurface tone="degraded" title="Decision evidence is unavailable" description={String(decisions.error)} /> : <div className="lite-rules-decision-list">{(decisions.data?.decisions || []).map((decision) => { const reason = getLiteReasonPresentation(decision.reason_code, decision.reason_code || 'Decision recorded'); return <div key={decision.decision_id} className="lite-rules-decision-row"><StatusBadge status={decision.allow ? 'healthy' : 'degraded'}>{decision.allow ? 'Allowed' : 'Blocked'}</StatusBadge><div><strong>{getLiteRulesActionLabel(decision.action_id) || 'Protected action'}</strong><span>{decision.target_type}: {decision.target_id}</span><small>{reason.title}</small></div><div className="lite-rules-decision-meta"><span>{decision.occurred_at ? formatLiteTime(decision.occurred_at) : 'Recent'}</span><small>{decision.evaluation_ms} ms</small></div><LiteButton variant="secondary" onClick={() => openDecision(decision.decision_id)} disabled={Boolean(busy)}>Details</LiteButton></div>; })}</div>}
          {!decisions.loading && !(decisions.data?.decisions || []).length ? <StateSurface tone="neutral" title="No decisions match" description="Protected-action decisions appear here without raw session, authenticator or command material." /> : null}
          {decisionDetail ? <div className="lite-rules-focus-detail"><div className="lite-rules-card-head"><strong>Decision details</strong><LiteButton variant="secondary" onClick={() => setDecisionDetail(null)}>Close</LiteButton></div><dl className="lite-rules-detail-list"><div><dt>Result</dt><dd>{decisionDetail.allow ? 'Allowed' : 'Blocked'}</dd></div><div><dt>Reason</dt><dd>{getLiteReasonPresentation(decisionDetail.reason_code).title}</dd></div><div><dt>Action</dt><dd>{getLiteRulesActionLabel(decisionDetail.action_id) || decisionDetail.action_id}</dd></div><div><dt>Target</dt><dd>{decisionDetail.target_type}: {decisionDetail.target_id}</dd></div><div><dt>Rules revision</dt><dd><RevisionValue value={decisionDetail.policy_revision} label="decision" /></dd></div><div><dt>Constraints</dt><dd>{(decisionDetail.constraints || []).join(', ') || 'None'}</dd></div></dl><details className="lite-rules-advanced-details"><summary>Evidence reference</summary><p>Correlation: <code>{decisionDetail.correlation_id || 'unavailable'}</code></p><p>Reason code: <code>{decisionDetail.reason_code || 'none'}</code></p></details></div> : null}
        </GlassCard>
      ) : null}

      {section === 'requests' ? (
        <GlassCard className="lite-rules-card">
          <div className="lite-rules-card-head"><LiteHelpHeading title="Review requests" helpKey="rules.requests" as="h3" /><span className="lite-rules-soft-badge">Independent review</span></div>
          {resolvedRole === 'Owner' ? <StateSurface tone="healthy" title="Owner actions do not create peer-approval deadlocks" description="Owner can perform supported protected actions directly once normal hard safety checks pass. Requests shown here are for delegated Admin/Operator actions that current Rules require another eligible person to review." /> : null}
          <p>A request is exact-target, exact-Rules-revision, short-lived and one-time. Approving it never performs the original action.</p>
          {approvals.error ? <StateSurface tone="degraded" title="Requests are unavailable" description={String(approvals.error)} /> : <div className="lite-rules-decision-list">{(approvals.data?.approvals || []).map((approval) => { const presentation = getApprovalPresentation(approval); return <div key={approval.approval_id} className="lite-rules-approval-card"><div className="lite-rules-approval-head"><StatusBadge status={presentation.tone === 'blocked' ? 'degraded' : presentation.tone}>{presentation.label}</StatusBadge><strong>{approval.action_id === 'device.remove' ? 'Remove device' : approval.action_id}</strong></div><p>{presentation.guidance}</p><dl className="lite-rules-compact-meta"><div><dt>Device</dt><dd>{approval.target_id}</dd></div><div><dt>Requested</dt><dd>{formatLiteTime(approval.created_at)}</dd></div><div><dt>Expires</dt><dd>{formatLiteTime(approval.expires_at)}</dd></div></dl><div className="lite-rules-inline-actions"><LiteButton variant="secondary" onClick={() => openApproval(approval.approval_id)} disabled={Boolean(busy)}>History</LiteButton>{canReviewRequests && approval.viewer_actions?.approve ? <LiteButton onClick={() => transitionApproval(approval, 'approve')} disabled={Boolean(busy) || enterpriseReadOnly}>Approve</LiteButton> : null}{canReviewRequests && approval.viewer_actions?.reject ? <LiteButton variant="secondary" onClick={() => transitionApproval(approval, 'reject')} disabled={Boolean(busy) || enterpriseReadOnly}>Reject</LiteButton> : null}{approval.viewer_actions?.cancel ? <LiteButton variant="secondary" onClick={() => transitionApproval(approval, 'cancel')} disabled={Boolean(busy) || enterpriseReadOnly}>Cancel request</LiteButton> : null}</div></div>; })}</div>}
          {!approvals.loading && !(approvals.data?.approvals || []).length ? <StateSurface tone="neutral" title="No review requests" description={resolvedRole === 'Owner' ? 'Owner has no peer-approval requirement. Delegated requests will appear here when Admin or Operator actions require review.' : 'A qualifying delegated protected action will create a short-lived request here.'} /> : null}
          {approvalDetail ? <div className="lite-rules-focus-detail"><div className="lite-rules-card-head"><strong>Request history</strong><LiteButton variant="secondary" onClick={() => setApprovalDetail(null)}>Close</LiteButton></div><ol className="lite-rules-history-list">{(approvalDetail.history || []).map((entry,index) => <li key={`${entry.occurred_at}-${index}`}><strong>{getLiteStatusPresentation(entry.event_type?.split('.').pop()).label}</strong><span>{entry.summary}</span><small>{formatLiteTime(entry.occurred_at)}</small></li>)}</ol></div> : null}
        </GlassCard>
      ) : null}

      {section === 'exceptions' ? (
        <GlassCard className="lite-rules-card">
          <div className="lite-rules-card-head"><LiteHelpHeading title="Temporary access" helpKey="rules.exceptions" as="h3" /><span className="lite-rules-soft-badge">Narrow + expiring</span></div>
          {!canReadExceptions ? <RoleUnavailable title="Temporary access is not available to this role" description="Owner/Admin can create or revoke exact exceptions. Auditor can review them. Operator and Viewer do not receive this continuation surface." /> : <><StateSurface tone="neutral" title="Exact scope only" description="Temporary access is bound to one app, one device, one active person, the current Rules revision and at most 60 minutes. Wildcards remain blocked by the server." />{canManageExceptions ? <form onSubmit={createException} className="lite-rules-form-grid mt-4"><label><span>App</span><select value={exceptionDraft.app_id} onChange={(event) => setExceptionDraft((value) => ({ ...value, app_id: event.target.value }))}><option value="photoprism">PhotoPrism</option></select></label><label><span>Device</span><select required value={exceptionDraft.device_id} onChange={(event) => setExceptionDraft((value) => ({ ...value, device_id: event.target.value }))}><option value="">Select a device</option>{devices.map((device) => { const id = device.device_id || device.id; return <option key={id} value={id}>{device.display_name || device.name || 'Pocket Lab device'}</option>; })}</select></label><label><span>Person</span><select required value={exceptionDraft.human_id} onChange={(event) => setExceptionDraft((value) => ({ ...value, human_id: event.target.value }))}><option value="">Select a person</option>{people.map((person) => <option key={person.human_id} value={person.human_id}>{person.display_name} · {person.role}</option>)}</select></label><label><span>Expires in</span><select value={String(exceptionDraft.duration_minutes)} onChange={(event) => setExceptionDraft((value) => ({ ...value, duration_minutes: Number(event.target.value) }))}><option value="5">5 minutes</option><option value="15">15 minutes</option><option value="30">30 minutes</option><option value="60">60 minutes</option></select></label><label className="lite-rules-form-wide"><span>Reason</span><input required maxLength="240" value={exceptionDraft.reason} onChange={(event) => setExceptionDraft((value) => ({ ...value, reason: event.target.value }))} /></label><LiteButton type="submit" disabled={Boolean(busy) || enterpriseReadOnly || !exceptionDraft.device_id || !exceptionDraft.human_id}>Create temporary access</LiteButton></form> : <StateSurface tone="neutral" title="Read-only temporary access" description="Auditor can review exact scope and lifecycle but cannot create or revoke exceptions." className="mt-3" />}<div className="lite-rules-decision-list mt-4">{(exceptions.data?.exceptions || []).map((exception) => { const state = getLiteStatusPresentation(exception.status); return <div key={exception.exception_id} className="lite-rules-exception-row"><StatusBadge status={state.tone}>{state.label}</StatusBadge><div><strong>{exception.app_id} on {exception.device_id}</strong><span>{exception.reason}</span><small>Expires {formatLiteTime(exception.expires_at)}</small></div>{canManageExceptions && exception.status === 'active' ? <LiteButton variant="secondary" onClick={() => revokeException(exception.exception_id)} disabled={Boolean(busy)}>Revoke</LiteButton> : null}</div>; })}</div>{!exceptions.loading && !(exceptions.data?.exceptions || []).length ? <StateSurface tone="neutral" title="No temporary access" description="No active or recent exact exceptions are recorded." /> : null}</>}
        </GlassCard>
      ) : null}
    </section>
  );
}
