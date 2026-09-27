import './identityRules.css';
import './identityRulesGovernance.css';
import './rulesActivationProgress.css';
import React from 'react';
import { FileCheck, ShieldCheck } from 'lucide-react';
import { useLiteResource } from '../hooks/useLiteStatus.js';
import { formatLiteTime, liteApi } from '../lib/liteApi.js';
import { liteEnterpriseApi } from '../lib/liteEnterpriseApi.js';
import { getLitePasskey } from '../lib/liteWebAuthn.js';
import { buildLiteRulesOverview, getLiteReasonPresentation, getLiteRulesActionLabel } from '../lib/identityRulesPresentation.js';
import {
  GlassCard,
  StatusBadge,
  StateSurface,
  PageHeader,
  LiteRefreshButton,
  LoadingCard,
  LiteButton,
  LiteActionRow,
  LiteOperationalStory,
} from './LiteUi.jsx';
import LiteRulesEnterprise from './LiteRulesEnterprise.jsx';
import LiteHelp, { LiteHelpHeading } from './LiteHelp.jsx';
import { LiteSheet } from './LiteOverlay.jsx';
import { LiteFreshness, LiteHistoryTimeline, LiteTechnicalFacts } from './LiteUx.jsx';

const RULE_ACTIVATION_STEPS = [
  { id: 'pending', label: 'Accepted', detail: 'Owner confirmation was accepted and queued for the supervisor.' },
  { id: 'validating', label: 'Validating', detail: 'Pocket Lab is checking the candidate and its immutable manifest.' },
  { id: 'switching', label: 'Switching', detail: 'The supervisor is switching to the staged candidate under the activation lock.' },
  { id: 'restarting', label: 'Restarting', detail: 'The local policy engine is restarting on the candidate revision.' },
  { id: 'verifying', label: 'Verifying', detail: 'Pocket Lab is proving health and the exact running Rules revision.' },
  { id: 'active', label: 'Succeeded', detail: 'The proved revision is active and known-good.' },
];
const RULE_ACTIVATION_NONTERMINAL = new Set(['pending', 'validating', 'switching', 'restarting', 'verifying', 'rolling_back']);

function actionLabel(action = '') {
  return getLiteRulesActionLabel(action) || String(action || '').replaceAll('.', ' · ');
}

function errorCode(error) {
  return error?.payload?.detail?.reason_code || error?.payload?.reason_code || '';
}

function activationStateLabel(state) {
  if (state === 'rolling_back') return 'Recovering safely';
  if (state === 'not_completed') return 'Update not completed';
  if (state === 'uncertain') return 'Recovery needs attention';
  return RULE_ACTIVATION_STEPS.find((step) => step.id === state)?.label || 'Preparing';
}

