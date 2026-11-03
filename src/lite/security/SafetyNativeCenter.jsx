import React, { useEffect, useRef } from 'react';
import {
  Activity, AlertTriangle, ArrowLeft, ChevronRight, CircleHelp,
  FileCheck2, GitCompareArrows, History, ListChecks, ScanLine, Settings2,
  ShieldAlert, ShieldCheck, WifiOff,
} from 'lucide-react';
import { LiteButton } from '../LiteUi.jsx';
import './safetyCenter.css';

// The Safety overview only receives values already selected from FastAPI-derived
// state by LiteSecurity. A missing score, tool outcome, or scope is never "safe".
export function SafetyCenterHero({
  status, profile, reportedScore, score, hasRun, freshness, saved, offline,
  findings, coverageReported, checkedCount, coverageQuality, evidenceSaved,
  busy, writeBlocked, blockedReason, onQuickCheck, onOpenChecks,
}) {
  const scoreLabel = reportedScore && Number.isFinite(Number(score))
    ? Math.round(Number(score))
    : null;
  const reviewLabel = hasRun ? String(findings) : 'Not checked';
  const coverageLabel = !coverageReported ? 'Not reported'
    : coverageQuality === 'incomplete' ? 'Incomplete coverage'
    : String(checkedCount) + ' checked';
  const evidenceLabel = !hasRun ? 'Not available' : evidenceSaved ? 'Saved' : 'Not confirmed';
  const actionUnavailable = Boolean(busy || writeBlocked);
  return (
    <section className="lite-safety-native-hero" aria-label="Safety overview" data-safety-native-hero="true"
      data-safety-reporting={scoreLabel === null ? 'unreported' : 'reported'}>
      <div className="lite-safety-native-hero-main">
        <div className="lite-safety-native-eyebrow"><ShieldCheck size={19} aria-hidden="true" /> Safety overview</div>
        <h2>{status || 'Safety status unavailable'}</h2>
        <p className="lite-safety-native-profile">{profile || 'Quick Scan'} · {freshness || 'No saved check yet'}</p>
        {saved || offline ? <p className="lite-safety-native-freshness" role="status">
          {offline ? <WifiOff size={17} aria-hidden="true" /> : <CircleHelp size={17} aria-hidden="true" />}
          {offline ? 'Offline — showing saved information' : 'Showing saved result — confirm freshness before acting'}
        </p> : null}
        <dl className="lite-safety-native-stats">
          <div><dt>Items to review</dt><dd>{reviewLabel}</dd></div>
          <div><dt>Coverage</dt><dd>{coverageLabel}</dd></div>
          <div><dt>Evidence</dt><dd>{evidenceLabel}</dd></div>
        </dl>
        <div className="lite-safety-native-hero-actions">
          <LiteButton tone="primary" haptic onClick={onQuickCheck} disabled={actionUnavailable}
            ariaLabel={busy ? 'Safety check already in progress' : writeBlocked ? 'Reconnect to run Quick Scan' : 'Run Quick Scan'}>
            <ScanLine size={18} aria-hidden="true" /> {busy ? 'Check in progress' : writeBlocked ? 'Reconnect to check' : 'Run Quick Scan'}
          </LiteButton>
          {writeBlocked && blockedReason ? <small role="status">{blockedReason}</small> : null}
          <button type="button" className="lite-safety-native-text-link" onClick={onOpenChecks}>
            Other checks in Manage Safety <ChevronRight size={16} aria-hidden="true" />
          </button>
        </div>
      </div>
      <div className="lite-safety-native-score" role="img" aria-label={scoreLabel === null ? 'Safety score not reported' : 'Reported safety score ' + scoreLabel}>
        <span>Reported score</span>
        <strong>{scoreLabel === null ? '—' : scoreLabel}</strong>
        <small>{scoreLabel === null ? 'No score available for this profile' : 'Based on reported check coverage'}</small>
      </div>
    </section>
  );
}

const DESTINATIONS = [
  { id: 'issues', label: 'Needs Attention', description: 'Review reported findings and recommended next steps', Icon: ShieldAlert },
  { id: 'coverage', label: 'Coverage & Checks', description: 'See checked scope, tool outcomes and exclusions', Icon: ListChecks },
  { id: 'history', label: 'Recent Activity', description: 'Review latest and previous saved results', Icon: History },
];

