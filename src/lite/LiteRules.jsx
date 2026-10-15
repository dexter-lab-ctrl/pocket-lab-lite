import './identityRules.css';
import './identityRulesGovernance.css';
import './rulesActivationProgress.css';
import React from 'react';
import { ShieldCheck, History, CircleAlert } from 'lucide-react';
import RulesProtectionJourney from './rules/RulesProtectionJourney.jsx';
import RulesDecisionInsight from './rules/RulesDecisionInsight.jsx';
import { RulesDecisionTimeline, RulesActivationTimeline } from './rules/RulesPremiumTimeline.jsx';
import { rulesProtectionView, rulesDecisionView } from './rules/rulesPremiumView.js';
import './rules/rulesPremium.css';
import { useLiteResource } from '../hooks/useLiteStatus.js';
import { formatLiteTime, liteApi } from '../lib/liteApi.js';
import { liteEnterpriseApi } from '../lib/liteEnterpriseApi.js';
import { getLitePasskey } from '../lib/liteWebAuthn.js';
import { getLiteReasonPresentation, getLiteRulesActionLabel } from '../lib/identityRulesPresentation.js';
import {
  GlassCard,
  StatusBadge,
  StateSurface,
  PageHeader,
  LiteRefreshButton,
  LoadingCard,
  LiteButton,
  LiteActionRow,
} from './LiteUi.jsx';
import LiteRulesEnterprise from './LiteRulesEnterprise.jsx';
import LiteHelp from './LiteHelp.jsx';
import { LiteSheet } from './LiteOverlay.jsx';
import { LiteFreshness, LiteTechnicalFacts } from './LiteUx.jsx';
import { useLiteUiStore } from '../stores/liteUiStore.js';

