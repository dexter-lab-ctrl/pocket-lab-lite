import React, { useState } from 'react';
import { formatActivityCount } from '../homeActivityEvidence.js';
const sections = [
  ['attention','Attention'],['running','Running'],['recent','Recent'],['history','History'],
];
const failures = new Set(['failed','timed_out','error','blocked','undeliverable','degraded']);
const running = new Set(['running','working','in_progress']);
export default function HomeActivityDetails({ activity, cursor, cursorBusy, cursorError, saved, onMarkReviewed, onNavigate }) {
  const [section, setSection] = useState('attention');
  const events = activity?.events || [];
  const lists = {
    attention: events.filter((event) => event.needsAttention),
    running: events.filter((event) => running.has(event.status)),
    recent: events.slice(0, 4),
    history: events,
  };
  return <div className="lite-home-activity-details">
    <nav className="lite-home-details-nav" aria-label="Activity sections">
      {sections.map(([key, label]) => <button type="button" key={key}
        aria-current={section === key ? 'page' : undefined} onClick={() => setSection(key)}>{label}</button>)}
    </nav>
    {!activity ? <p role="status">Activity information is not available. No successful or running action is assumed.</p> :
      <div className="lite-home-activity-content">
        <dl className="lite-home-activity-counts">
          <div><dt>Running now</dt><dd>{formatActivityCount(activity.active)}</dd></div>
          <div><dt>Waiting / queued</dt><dd>{formatActivityCount(activity.queued)}</dd></div>
          <div><dt>Completed recently</dt><dd>{formatActivityCount(activity.completed)}</dd></div>
          <div><dt>Needs review</dt><dd>{formatActivityCount(activity.attention)}</dd></div>
        </dl>
        <p className="lite-home-muted">{activity.runningWindowMinutes ? 'Running and waiting: updated within the last 30 minutes. Older unfinished records are not confirmed running.' : 'Running window not reported.'}
          {' '}{activity.historyWindowDays ? 'Completions and historical failures: last 7 days.' : 'History window not reported.'}</p>
        {activity.stale !== null && activity.stale > 0 ? <p>{formatActivityCount(activity.stale)} older unfinished records require lifecycle verification.</p> : null}
        {section === 'attention' && activity.attentionScope === 'explicit_active_flags_only' ?
          <p>Only issues explicitly marked active by the backend are counted as unresolved. Historical failures are shown separately.</p> : null}
        {section === 'attention' && activity.attentionScope !== 'explicit_active_flags_only' ?
          <p>Unresolved issue classification is not available from this source.</p> : null}
        {section === 'history' && activity.historicalFailures !== null ?
          <p>Historical failures in the last 7 days: {formatActivityCount(activity.historicalFailures)}. A failed record does not prove an issue is still unresolved.</p> : null}
        {section === 'attention' && activity.grouped.length ? <p>Historical patterns to review — not automatically unresolved incidents.</p> : null}
        {section === 'attention' && activity.grouped.length ?
          <ol className="lite-home-activity-timeline">
            {activity.grouped.map((group, index) => <li key={group.domain + '-' + group.at + '-' + index}>
              <strong>{group.label}</strong><span>{group.summary}</span>
              <button type="button" onClick={() => onNavigate(group.domain)}>Review {group.domain === 'security' ? 'Safety' : group.domain === 'apps' ? 'Apps' : group.domain === 'devices' ? 'Devices' : 'Recovery'}</button>
            </li>)}
          </ol> : null}
        {lists[section].length ? <ol className="lite-home-activity-timeline" aria-label={sections.find(([key]) => key === section)?.[1] + ' events'}>
          {lists[section].map((event, index) => <li key={event.domain + '-' + event.at + '-' + index}>
            <strong>{event.label}</strong><span>{event.statusLabel}</span>
            <time dateTime={new Date(event.at).toISOString()}>{new Date(event.at).toLocaleString()}</time>
            <button type="button" onClick={() => onNavigate(event.domain)}>Open {event.domain === 'security' ? 'Safety' : event.domain === 'apps' ? 'Apps' : event.domain === 'devices' ? 'Devices' : 'Recovery'}</button>
          </li>)}
        </ol> : <p>No {section} events in the bounded recent sample.</p>}
        {section === 'history' ? <div className="lite-home-personal-review">
          <h3>Personal activity review</h3>
          {cursor?.last_reviewed_at ? <p>Last reviewed: {new Date(cursor.last_reviewed_at).toLocaleString()}</p> : null}
          {cursor?.changed_since_review ? <p>Something changed since your last review.</p> : null}
          <p>Marking history reviewed changes only your private review position. It does not resolve an issue, approve work, clear audit history or retry an action.</p>
          {cursor?.changed_since_review ? <button type="button" disabled={saved || cursorBusy} onClick={onMarkReviewed}>
            {cursorBusy ? 'Saving review…' : 'Mark activity reviewed'}</button> : null}
          {cursorError ? <p role="status">{cursorError}</p> : null}
          {!cursor && !cursorError ? <p>Review history couldn't be loaded or is still checking.</p> : null}
        </div> : null}
      </div>}
  </div>;
}