function RulesActivationProgress({ activation, backendReachable }) {
  const state = String(activation?.state || 'pending');
  const previousState = String(activation?.previous_state || '');
  const effectiveState = state === 'not_completed' ? previousState : state;
  const activeIndex = RULE_ACTIVATION_STEPS.findIndex((step) => step.id === effectiveState);
  const succeeded = state === 'active';
  const recovery = state === 'rolling_back';
  const failed = ['not_completed', 'uncertain', 'rolled_back', 'failed'].includes(state);

  return (
    <GlassCard className="lite-rules-activation-card mb-5" data-rules-activation-state={state}>
      <div className="lite-rules-activation-head">
        <div>
          <span>Supervisor proof</span>
          <h2>Updating Safety Rules</h2>
        </div>
        <StatusBadge status={succeeded ? 'healthy' : failed ? 'degraded' : 'review'}>{activationStateLabel(state)}</StatusBadge>
      </div>
      <p className="lite-rules-activation-summary">
        {succeeded
          ? 'Pocket Lab proved the new Rules revision and advanced known-good protection.'
          : failed
            ? 'Pocket Lab did not prove the new revision. The previous known-good protection remains authoritative while recovery is reviewed or retried.'
            : recovery
              ? 'The candidate did not complete verification. Pocket Lab is restoring the previous known-good revision before allowing protected changes.'
              : backendReachable
                ? 'Protected changes stay fail-closed while the supervisor advances each server-reported phase.'
                : 'Fresh supervisor proof is temporarily unavailable. Pocket Lab will not advance this progress view from saved state alone.'}
      </p>
      <ol className="lite-rules-activation-steps" aria-label="Safety Rules update progress" aria-live="polite">
        {RULE_ACTIVATION_STEPS.map((step, index) => {
          const complete = succeeded || (activeIndex >= 0 && index < activeIndex);
          const current = !succeeded && index === activeIndex && !failed;
          const pending = !complete && !current;
          return (
            <li key={step.id} className={`${complete ? 'is-complete' : ''} ${current ? 'is-current' : ''} ${pending ? 'is-pending' : ''}`.trim()} aria-current={current ? 'step' : undefined}>
              <span className="lite-rules-activation-marker" aria-hidden="true">{complete ? '✓' : index + 1}</span>
              <div>
                <strong>{step.label}</strong>
                <small>{step.detail}</small>
              </div>
            </li>
          );
        })}
      </ol>
      <div className="lite-rules-activation-foot" role="status">
        <span>{backendReachable ? 'Current protection check' : 'Waiting for Pocket Lab'}</span>
        {activation?.candidate_revision_id ? <code>{activation.candidate_revision_id}</code> : null}
      </div>
    </GlassCard>
  );
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
    backendDegraded,
  } = policy;
  const [advancedOpen, setAdvancedOpen] = React.useState(false);
  const [manageOpen, setManageOpen] = React.useState(false);
  const [sourceSyncBusy, setSourceSyncBusy] = React.useState(false);
  const [sourceSyncNotice, setSourceSyncNotice] = React.useState(null);
  const [activationStatus, setActivationStatus] = React.useState(null);
  const [activationTracked, setActivationTracked] = React.useState(false);
  const enterpriseEnabled = Boolean(identity.data?.enterprise?.enabled);
  const role = identity.data?.enterprise?.current_membership?.role || identity.data?.person?.role || (identity.data?.person?.is_local_owner ? 'Owner' : '');
  const rulesReadOnly = savedStateOnly || !backendReachable;
  const ready = data?.status === 'ready' && data?.engine?.healthy && data?.engine?.loopback_only;
  const sourceUpdateRequired = Boolean(data?.active_policy?.source_update_required);
  const activationInProgress = Boolean(data?.active_policy?.activation_in_progress) || data?.degraded_reason === 'policy_activation_pending';
  const activationState = String(activationStatus?.state || '');
  const activationBusy = sourceSyncBusy || activationInProgress || RULE_ACTIVATION_NONTERMINAL.has(activationState);
  const recent = Array.isArray(data?.recent_decisions) ? data.recent_decisions.slice(0, 4) : [];
  const templates = Array.isArray(data?.templates) ? data.templates : [];
  const degraded = getLiteReasonPresentation(data?.degraded_reason, data?.summary || 'Safety Rules need attention.');
  const overview = React.useMemo(() => buildLiteRulesOverview(data, {
    savedStateOnly,
    backendReachable,
    lastUpdatedLabel,
    isExpired,
  }), [data, savedStateOnly, backendReachable, lastUpdatedLabel, isExpired]);

  const manageLabel = enterpriseEnabled ? 'Review core Safety Rules' : 'Manage Safety Rules';

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
          setActivationStatus((previous) => ({
            ...(previous || {}),
            previous_state: previous?.state || '',
            state: source.source_update_required ? 'not_completed' : 'active',
          }));
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
      await refresh({ force: true });
    } catch (syncError) {
      const reason = getLiteReasonPresentation(errorCode(syncError), syncError?.message || 'Pocket Lab could not start the Safety Rules update.');
      setSourceSyncNotice({ error: true, title: reason.title, message: reason.message });
    } finally {
      setSourceSyncBusy(false);
    }
  }

  const showActivationProgress = Boolean(activationTracked || activationInProgress || RULE_ACTIVATION_NONTERMINAL.has(activationState));

  return (
    <>
      <PageHeader
        eyebrow="Rules"
        title="Safety Rules"
        description="See what Pocket Lab protects, why an action is allowed or blocked, and what you can do next."
        actions={(
          <div className="lite-governance-inline-actions">
            <LiteHelp helpKey="rules.protection" />
            {activationBusy ? <LiteButton disabled aria-disabled="true">Rules update running</LiteButton> : <LiteRefreshButton scope="rules" refresh={refresh} cacheStatus={cacheStatus} error={error} refreshing={refreshing} />}
          </div>
        )}
      />

      <LiteOperationalStory
        className="lite-rules-operational-story"
        story={overview.workspaceStory}
        primaryAction={!activationBusy && overview.workspaceStory.nextAction?.id === 'refresh' ? { label: 'Refresh Rules', onClick: refresh } : enterpriseEnabled ? { label: 'Review Enterprise protection', onClick: () => document.getElementById('enterprise-rules-heading')?.scrollIntoView({ block: 'start' }) } : null}
        manageAction={!rulesReadOnly ? { label: manageLabel, onClick: () => setManageOpen(true) } : null}
      />
      <LiteFreshness
        saved={savedStateOnly}
        stale={isExpired}
        refreshing={refreshing}
        lastUpdatedLabel={lastUpdatedLabel}
        backendReachable={backendReachable}
      />

      {loading ? <LoadingCard label="Checking your Safety Rules…" /> : null}
      {error && !data ? <StateSurface tone="degraded" title="Safety Rules are temporarily unavailable" description="Pocket Lab could not confirm the latest protection state. Saved information remains visible when available." className="mb-5" /> : null}
      {backendDegraded && backendReachable && !sourceUpdateRequired && !activationInProgress ? <StateSurface tone="degraded" title="Safety Rules need attention" description={degraded.message} className="mb-5" /> : null}
      {sourceSyncNotice ? <StateSurface tone={sourceSyncNotice.error ? 'degraded' : 'neutral'} title={sourceSyncNotice.title} description={sourceSyncNotice.message} className="mb-5" /> : null}

      {showActivationProgress ? <RulesActivationProgress activation={activationStatus || { state: 'pending' }} backendReachable={backendReachable && !savedStateOnly} /> : null}

      {sourceUpdateRequired ? (
        <GlassCard className="lite-rules-card mb-5">
          <div className="lite-rules-card-head"><LiteHelpHeading title="Safety Rules update ready" helpKey="rules.protection" as="h2" /><StatusBadge status="review">{activationBusy ? 'Updating' : 'Owner confirmation'}</StatusBadge></div>
          <p>Pocket Lab has newer Safety Rules ready. Protected changes stay blocked until the update is safely applied and verified.</p>
          {role === 'Owner' && !rulesReadOnly ? <div className="lite-governance-actions"><LiteButton onClick={updateSafetyRules} disabled={activationBusy}>{activationBusy ? 'Update in progress…' : 'Update Safety Rules'}</LiteButton></div> : <p>An active Owner must confirm this Safety Rules update before it can continue.</p>}
        </GlassCard>
      ) : null}

      {activationInProgress && !showActivationProgress ? <StateSurface tone="neutral" title="Safety Rules update in progress" description="Pocket Lab is applying and checking the Safety Rules update. Protected changes stay blocked until the new rules are confirmed or the previous safe rules are restored." className="mb-5" /> : null}

      {!loading && data ? (
        <>
          <section className="lite-rules-key-areas" aria-labelledby="rules-key-areas">
            <div className="lite-rules-key-areas-head"><span>Protection areas</span><div className="lite-governance-title-row"><h2 id="rules-key-areas">What Pocket Lab checks</h2><LiteHelp helpKey="rules.protection" /></div></div>
            {overview.protectedAreas.map((area) => <LiteActionRow key={area.key} label={area.label} value={area.value} summary={area.summary} attention={area.attention} action={!rulesReadOnly ? { label: 'Review', onClick: () => setManageOpen(true) } : null} />)}
            <LiteActionRow label="Recent decisions" value={overview.recentDecisionSummary} summary="This shows why Pocket Lab allowed or blocked an action. The action result is shown separately." action={!rulesReadOnly ? { label: 'Review', onClick: () => setManageOpen(true) } : null} />
          </section>

          <div className="lite-governance-grid mt-5">
            <GlassCard className="lite-governance-card">
              <div className="lite-governance-card-head"><ShieldCheck className="h-5 w-5" /><LiteHelp helpKey="rules.protection" /></div>
              <h2>Protection</h2><strong className="lite-governance-value">{ready ? 'Ready' : 'Needs attention'}</strong>
              <p>{ready ? 'Protected app, device and Identity changes are checked before they continue.' : 'Protected changes stay blocked until Pocket Lab can confirm the current Safety Rules.'}</p>
            </GlassCard>
            <GlassCard className="lite-governance-card">
              <div className="lite-governance-card-head"><FileCheck className="h-5 w-5" /><LiteHelp helpKey="rules.decisions" /></div>
              <h2>Activity</h2><strong className="lite-governance-value">{recent.length ? `${recent.length} recent` : 'No recent decisions'}</strong>
              <p>Recent decisions explain why Pocket Lab allowed or blocked protected actions.</p>
            </GlassCard>
            <GlassCard className="lite-governance-card">
              <div className="lite-governance-card-head"><ShieldCheck className="h-5 w-5" /><LiteHelp helpKey="identity.mode" /></div>
              <h2>Workspace mode</h2><strong className="lite-governance-value">{enterpriseEnabled ? 'Enterprise' : 'Personal'}</strong>
              <p>{enterpriseEnabled ? `${role || 'Your role'} authority and typed governance are active.` : 'The local Owner is the only human authority; Enterprise requests and temporary access are off.'}</p>
            </GlassCard>
          </div>

          {enterpriseEnabled ? (
            <div className="mt-6">
              <StateSurface tone="neutral" title="Core protection + Enterprise governance" description="Core Safety Rules continue to protect important actions. Enterprise Mode adds role-aware controls, review requests and temporary access on top." className="mb-4" />
              <LiteRulesEnterprise role={role} />
            </div>
          ) : (
            <GlassCard className="lite-rules-card mt-6">
              <div className="lite-rules-card-head"><LiteHelpHeading title="Personal Mode protection" helpKey="rules.owner" as="h2" /><StatusBadge status={ready ? 'healthy' : 'degraded'}>{ready ? 'Owner protected' : 'Fail closed'}</StatusBadge></div>
              <p>The local Owner can perform supported administrative actions without another human approval. Explicit confirmation, passkey step-up where required, protected Server Host checks, Rules consistency and audit evidence still apply.</p>
            </GlassCard>
          )}

          <LiteSheet open={manageOpen && !rulesReadOnly} onClose={() => setManageOpen(false)} title="Manage Safety Rules" eyebrow="Safety Rules" description="Review what Pocket Lab protects, recent decisions, and safe technical status." className="lite-rules-manage-sheet">
            <div className="lite-rules-manage-stack">
              <section aria-labelledby="rules-manage-protections">
                <div className="lite-rules-card-head"><LiteHelpHeading title="Protections" helpKey="rules.protection" as="h2" /><StatusBadge status={ready ? 'healthy' : 'degraded'}>{ready ? 'Active' : 'Blocked'}</StatusBadge></div>
                <p>Pocket Lab checks these important actions before they can continue.</p>
                <div className="lite-rules-list">{(data?.policy_groups || []).map((group, index) => <div key={group.id}><span>{index + 1}</span><p><strong>{group.label}</strong><small>{(group.actions || []).map(actionLabel).join(' · ')}</small></p></div>)}</div>
                <div className="lite-identity-checklist"><div><span className="lite-check-dot" /><strong>Safety check first</strong><small>Pocket Lab checks who is acting, what is changing, and whether it is safe.</small></div><div><span className="lite-check-dot" /><strong>Confirmation when needed</strong><small>A passkey or independent review is requested only when the active Safety Rule requires it.</small></div><div><span className="lite-check-dot" /><strong>Safe by default</strong><small>If Pocket Lab cannot confirm a safe decision, the protected change stays blocked.</small></div></div>
              </section>

              <section aria-labelledby="rules-manage-decisions">
                <div className="lite-rules-card-head"><LiteHelpHeading title="Recent protected decisions" helpKey="rules.decisions" as="h2" /><span className="lite-rules-soft-badge">Recent activity</span></div>
                <p>Each item explains why Pocket Lab allowed or blocked a protected action. Action completion is shown separately where that action lives.</p>
                <LiteHistoryTimeline
                  items={recent.map((decision) => { const reason = getLiteReasonPresentation(decision.reason_code, decision.reason_code || 'Decision recorded'); return { id: decision.decision_id, title: `${decision.allow ? 'Allowed' : 'Blocked'} · ${actionLabel(decision.action_id)}`, summary: reason.message || reason.title, time: decision.occurred_at ? formatLiteTime(decision.occurred_at) : 'Recent', state: decision.allow ? 'completed' : 'blocked' }; })}
                  emptyTitle="No protected decisions yet"
                  emptyDescription="A decision will appear after Pocket Lab checks a protected action."
                />
              </section>

              <section aria-labelledby="rules-manage-templates">
                <div className="lite-rules-card-head"><LiteHelpHeading title="Safe protection templates" helpKey="rules.policies" as="h2" /><span className="lite-rules-soft-badge">Server owned</span></div>
                <p>These templates explain the safeguards that are available without exposing internal rule definitions.</p>
                <div className="lite-rules-template-grid">{templates.map((template) => <div key={template.id} className="lite-rules-template-card"><div><strong>{template.label}</strong><StatusBadge status={template.status === 'active' ? 'healthy' : 'neutral'}>{template.status === 'active' ? 'Active' : 'Available'}</StatusBadge></div><p>{template.summary}</p></div>)}{!templates.length ? <StateSurface tone="neutral" title="No safeguard summaries" description="Pocket Lab will show current safe templates here when the server returns them." /> : null}</div>
              </section>

              <LiteTechnicalFacts
                title="Technical details"
                description="Safe operational facts about the current Safety Rules."
                facts={[
                  { id: 'protection', label: 'Protection service', value: ready ? 'Ready' : 'Needs attention', tone: ready ? 'ready' : 'review' },
                  { id: 'scope', label: 'Runs on', value: data?.engine?.loopback_only ? 'This Pocket Lab only' : 'Needs attention' },
                  { id: 'rules-package', label: 'Safety Rules set', value: data?.active_policy?.bundle_ready ? 'Ready' : 'Not ready' },
                  { id: 'information', label: 'Information', value: savedStateOnly ? 'Saved information' : 'Current information' },
                  { id: 'updated', label: 'Last update', value: lastUpdatedLabel || 'Just now' },
                ]}
              />
            </div>
          </LiteSheet>
        </>
      ) : null}
    </>
  );
}