import React, { useState } from 'react';
import { AlertCircle, Clock3, Info, History, CheckCircle2 } from 'lucide-react';
import { StateSurface } from '../../components/ui.jsx';
import { formatActivityCount } from '../homeActivityEvidence.js';

const sections = [
  ['attention', 'Attention'], ['running', 'Running'], ['recent', 'Recent'], ['history', 'History'],
];
const running = new Set(['running', 'working', 'in_progress']);
const destination = { security: 'Safety', apps: 'Apps', devices: 'Devices', recovery: 'Recovery' };

function ActivityNotice({ title, children, tone = 'info', icon: Icon = Info }) {
  return <aside className={`lite-home-activity-notice is-${tone}`} aria-label={title}>
    <Icon size={19} aria-hidden="true" />
    <div><strong>{title}</strong><p>{children}</p></div>
  </aside>;
}

function ActivityTime({ value }) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return <span className="lite-home-activity-time">Time not available</span>;
  return <time className="lite-home-activity-time" dateTime={date.toISOString()}>{date.toLocaleString()}</time>;
}

function ActivityEvents({ events, label, onNavigate }) {
  if (!events.length) return <StateSurface tone="empty" title={`No ${label.toLowerCase()} events in this sample`}
    description="Only the bounded recent sample is shown. Other operations may exist outside this window."
    className="lite-home-activity-state" />;
  return <ol className="lite-home-activity-timeline" aria-label={`${label} events`}>
    {events.map((event, index) => <li key={`${event.domain}-${event.at}-${index}`}>
      <div className="lite-home-event-copy">
        <strong>{event.label}</strong>
        <span className="lite-home-event-status">{event.statusLabel}</span>
        <ActivityTime value={event.at} />
      </div>
      {destination[event.domain] ? <button type="button"
        aria-label={`Open ${destination[event.domain]} for ${event.label}`}
        onClick={() => onNavigate?.(event.domain)}>Open {destination[event.domain]}</button> : null}
    </li>)}
  </ol>;
}