const RULE_ACTIVATION_NONTERMINAL = new Set(['pending', 'validating', 'switching', 'restarting', 'verifying', 'rolling_back']);
function actionLabel(action = '') {
  return getLiteRulesActionLabel(action) || 'Protected action';
}
function errorCode(error) {
  return error?.payload?.detail?.reason_code || error?.payload?.reason_code || '';
}
export default function RulesScreen() {
  const policy = useLiteResource(liteApi.policy, []);
  const identity = useLiteResource(liteEnterpriseApi.identitySelf, []);
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
  } = policy;
  const [manageOpen, setManageOpen] = React.useState(false);
  const [manageSection, setManageSection] = React.useState('overview');
  const [insightDecision, setInsightDecision] = React.useState(null);
  const [manageDecision, setManageDecision] = React.useState(null);
  const [sourceSyncBusy, setSourceSyncBusy] = React.useState(false);
  const [sourceSyncNotice, setSourceSyncNotice] = React.useState(null);
  const [activationStatus, setActivationStatus] = React.useState(null);
  const [activationTracked, setActivationTracked] = React.useState(false);
  const pushToast = useLiteUiStore((state) => state.pushToast);
  const enterpriseEnabled = identity.data?.enterprise?.enabled === true;
  const enterpriseMode = identity.data?.enterprise?.enabled;
  const role = identity.data?.enterprise?.current_membership?.role || identity.data?.person?.role || (identity.data?.person?.is_local_owner ? 'Owner' : '');
  const rulesReadOnly = savedStateOnly || isExpired || !backendReachable;
  const sourceUpdateRequired = Boolean(data?.active_policy?.source_update_required);
  const activationInProgress = Boolean(data?.active_policy?.activation_in_progress) || data?.degraded_reason === 'policy_activation_pending';
  const activationState = String(activationStatus?.state || '');
  const activationBusy = sourceSyncBusy || activationInProgress || RULE_ACTIVATION_NONTERMINAL.has(activationState);
  const recent = Array.isArray(data?.recent_decisions) ? data.recent_decisions : [];
  const latest = recent[0] || null;
  const latestView = rulesDecisionView(latest);
  const templates = Array.isArray(data?.templates) ? data.templates : [];
  const protection = rulesProtectionView(data, { savedStateOnly, backendReachable, isExpired, enterprise: enterpriseMode });
  const openManage = (section = 'overview') => { setManageDecision(null); setManageSection(section); setManageOpen(true); };
  async function explainDecision(record, inManage = false) {
    if (!record) return;
    const update = inManage ? setManageDecision : setInsightDecision;
    update(record);
    // Details are hydrated only on intent. Never fetch an entire history for first paint.
    if (!record.decision_id || !backendReachable || savedStateOnly) return;
    try {
      const result = await liteApi.policyDecision(record.decision_id);
      const detail = result?.decision && typeof result.decision === 'object' ? result.decision : result;
      if (!detail || typeof detail !== 'object' || (detail.decision_id && detail.decision_id !== record.decision_id)) return;
      update((previous) => previous?.decision_id === record.decision_id ? { ...record, ...detail } : previous);
    } catch (_error) {
      // Retain verified list summary; missing detail is not a new authorization outcome.
    }
  }
  const enterpriseSections = {
    governance: 'protection', decisions: 'activity', policies: 'policies', simulate: 'simulate',
    requests: 'requests', exceptions: 'exceptions', revision: 'revision',
  };
  const sections = [
    ['overview', 'Overview'], ['protections', 'Protections'], ['decisions', 'Decisions'],
    ...(enterpriseEnabled ? [['simulate', 'Test a Change'], ['policies', 'Policies'], ['requests', 'Requests'], ['exceptions', 'Temporary Access'], ['revision', 'Revision & Recovery'], ['governance', 'Governance']] : [['policies', 'Policies']]),
    ['technical', 'Technical Status'],
  ];

  React.useEffect(() => {
    if (!backendReachable || (!activationInProgress && !activationTracked)) return undefined;
    if (['active', 'not_completed', 'uncertain', 'rolled_back', 'failed'].includes(activationState)) return undefined;

    let cancelled = false;
    let timer = null;

    async function pollActivation() {
      try {
        const result = await liteEnterpriseApi.ruleSourceSyncStatus();
        if (cancelled) return;
        const source = result?.source || {};
        const operation = source?.activation_operation && typeof source.activation_operation === 'object'
          ? source.activation_operation
          : null;
        if (operation) {
          setActivationTracked(true);
          setActivationStatus(operation);
        } else if (activationTracked || activationInProgress) {
          // Missing server operation evidence is uncertainty, never synthetic success.
          setActivationStatus((previous) => ({ ...(previous || {}), state: 'uncertain' }));
        }
        await refresh({ force: true });
      } catch (_pollError) {
        // Keep the last proved phase. Network loss must never synthesize progress.
      }
      if (!cancelled) timer = window.setTimeout(pollActivation, 1200);
    }

    pollActivation();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [activationInProgress, activationTracked, activationState, backendReachable, refresh]);

  async function updateSafetyRules() {
    if (activationBusy) return;
    setSourceSyncBusy(true);
    setSourceSyncNotice({ title: 'Waiting for Pocket Lab', message: 'Current protection stays fail-closed while the Rules update is prepared.' });
    try {
      let result;
      try {
        result = await liteEnterpriseApi.syncRuleSource();
      } catch (firstError) {
        if (firstError?.status !== 428 && errorCode(firstError) !== 'owner_step_up_required') throw firstError;
        setSourceSyncNotice({ title: 'Confirm with your passkey', message: 'Owner confirmation is required before Pocket Lab can activate updated Safety Rules.' });
        const options = await liteApi.passkeyStepUpOptions('policy.rules.activate');
        const credential = await getLitePasskey(options);
        await liteApi.verifyPasskeyStepUp({ purpose: 'policy.rules.activate', challenge: options.publicKey.challenge, credential });
        result = await liteEnterpriseApi.syncRuleSource();
      }
      if (result?.accepted) {
        setActivationTracked(true);
        setActivationStatus(result?.operation || { state: 'pending' });
      }
      setSourceSyncNotice({
        title: result?.accepted ? 'Safety Rules update accepted' : 'Safety Rules already current',
        message: result?.summary || 'Pocket Lab accepted the Rules reconciliation request.',
      });
      pushToast({
        id: `rules-source:${result?.operation?.operation_id || result?.updated_at || 'current'}`,
        kind: result?.accepted ? 'success' : 'info',
        title: result?.accepted ? 'Safety Rules update accepted' : 'Safety Rules already current',
        message: result?.summary || 'Pocket Lab accepted the Rules reconciliation request.',
      });
      await refresh({ force: true });
    } catch (syncError) {
      const reason = getLiteReasonPresentation(errorCode(syncError), syncError?.message || 'Pocket Lab could not start the Safety Rules update.');
      setSourceSyncNotice({ error: true, title: reason.title, message: reason.message });
      pushToast({ id: 'rules-source:problem', kind: 'error', title: reason.title, message: reason.message });
    } finally {
      setSourceSyncBusy(false);
    }
  }

  const showActivationProgress = Boolean(activationStatus);
  return (
    <section className="lite-rules-premium-screen" data-rules-protection-state={protection.state}>
      <PageHeader
        eyebrow="Rules"
        title="Safety Rules"
        description="Understand how sensitive changes are checked and review recent decisions."
        actions={<div className="lite-governance-inline-actions"><LiteHelp helpKey="rules.protection" /><LiteRefreshButton scope="rules" refresh={refresh} cacheStatus={cacheStatus} error={error} refreshing={refreshing} /></div>}
      />
      <GlassCard className="lite-rules-premium-hero">
        <div className="lite-rules-premium-hero-head">
          <div className="lite-rules-premium-brand"><ShieldCheck size={25} aria-hidden="true" /><div><span>Safety Rules</span><small>Protection Center</small></div></div>
          <StatusBadge status={protection.tone}>{protection.label}</StatusBadge>
        </div>
        <h2>{protection.headline}</h2>
        <p>{protection.summary}</p>
        <div className="lite-rules-premium-chips"><span>{protection.mode}</span>{protection.revisionCurrent ? <span>Rules current</span> : null}</div>
        {protection.updateAttention ? <div className="lite-rules-premium-attention"><CircleAlert size={18} aria-hidden="true" /><span>Safety Rules update requires attention. Protected changes are checked against authoritative server state.</span></div> : null}
        <LiteButton onClick={() => openManage('overview')}>Manage Safety Rules</LiteButton>
      </GlassCard>
      <LiteFreshness saved={savedStateOnly} stale={isExpired} refreshing={refreshing} lastUpdatedLabel={lastUpdatedLabel} backendReachable={backendReachable} />
      {loading && !data ? <LoadingCard label="Checking your Safety Rules…" /> : null}
      {error && !data ? <StateSurface tone="degraded" title="Live Rules unavailable" description="Pocket Lab could not confirm the protection state. No action is authorized from saved information." /> : null}
      {sourceSyncNotice ? <StateSurface tone={sourceSyncNotice.error ? 'degraded' : 'neutral'} title={sourceSyncNotice.title} description={sourceSyncNotice.message} /> : null}
      <RulesProtectionJourney />
      <GlassCard className="lite-rules-premium-latest" aria-label="Latest Decision">
        <header><div><span className="lite-rules-eyebrow">Latest Decision</span><h2>Most recent protection decision</h2></div><LiteButton tone="secondary" onClick={() => openManage('decisions')}><History size={16} aria-hidden="true" /> History</LiteButton></header>
        {latestView ? <div className="lite-rules-premium-latest-body">
          <StatusBadge status={latestView.tone}>{latestView.status}</StatusBadge>
          <h3>{latestView.action}</h3><p>{latestView.reason}</p>
          {latestView.occurredAt ? <time dateTime={latestView.occurredAt}>{formatLiteTime(latestView.occurredAt)}</time> : null}
          <p className="lite-rules-premium-boundary">This is an authorization decision, not proof of execution.</p>
          <LiteButton onClick={() => explainDecision(latest)}>Explain this</LiteButton>
        </div> : <StateSurface tone="neutral" title="No recorded decisions" description="When Pocket Lab evaluates a protected change, its decision can appear here. Nothing is assumed." />}
        {(savedStateOnly || isExpired) && latestView ? <p className="lite-rules-premium-saved">Saved decision — current state not confirmed.</p> : null}
      </GlassCard>
      {showActivationProgress ? <RulesActivationTimeline operation={activationStatus} backendReachable={backendReachable && !savedStateOnly} /> : activationInProgress ? <StateSurface tone="neutral" title="Rules update reported" description="The server reports an update but has not returned a detailed activation phase. No stage is assumed." /> : null}
      <LiteSheet variant="rules" open={manageOpen} onClose={() => setManageOpen(false)} title="Manage Safety Rules" eyebrow="Safety Rules" description="Review current protection, decisions and authorized management options." className="lite-rules-manage-sheet lite-rules-premium-manage">
        <nav className="lite-rules-premium-nav" aria-label="Manage Safety Rules sections">
          {sections.map(([id,label]) => <button key={id} type="button" aria-current={manageSection === id ? 'page' : undefined} className={manageSection === id ? 'is-active' : ''} onClick={() => setManageSection(id)}>{label}</button>)}
        </nav>
        {manageSection === 'overview' ? <div className="lite-rules-premium-manage-content" data-rules-manage-section="overview">
          <h2>Protection overview</h2><StatusBadge status={protection.tone}>{protection.label}</StatusBadge>
          <p>{protection.summary}</p><p>Workspace: {protection.mode}. Rules updates and policy decisions require live server authority.</p>
          {sourceUpdateRequired ? <StateSurface tone="neutral" title="Safety Rules update ready" description="An Owner must confirm the update. Known-good protection remains authoritative until verified." /> : null}
          {sourceUpdateRequired && role === 'Owner' ? <LiteButton disabled={rulesReadOnly || activationBusy} onClick={updateSafetyRules}>{activationBusy ? 'Update running' : 'Update Safety Rules'}</LiteButton> : null}
          {showActivationProgress ? <RulesActivationTimeline operation={activationStatus} backendReachable={backendReachable && !savedStateOnly} /> : null}
        </div> : null}
        {manageSection === 'protections' ? <div className="lite-rules-premium-manage-content" data-rules-manage-section="protections"><h2>Protected actions</h2>
          {(data?.policy_groups || []).map((group,index) => <LiteActionRow key={group.id || index} label={group.label || 'Protected group'} value={Array.isArray(group.actions) ? group.actions.length + ' actions' : 'Information unavailable'} summary={Array.isArray(group.actions) ? group.actions.map(actionLabel).join(' · ') : 'No actions reported'} />)}
          {!(data?.policy_groups || []).length ? <StateSurface tone="neutral" title="Protection groups unavailable" description="No policy-group information was returned." /> : null}
          <p>Owner actions still obey Server Host protections, passkey step-up where required and backend confirmation.</p>
        </div> : null}
        {manageSection === 'decisions' && !enterpriseEnabled ? <div className="lite-rules-premium-manage-content" data-rules-manage-section="decisions"><h2>Decision History</h2>
          {manageDecision ? <div className="lite-rules-premium-inline-insight"><LiteButton tone="secondary" onClick={() => setManageDecision(null)}>Back to Decision History</LiteButton><RulesDecisionInsight decision={manageDecision} /></div> : <RulesDecisionTimeline decisions={recent} saved={savedStateOnly || isExpired} onExplain={(record) => explainDecision(record, true)} />}
        </div> : null}
        {manageSection === 'policies' && !enterpriseEnabled ? <div className="lite-rules-premium-manage-content" data-rules-manage-section="policies"><h2>Policy summaries</h2>
          {templates.map((template) => <LiteActionRow key={template.id} label={template.label} value={template.status === 'active' ? 'Active' : 'Available'} summary={template.summary} />)}
          {!templates.length ? <StateSurface tone="neutral" title="No policy summaries available" description="Only server-supported policy summaries are displayed." /> : null}
        </div> : null}
        {enterpriseEnabled && enterpriseSections[manageSection] ? <div data-rules-manage-section={manageSection}><LiteRulesEnterprise key={manageSection} role={role} embedded sectionOverride={enterpriseSections[manageSection]} /></div> : null}
        {manageSection === 'technical' ? <div className="lite-rules-premium-manage-content" data-rules-manage-section="technical">
          <h2>Technical Status</h2><LiteTechnicalFacts title="Show technical details" facts={[
            { id: 'engine', label: 'Policy engine', value: data?.engine?.healthy === true && !rulesReadOnly ? 'Reported healthy' : 'Not confirmed' },
            { id: 'loopback', label: 'Local-only restriction', value: data?.engine?.loopback_only === true ? 'Reported local only' : 'Not confirmed' },
            { id: 'bundle', label: 'Rules bundle', value: data?.active_policy?.bundle_ready === true ? 'Reported ready' : 'Not confirmed' },
            { id: 'freshness', label: 'Data freshness', value: savedStateOnly ? 'Saved only' : isExpired ? 'Stale' : backendReachable ? 'Live' : 'Unavailable' },
            { id: 'updated', label: 'Last updated', value: lastUpdatedLabel || 'Not reported' },
          ]} />
        </div> : null}
      </LiteSheet>
      <LiteSheet variant="rules" open={Boolean(insightDecision)} onClose={() => setInsightDecision(null)} title="Decision Insight" eyebrow="Safety Rules" description="What the server reported about this protected decision." className="lite-rules-insight-sheet">
        {insightDecision ? <RulesDecisionInsight decision={insightDecision} /> : null}
      </LiteSheet>
    </section>
  );
}
