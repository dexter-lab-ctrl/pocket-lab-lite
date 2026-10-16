import React from 'react';
import { BadgeCheck, DatabaseBackup, ScanEye, ArchiveRestore, ShieldAlert, History, Clock3 } from 'lucide-react';
import { GlassCard, LiteButton } from '../LiteUi.jsx';
import { formatLiteTime } from '../../lib/liteApi.js';

const ICONS = { backup: DatabaseBackup, verification: BadgeCheck, verify: BadgeCheck, preview: ScanEye, restore: ArchiveRestore, checkpoint: History };
export default function RecoveryPremiumTimeline({ items = [], unavailable = false, saved = false, onViewActivity }) {
  return <GlassCard className="lite-recovery-premium-timeline" aria-label="Recent Activity">
    <header><span className="lite-recovery-premium-eyebrow">Recent Activity</span><h2>Recovery records</h2><p>{saved || unavailable ? 'Live activity is not available. Refresh to confirm the latest records.' : 'A short view of reported activity and available recovery records.'}</p></header>
    {items.length ? <ol className="lite-recovery-premium-timeline-list" aria-label="Recent Recovery records">
      {items.map((item) => {
        const Icon = item.state === 'failed' ? ShieldAlert : ICONS[item.kind] || Clock3;
        return <li key={item.id} data-recovery-activity-state={item.state}>
          <span className="lite-recovery-premium-timeline-icon" aria-hidden="true"><Icon size={19} /></span>
          <div><strong>{item.title}</strong><span>{item.summary}</span>
            <small>{item.time ? <time dateTime={item.time}>{formatLiteTime(item.time)}</time> : 'Time not reported'} · {item.state.replace(/_/g, ' ')}</small>
            {item.origin === 'snapshot' ? <small>Current record, not a separate historical event</small> : null}
          </div>
        </li>;
      })}
    </ol> : <p className="lite-recovery-premium-timeline-empty">{unavailable || saved ? 'Recovery activity cannot be confirmed while offline or outdated.' : 'No recovery activity yet. Create your first backup to begin building recovery history.'}</p>}
    <LiteButton tone="secondary" onClick={onViewActivity}>View Activity</LiteButton>
  </GlassCard>;
}