export default function HomeActivityDetails({
  activity, navigation, cursor, cursorBusy, cursorError, saved, onMarkReviewed, onNavigate,
}) {
  const [section, setSection] = useState('attention');
  const events = activity?.events || [];
  const lists = {
    attention: events.filter((event) => event.needsAttention),
    running: events.filter((event) => running.has(event.status)),
    recent: events.slice(0, 4),
    history: events,
  };
  return <div className="lite-home-activity-details">
    <nav ref={navigation?.navRef} className="lite-home-details-nav lite-home-activity-tabs"
      aria-label="Activity sections" data-tabs-hidden={navigation?.hidden ? 'true' : 'false'}
      data-tabs-scrolled={navigation?.scrolled ? 'true' : 'false'}>
      {sections.map(([key, label]) => <button type="button" key={key}
        aria-current={section === key ? 'page' : undefined}
        onClick={() => { navigation?.reveal(true); setSection(key); }}>{label}</button>)}
    </nav>
    {!activity ? <StateSurface tone="unavailable" title="Activity unavailable"
      description="Activity information is not available. No successful or running action is assumed."
      className="lite-home-activity-state" /> :
      <div className="lite-home-activity-content">
        <dl className="lite-home-activity-counts">
          <div><dt>Running now</dt><dd>{formatActivityCount(activity.active)}</dd></div>
          <div><dt>Waiting / queued</dt><dd>{formatActivityCount(activity.queued)}</dd></div>
          <div><dt>Completed</dt><dd>{formatActivityCount(activity.completed)}</dd></div>
          <div><dt>Needs review</dt><dd>{formatActivityCount(activity.attention)}</dd></div>
        </dl>
        <ActivityNotice title="Activity time window" icon={Clock3}>
          {activity.runningWindowMinutes !== null && activity.runningWindowMinutes !== undefined
            ? `Running and waiting: updated within the last ${activity.runningWindowMinutes} minutes. Older unfinished records are not confirmed running.`
            : 'Running window not reported.'}
          {' '}
          {activity.historyWindowDays !== null && activity.historyWindowDays !== undefined
            ? `Completions and historical failures: last ${activity.historyWindowDays} days.`
            : 'History window not reported.'}
        </ActivityNotice>
        {activity.stale !== null && activity.stale > 0 ? <ActivityNotice title="Older unfinished operations" tone="warning" icon={AlertCircle}>
          {formatActivityCount(activity.stale)} older unfinished records require lifecycle verification.
        </ActivityNotice> : null}
        {section === 'attention' ? <ActivityNotice title="How attention is counted">
          {activity.attentionScope === 'explicit_active_flags_only'
            ? 'Only issues explicitly marked active by the backend are counted as unresolved. Historical failures are shown separately.'
            : 'Unresolved issue classification is not available from this source.'}
        </ActivityNotice> : null}
        {section === 'history' && activity.historicalFailures !== null ? <ActivityNotice title="Historical failures" tone="warning" icon={History}>
          Historical failures {activity.historyWindowDays ? `in the last ${activity.historyWindowDays} days` : 'in the reported history window'}: {formatActivityCount(activity.historicalFailures)}. A failed record does not prove an issue is still unresolved.
        </ActivityNotice> : null}
        {section === 'attention' && activity.grouped?.length ? <>
          <ActivityNotice title="Historical patterns">
            Historical patterns to review — not automatically unresolved incidents.
          </ActivityNotice>
          <ol className="lite-home-activity-timeline" aria-label="Grouped historical patterns">
            {activity.grouped.map((group, index) => <li key={`${group.domain}-${group.at}-${index}`}>
              <div className="lite-home-event-copy"><strong>{group.label}</strong><span>{group.summary}</span><ActivityTime value={group.at} /></div>
              {destination[group.domain] ? <button type="button" onClick={() => onNavigate?.(group.domain)}
                aria-label={`Review ${destination[group.domain]} for ${group.label}`}>Review {destination[group.domain]}</button> : null}
            </li>)}
          </ol>
        </> : null}
        <ActivityEvents events={lists[section]} label={sections.find(([key]) => key === section)?.[1] || section}
          onNavigate={onNavigate} />
        {section === 'history' ? <section className="lite-home-personal-review" aria-label="Personal activity review">
          <div className="lite-home-review-heading">
            <CheckCircle2 size={20} aria-hidden="true" />
            <div><h3>Personal activity review</h3><p>Private review position and status</p></div>
          </div>
          {cursor?.last_reviewed_at ? <p>Last reviewed: <ActivityTime value={cursor.last_reviewed_at} /></p> : null}
          {cursor?.changed_since_review ? <p className="lite-home-review-changed">Something changed since your last review.</p> : null}
          {!cursor?.changed_since_review && cursor ? <p>Nothing new reported since your last review.</p> : null}
          <p>Marking history reviewed changes only your private review position. It does not resolve an issue, approve work, clear audit history or retry an action.</p>
          {cursor?.changed_since_review ? <button type="button"
            disabled={Boolean(saved || cursorBusy)} aria-busy={cursorBusy || undefined}
            onClick={onMarkReviewed}>{cursorBusy ? 'Saving review…' : 'Mark activity reviewed'}</button> : null}
          {saved ? <ActivityNotice title="Saved information">Reconnect to confirm a new review position.</ActivityNotice> : null}
          {cursorError ? <StateSurface tone="error" title="Review history unavailable" description={cursorError}
            className="lite-home-activity-state" /> : null}
          {!cursor && !cursorError ? <StateSurface tone="unavailable" title="Review status not available"
            description="Review history couldn't be loaded or is still checking."
            className="lite-home-activity-state" /> : null}
        </section> : null}
      </div>}
  </div>;
}
