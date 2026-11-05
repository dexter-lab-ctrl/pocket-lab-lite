import React from 'react';
import { BadgeCheck, DatabaseBackup, ScanEye, ArchiveRestore, ShieldAlert, History, Clock3 } from 'lucide-react';
import { GlassCard, LiteButton } from '../LiteUi.jsx';
import { formatLiteTime } from '../../lib/liteApi.js';

const ICONS = { backup: DatabaseBackup, verification: BadgeCheck, verify: BadgeCheck, preview: ScanEye, restore: ArchiveRestore, checkpoint: History };
export default function RecoveryPremiumTimeline({ items = [], unavailable = false, saved = false, onViewActivity }) {
  const item = items[0] || null;
  const Icon = item?.state === 'failed' ? ShieldAlert : ICONS[item?.kind] || Clock3;
  return <GlassCard className="lite-recovery-recent-activity" aria-label="Recent Activity" data-recovery-activity="compact">
    <header className="lite-recovery-recent-head">
      <div><h2>Recent Activity</h2><p>{saved || unavailable ? 'Live activity is not confirmed.' : 'Most recent reported record'}</p></div>
      <LiteButton tone="secondary" haptic onClick={onViewActivity} ariaLabel="View all recovery activity">View all activity</LiteButton>
    </header>
    {item ? <div className="lite-recovery-recent-event" data-recovery-activity-state={item.state}>
      <span className="lite-recovery-recent-icon" aria-hidden="true"><Icon size={20}/></span>
      <div><strong>{item.title}</strong><p>{item.summary}</p>
        <small>{item.time ? <time dateTime={item.time}>{formatLiteTime(item.time)}</time> : 'Time not reported'} · {item.state.replace(/_/g, ' ')}</small>
        {item.origin === 'snapshot' ? <small>Current record, not a separate historical event</small> : null}
      </div>
    </div> : <p className="lite-recovery-recent-empty">{unavailable || saved ? 'Recovery activity cannot be confirmed while offline or outdated.' : 'No recovery activity yet. Create a backup to begin.'}</p>}
  </GlassCard>;
}
