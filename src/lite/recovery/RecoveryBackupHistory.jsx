import React, { memo, useMemo } from 'react';
import { formatLiteTime } from '../../lib/liteApi.js';
import LiteHistorySection from '../components/LiteHistorySection.jsx';
import { GlassCard, StatusBadge } from '../LiteUi.jsx';

const RECOVERY_HISTORY_SECTION_LAZY_BY_DEFAULT = true;
const RECOVERY_HISTORY_NO_ALWAYS_RENDERED_ROWS = true;
void RECOVERY_HISTORY_SECTION_LAZY_BY_DEFAULT;
void RECOVERY_HISTORY_NO_ALWAYS_RENDERED_ROWS;

function safeHistoryItems(history = [], latestPreviewReady = false) {
  return (Array.isArray(history) ? history : [])
    .filter(Boolean)
    .map((backup) => ({
      id: backup.backup_id || backup.id || backup.snapshot_id,
      title: backup.verification_status === 'verified' ? 'Backup verified and ready' : backup.summary || 'Backup created',
      meta: [
        backup.created_at ? formatLiteTime(backup.created_at) : '',
        backup.engine || 'restic',
        `${backup.included_file_count || 0} item(s)`,
        backup.verification_status === 'verified' ? 'Verified' : 'Needs verification',
        latestPreviewReady ? 'Preview ready' : '',
      ].filter(Boolean).join(' · '),
    }))
    .filter((item) => item.id)
    .slice(0, 12);
}

const RecoveryBackupHistory = memo(function RecoveryBackupHistory({ history = [], latestPreviewReady = false, savedStateOnly = false }) {
  const items = useMemo(() => safeHistoryItems(history, latestPreviewReady), [history, latestPreviewReady]);

  return (
    <GlassCard className="lite-recovery-card mt-4 lite-recovery-history-card" data-recovery-history-lazy="true">
      <div className="lite-recovery-card-head">
        <div>
          <h2>Backup history</h2>
          <p>Available restore points appear here only when opened.</p>
        </div>
        <StatusBadge status={items.length ? 'healthy' : 'unknown'}>{items.length} saved</StatusBadge>
      </div>
      <LiteHistorySection
        title="Backup history"
        summary={items.length ? `${items.length} saved restore point${items.length === 1 ? '' : 's'} available.` : 'History will appear after your first backup.'}
        items={items}
        enabled
        savedState={savedStateOnly}
        emptyMessage="Use Backup Now to create your first encrypted local backup."
      />
    </GlassCard>
  );
});

export default RecoveryBackupHistory;
