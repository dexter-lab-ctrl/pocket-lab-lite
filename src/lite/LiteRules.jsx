import './identityRules.css';
import './identityRulesGovernance.css';
import './rulesActivationProgress.css';
import React from 'react';
import { ShieldCheck, History, CircleAlert, Move, Maximize2, RotateCcw, ArrowLeft, ChevronRight, ScanSearch, ListChecks, ScrollText, FlaskConical, UserCheck, TimerReset, Settings2 } from 'lucide-react';
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
import { useDesktopManageGeometry, MANAGE_DESKTOP_QUERY } from './components/useDesktopManageGeometry.js';
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
  const { panelRef: managePanelRef, desktopPanel, panelStyle, announcement, reset: resetManagePanel, startPanelInteraction, adjustPanelWithKeyboard } = useDesktopManageGeometry({ open: manageOpen, defaultWidth: 680, minWidth: 380, minHeight: 360 });
  const [manageSection, setManageSection] = React.useState('overview');
  const manageTitleRef = React.useRef(null);
  const [insightDecision, setInsightDecision] = React.useState(null);
  const [manageDecision, setManageDecision] = React.useState(null);
  const [sourceSyncBusy, setSourceSyncBusy] = React.useState(false);
  const [sourceSyncNotice, setSourceSyncNotice] = React.useState(null);
  const [activationStatus, setActivationStatus] = React.useState(null);
  const [activationTracked, setActivationTracked] = React.useState(false);
  const [activationDetailsOpen, setActivationDetailsOpen] = React.useState(false);
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
  const protection = rulesProtectionView(data, { savedStateOnly, backendReachable, isExpired, enterprise: enterpriseMode, activationState });
  const openManage = (section = 'overview') => { setManageDecision(null); setManageSection(section === 'overview' && !(typeof window !== 'undefined' && window.matchMedia?.(MANAGE_DESKTOP_QUERY)?.matches) ? null : section); setManageOpen(true); };
  React.useEffect(() => {
    if (manageOpen && manageSection && !desktopPanel) manageTitleRef.current?.focus({ preventScroll: true });
  }, [manageOpen, manageSection, desktopPanel]);
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
  // Settings groups are UI navigation only. Enterprise permissions remain server-owned.
  const groups = [
    { heading: 'Protection', items: [
      ['overview', 'Protection Overview', ShieldCheck],
      ['protections', 'Protected Actions', ListChecks],
      ['journey', 'How Protection Works', ScanSearch],
    ] },
    { heading: 'Activity', items: [['decisions', 'Decision History', History]] },
    { heading: 'Policies', items: [
      ['policies', 'Policy Settings', ScrollText],
      ...(enterpriseEnabled ? [['revision', 'Rules Version', RotateCcw]] : []),
    ] },
    { heading: 'Advanced', items: [
      ...(enterpriseEnabled ? [
        ['simulate', 'Test a Change', FlaskConical], ['requests', 'Requests & Approvals', UserCheck],
        ['exceptions', 'Temporary Access', TimerReset], ['governance', 'Governance', ShieldCheck],
      ] : []),
      ['technical', 'Technical Status', Settings2],
    ] },
  ];
  const selectedLabel = groups.flatMap((group) => group.items).find(([id]) => id === manageSection)?.[1] || 'Protection Overview';

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
        kind: 'info', // Accepted is not proof of completed activation.
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
  const protectedModeLabel = protection.mode;
  const revisionLabel = protection.revisionCurrent ? 'Revision verified' : sourceUpdateRequired ? 'Update required' : 'Revision unverified';
  return (
    <section className="lite-rules-premium-screen" data-rules-protection-state={protection.state}>
      <PageHeader eyebrow="Rules" title="Safety Rules"
        description="Understand protection, review decisions, and manage authorized controls."
        actions={<div className="lite-governance-inline-actions lite-rules-header-actions">
          <LiteHelp helpKey="rules.protection" />
          <LiteRefreshButton scope="rules" refresh={refresh} cacheStatus={cacheStatus} error={error} refreshing={refreshing} />
        </div>}
      />
      <GlassCard className="lite-rules-premium-hero" aria-label="Protection Center">
        <div className="lite-rules-premium-hero-head">
          <div className="lite-rules-premium-brand"><span className="lite-rules-premium-shield"><ShieldCheck size={23} aria-hidden="true" /></span><span className="lite-rules-eyebrow">Protection Center</span></div>
          <StatusBadge status={protection.tone}>{protection.label}</StatusBadge>
        </div>
        <h2>{protection.headline}</h2>
        <p>{protection.summary}</p>
        <div className="lite-rules-premium-chips" aria-label="Mode and Rules revision"><span>{protectedModeLabel}</span><span>{revisionLabel}</span></div>
        {protection.updateAttention ? <div className="lite-rules-premium-attention"><CircleAlert size={18} aria-hidden="true" /><span>A Rules update requires attention. Current protection stays subject to server authorization.</span></div> : null}
        <LiteButton onClick={() => openManage('overview')}>Manage Safety Rules <ChevronRight size={17} aria-hidden="true" /></LiteButton>
      </GlassCard>
      <LiteFreshness saved={savedStateOnly} stale={isExpired} refreshing={refreshing} lastUpdatedLabel={lastUpdatedLabel} backendReachable={backendReachable} />
      {loading && !data ? <LoadingCard label="Checking your Safety Rules…" /> : null}
      {error && !data ? <StateSurface tone="degraded" title="Live Rules unavailable" description="Pocket Lab could not confirm protection. No action is authorized from saved information." /> : null}
      {sourceSyncNotice ? <StateSurface tone={sourceSyncNotice.error ? 'degraded' : 'neutral'} title={sourceSyncNotice.title} description={sourceSyncNotice.message} /> : null}
      <div className="lite-rules-premium-overview-grid">
        <RulesProtectionJourney />
        <GlassCard className="lite-rules-premium-latest" aria-label="Latest Decision">
          <header><div><span className="lite-rules-eyebrow">Activity</span><h2>Latest Decision</h2></div></header>
          {latestView ? <div className="lite-rules-premium-latest-body">
            <StatusBadge status={savedStateOnly || isExpired ? 'neutral' : latestView.tone}>{latestView.status}</StatusBadge>
            <h3>{latestView.action}</h3><p>{latestView.reason}</p>
            {latestView.occurredAt ? <time dateTime={latestView.occurredAt}>{formatLiteTime(latestView.occurredAt)}</time> : null}
            <p className="lite-rules-premium-boundary">Authorization is separate from execution.</p>
            <LiteButton tone="secondary" onClick={() => explainDecision(latest)}>Explain decision <ChevronRight size={16} aria-hidden="true" /></LiteButton>
          </div> : <StateSurface tone="neutral" title={rulesReadOnly ? 'Current decisions unavailable' : 'No recorded decisions'} description={rulesReadOnly ? 'Live decisions could not be confirmed. Open saved information only for reference.' : 'When Pocket Lab evaluates a protected change, the decision can appear here.'} />}
          {(savedStateOnly || isExpired) && latestView ? <p className="lite-rules-premium-saved">Saved decision — current status not confirmed.</p> : null}
        </GlassCard>
      </div>
      {showActivationProgress ? <div className="lite-rules-activation-entry"><StateSurface tone="neutral" title="Rules update status" description={`Server-reported phase: ${activationStatus.state || 'Uncertain'}. Completion is not assumed.`} /><LiteButton tone="secondary" onClick={() => setActivationDetailsOpen(true)}>View update progress</LiteButton></div> : activationInProgress ? <StateSurface tone="neutral" title="Rules update reported" description="The server reports an update but has not returned a detailed activation phase." /> : null}
      <LiteSheet variant="rules" open={manageOpen} onClose={() => { setManageOpen(false); setManageDecision(null); }} title="Manage Safety Rules" eyebrow="Protection"
        description={`${protection.label} · ${protectedModeLabel} · ${revisionLabel}`}
        className={`lite-rules-manage-sheet lite-rules-premium-manage ${desktopPanel ? 'is-movable' : ''}`}
        mobileSnap={!desktopPanel}
        surfaceRef={managePanelRef} surfaceStyle={panelStyle}
        surfaceProps={{ 'data-rules-manage-layout': desktopPanel ? 'desktop-movable' : 'mobile-sheet' }}
        headerActions={desktopPanel ? <div className="lite-rules-desktop-panel-tools" role="group" aria-label="Desktop Safety Rules panel controls">
          <button type="button" aria-label="Move Safety Rules panel" title="Drag or use arrow keys to move; Shift + arrow for larger steps" aria-keyshortcuts="ArrowUp ArrowDown ArrowLeft ArrowRight" onPointerDown={(event) => startPanelInteraction('move', event)} onKeyDown={(event) => adjustPanelWithKeyboard('move', event)}><Move size={16} aria-hidden="true" /></button>
          <button type="button" aria-label="Reset Safety Rules panel position and size" onClick={resetManagePanel}><RotateCcw size={16} aria-hidden="true" /> Reset</button>
          <button type="button" aria-label="Resize Safety Rules panel" title="Drag or use arrow keys to resize; Home resets" aria-keyshortcuts="ArrowUp ArrowDown ArrowLeft ArrowRight" onPointerDown={(event) => startPanelInteraction('resize', event)} onKeyDown={(event) => adjustPanelWithKeyboard('resize', event)}><Maximize2 size={16} aria-hidden="true" /></button>
          <span className="sr-only" role="status" aria-live="polite">{announcement}</span>
        </div> : null}>
        <div className="lite-rules-native-workspace" data-rules-manage-view={manageSection ? 'section' : 'index'}>
          <nav className="lite-rules-premium-nav" aria-label="Manage Safety Rules sections">
            {groups.map((group) => <div className="lite-rules-native-group" key={group.heading}>
              <h2>{group.heading}</h2>
              <div className="lite-rules-native-group-rows">
                {group.items.map(([id, label, Icon]) => <button key={id} type="button"
                  className={manageSection === id ? 'lite-rules-native-row is-active' : 'lite-rules-native-row'}
                  aria-current={manageSection === id ? 'page' : undefined} aria-label={label}
                  onClick={() => { setManageDecision(null); setManageSection(id); }}>
                  <Icon size={19} aria-hidden="true" /><span>{label}</span><ChevronRight size={17} aria-hidden="true" />
                </button>)}
              </div>
            </div>)}
          </nav>
          <section className="lite-rules-native-detail" aria-label={selectedLabel}>
            <button className="lite-rules-native-back" type="button" onClick={() => { setManageDecision(null); setManageSection(null); }}>
              <ArrowLeft size={18} aria-hidden="true" /> All Safety Rules settings
            </button>
            <h2 className="lite-rules-native-detail-title" tabIndex={-1} ref={manageTitleRef}>{selectedLabel}</h2>
            {manageSection === 'overview' ? <div className="lite-rules-premium-manage-content" data-rules-manage-section="overview">
              <StatusBadge status={protection.tone}>{protection.label}</StatusBadge>
              <p>{protection.summary}</p>
              <LiteFreshness saved={savedStateOnly} stale={isExpired} refreshing={refreshing} lastUpdatedLabel={lastUpdatedLabel} backendReachable={backendReachable} />
              <p>Mode: {protection.mode}. Revision: {revisionLabel}. Rules updates and decisions require current server authority.</p>
              {sourceUpdateRequired ? <StateSurface tone="neutral" title="Safety Rules update required" description="An Owner must confirm the update. Known-good protection stays authoritative until verified." /> : null}
              {sourceUpdateRequired && role === 'Owner' ? <LiteButton disabled={rulesReadOnly || activationBusy} onClick={updateSafetyRules}>{activationBusy ? 'Update running' : 'Update Safety Rules'}</LiteButton> : null}
              {showActivationProgress ? <RulesActivationTimeline operation={activationStatus} backendReachable={backendReachable && !savedStateOnly} /> : null}
            </div> : null}
            {manageSection === 'protections' ? <div className="lite-rules-premium-manage-content" data-rules-manage-section="protections">
              {(data?.policy_groups || []).map((group,index) => <LiteActionRow key={group.id || index} label={group.label || 'Protected group'} value={Array.isArray(group.actions) ? group.actions.length + ' actions' : 'Information unavailable'} summary={Array.isArray(group.actions) ? group.actions.map(actionLabel).join(' · ') : 'No actions reported'} />)}
              {!(data?.policy_groups || []).length ? <StateSurface tone="neutral" title="Protection groups unavailable" description="No policy-group information was returned." /> : null}
              <p>Owner actions still require backend checks and passkey confirmation when reported.</p>
            </div> : null}
            {manageSection === 'journey' ? <RulesProtectionJourney /> : null}
            {manageSection === 'decisions' && !enterpriseEnabled ? <div className="lite-rules-premium-manage-content" data-rules-manage-section="decisions">
              {manageDecision ? <div className="lite-rules-premium-inline-insight"><LiteButton tone="secondary" onClick={() => setManageDecision(null)}>Back to Decision History</LiteButton><RulesDecisionInsight decision={manageDecision} /></div> : <RulesDecisionTimeline decisions={recent} saved={savedStateOnly || isExpired} onExplain={(record) => explainDecision(record, true)} />}
            </div> : null}
            {manageSection === 'policies' && !enterpriseEnabled ? <div className="lite-rules-premium-manage-content" data-rules-manage-section="policies">
              {templates.map((template) => <LiteActionRow key={template.id} label={template.label} value={template.status === 'active' ? 'Active' : template.status === 'available' ? 'Available' : 'Status not confirmed'} summary={template.summary} />)}
              {!templates.length ? <StateSurface tone="neutral" title="No policy summaries available" description="Only server-supported policy summaries are displayed." /> : null}
            </div> : null}
            {enterpriseEnabled && enterpriseSections[manageSection] ? <div data-rules-manage-section={manageSection}><LiteRulesEnterprise key={manageSection} role={role} embedded sectionOverride={enterpriseSections[manageSection]} /></div> : null}
            {manageSection === 'technical' ? <div className="lite-rules-premium-manage-content" data-rules-manage-section="technical">
              <LiteTechnicalFacts title="Show technical details" facts={[
                { id: 'engine', label: 'Policy engine', value: data?.engine?.healthy === true && !rulesReadOnly ? 'Reported healthy' : 'Not confirmed' },
                { id: 'loopback', label: 'Local-only restriction', value: data?.engine?.loopback_only === true ? 'Reported local only' : 'Not confirmed' },
                { id: 'bundle', label: 'Rules bundle', value: data?.active_policy?.bundle_ready === true ? 'Reported ready' : 'Not confirmed' },
                { id: 'freshness', label: 'Data freshness', value: savedStateOnly ? 'Saved only' : isExpired ? 'Stale' : backendReachable ? 'Live' : 'Unavailable' },
                { id: 'updated', label: 'Last updated', value: lastUpdatedLabel || 'Not reported' },
              ]} />
            </div> : null}
          </section>
        </div>
      </LiteSheet>
      <LiteSheet variant="rules" mobileSnap open={activationDetailsOpen && showActivationProgress} onClose={() => setActivationDetailsOpen(false)}
        title="Safety Rules update" eyebrow="Revision & Recovery" description="Only the server can confirm completion or rollback." className="lite-rules-activation-sheet">
        {showActivationProgress ? <RulesActivationTimeline operation={activationStatus} backendReachable={backendReachable && !savedStateOnly} /> : null}
      </LiteSheet>
      <LiteSheet variant="rules" mobileSnap open={Boolean(insightDecision)} onClose={() => setInsightDecision(null)}
        title="Decision Insight" eyebrow="Safety Rules" description="What the server reported about this protected decision."
        className="lite-rules-insight-sheet">
        {insightDecision ? <RulesDecisionInsight decision={insightDecision} /> : null}
      </LiteSheet>
    </section>
  );

}