export function SafetyDestinations({ onOpen, hasRun, findings, coverageReported, lastChecked }) {
  return <nav className="lite-safety-native-destinations" aria-label="Safety destinations" data-safety-native-destinations="true">
    {DESTINATIONS.map(({ id, label, description, Icon }) =>
      <button key={id} type="button" className="lite-safety-native-destination" onClick={() => onOpen(id)}
        aria-label={'Open ' + label}>
        <span className="lite-safety-native-destination-icon"><Icon size={20} aria-hidden="true" /></span>
        <span className="lite-safety-native-destination-copy">
          <strong>{label}</strong>
          <small>{description}</small>
          {id === 'issues' && hasRun ? <small>{findings} reported for selected profile</small> : null}
          {id === 'coverage' && !coverageReported ? <small>Scope not reported</small> : null}
          {id === 'history' && lastChecked ? <small>{lastChecked}</small> : null}
        </span>
        <ChevronRight size={19} aria-hidden="true" />
      </button>)}
  </nav>;
}

const ICONS = {
  overview: ShieldCheck, issues: AlertTriangle, coverage: ListChecks,
  checks: ScanLine, changes: GitCompareArrows, history: History,
  evidence: FileCheck2, check_path: Activity, technical_details: Settings2,
};
const GROUPS = [
  { name: 'Review', ids: ['overview', 'issues', 'coverage'] },
  { name: 'Operations', ids: ['checks', 'changes', 'history', 'evidence', 'check_path', 'technical_details'] },
];

// Index/detail is display state only. The selected section remains in the
// existing Zustand store; no backend authority is copied into this component.
export function SafetyManageNavigation({ sections, descriptions, selected, mobileDetailOpen, onChoose, onBack, children }) {
  const titleRef = useRef(null);
  const selectedRowRef = useRef(null);
  const lastDetailOpen = useRef(mobileDetailOpen);
  useEffect(() => {
    if (lastDetailOpen.current === mobileDetailOpen) return;
    if (mobileDetailOpen) titleRef.current?.focus({ preventScroll: true });
    else selectedRowRef.current?.focus({ preventScroll: true });
    lastDetailOpen.current = mobileDetailOpen;
  }, [mobileDetailOpen]);

  const selectedItem = sections.find((section) => section.id === selected) || sections[0];
  return <div className="lite-safety-native-workspace" data-safety-manage-view={mobileDetailOpen ? 'section' : 'index'}
    data-safety-manage-selected={selected}>
    <nav className="lite-safety-native-index" aria-label="Manage Safety sections" data-safety-manage-index="true">
      {GROUPS.map((group) => <div className="lite-safety-native-group" key={group.name}>
        <h2>{group.name}</h2>
        <div className="lite-safety-native-navigation">
          {group.ids.map((id) => {
            const section = sections.find((entry) => entry.id === id);
            if (!section) return null;
            const Icon = ICONS[id] || ShieldCheck;
            return <button key={id} type="button" className="lite-safety-native-nav-row"
              ref={selected === id ? selectedRowRef : null}
              aria-current={selected === id ? 'page' : undefined}
              aria-label={'Open ' + section.label + ' in Manage Safety'}
              onClick={() => onChoose(id)}>
              <Icon size={19} aria-hidden="true" />
              <span><strong>{id === 'checks' ? 'Run Checks' : id === 'issues' ? 'Findings' : section.label}</strong>
                <small>{descriptions[id]}</small></span>
              <ChevronRight size={18} aria-hidden="true" />
            </button>;
          })}
        </div>
      </div>)}
    </nav>
    <div className="lite-safety-native-detail" data-safety-manage-detail="true">
      <button type="button" className="lite-safety-native-back" onClick={onBack}>
        <ArrowLeft size={18} aria-hidden="true" /> Back to Manage Safety
      </button>
      <header className="lite-safety-native-detail-heading">
        <h2 tabIndex={-1} ref={titleRef}>{selectedItem?.id === 'checks' ? 'Run Checks' : selectedItem?.label}</h2>
        <p>{descriptions[selected] || 'Review Safety information'}</p>
      </header>
      <div className="lite-safety-native-detail-content">{children}</div>
    </div>
  </div>;
}
