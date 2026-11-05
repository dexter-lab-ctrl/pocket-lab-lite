import React, { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { formatLiteTime, liteApi } from '../../lib/liteApi.js';
import { liteQueryKeys } from '../../lib/liteQueryClient.js';
import { selectRecoveryHistorySnapshotView } from '../../lib/liteViewModels.js';
import { useLiteQuery } from '../../hooks/useLiteQuery.js';
import LiteHistorySection from '../components/LiteHistorySection.jsx';
import { GlassCard, LiteButton, StatusBadge } from '../LiteUi.jsx';

const RECOVERY_HISTORY_SECTION_LAZY_BY_DEFAULT = true;
const RECOVERY_HISTORY_NO_ALWAYS_RENDERED_ROWS = true;
const RECOVERY_HISTORY_CURSOR_PAGINATION_R3 = true;
void RECOVERY_HISTORY_SECTION_LAZY_BY_DEFAULT;
void RECOVERY_HISTORY_NO_ALWAYS_RENDERED_ROWS;
void RECOVERY_HISTORY_CURSOR_PAGINATION_R3;

export function recoveryHistoryEligibility({ backup = {}, selectedBackupId = '', preview = null, saved = false } = {}) {
  const backupId = backup?.backup_id || backup?.id || backup?.snapshot_id || '';
  const locationStatus = String(backup?.location?.status || '').toLowerCase();
  const locationUnavailable = backup?.location?.available === false
    || ['missing', 'read_only', 'low_space', 'unavailable', 'repository_missing', 'repository_invalid'].includes(locationStatus);
  const verified = backup?.verification_status === 'verified';
  const selected = Boolean(backupId && backupId === selectedBackupId);
  const previewMatches = Boolean(backupId && preview?.preview_id && preview?.backup_id === backupId
    && preview?.status === 'ready' && preview?.restore_allowed !== false);
  const canRecover = !saved && verified && selected && previewMatches && !locationUnavailable;
  const reason = saved ? 'Live recovery state is unavailable.'
    : !selected ? 'Select this backup to review restoration.'
    : !verified ? 'Verify this backup before restoring.'
    : locationUnavailable ? 'Reconnect the backup destination.'
    : !previewMatches ? 'Prepare a fresh matching restore preview.'
    : 'Review the consequences before confirming.';
  return { selected, verified, previewMatches, locationUnavailable, canRecover, reason };
}

export function recoveryHistoryItems(history = [], latestPreview = null) {
  return (Array.isArray(history) ? history : [])
    .filter(Boolean)
    .map((backup) => {
      const id = backup.backup_id || backup.id || backup.snapshot_id;
      const previewReady = Boolean(latestPreview?.preview_id
        && latestPreview.backup_id === id
        && latestPreview.status === 'ready'
        && latestPreview.restore_allowed !== false);
      return {
        id,
        title: backup.verification_status === 'verified' ? 'Backup verified' : backup.summary || 'Backup created',
        meta: [
        backup.created_at ? formatLiteTime(backup.created_at) : '',
        `${backup.included_file_count || 0} item(s)`,
        backup.verification_status === 'verified' ? 'Verified' : 'Needs verification',
        backup.location?.display_name ? `From ${backup.location.display_name}` : '',
        previewReady ? 'Preview ready' : '',
        ].filter(Boolean).join(' · '),
      };
    })
    .filter((item) => item.id);
}

function formatSize(bytes) {
  const value = Number(bytes || 0);
  if (!value) return 'Size unavailable';
  return value >= 1024 * 1024 ? `${(value / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(value / 1024))} KB`;
}

const RecoveryBackupHistory = memo(function RecoveryBackupHistory({ initialHistory = [], latestPreview = null, savedStateOnly = false, selectedBackupId = '', onSelectBackup, onVerify, onPreview, onRecover, selectionOnly = false }) {
  const [cursor, setCursor] = useState('');
  const [pageOrder, setPageOrder] = useState(['first']);
  const [pageItems, setPageItems] = useState({ first: Array.isArray(initialHistory) ? initialHistory : [] });
  const requestedCursorsRef = useRef(new Set());
  const path = `/api/lite/recovery/backups?limit=10${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`;
  const query = useLiteQuery({
    queryKey: liteQueryKeys.recoveryHistoryPage(10, cursor),
    path,
    queryFn: () => liteApi.recoveryHistory(10, cursor),
    staleTime: 15_000,
    refetchInterval: false,
    pollingMode: 'slow',
    refetchOnWindowFocus: false,
    snapshotSelect: cursor ? undefined : selectRecoveryHistorySnapshotView,
  });

  useEffect(() => {
    const backups = Array.isArray(query.data?.backups) ? query.data.backups : null;
    if (!backups) return;
    const key = cursor || 'first';
    setPageItems((current) => ({ ...current, [key]: backups }));
    setPageOrder((current) => current.includes(key) ? current : [...current, key]);
  }, [cursor, query.data]);

  const history = useMemo(() => {
    const seen = new Set();
    return pageOrder.flatMap((key) => pageItems[key] || []).filter((backup) => {
      const id = backup?.backup_id || backup?.id || backup?.snapshot_id;
      if (!id || seen.has(id)) return false;
      seen.add(id);
      return true;
    }).sort((a, b) => {
      const aTime = Date.parse(a.created_at || '') || 0;
      const bTime = Date.parse(b.created_at || '') || 0;
      return bTime - aTime;
    });
  }, [pageItems, pageOrder]);
  const items = useMemo(() => recoveryHistoryItems(history, latestPreview), [history, latestPreview]);
  const nextCursor = String(query.data?.next_cursor || '');
  const hasMore = Boolean(!query.savedStateOnly && query.data?.has_more && nextCursor);
  const historySavedStateOnly = Boolean(savedStateOnly || query.savedStateOnly);
  const loadMore = useCallback(() => {
    if (!nextCursor || historySavedStateOnly || query.refreshing || requestedCursorsRef.current.has(nextCursor)) return;
    requestedCursorsRef.current.add(nextCursor);
    setCursor(nextCursor);
  }, [historySavedStateOnly, nextCursor, query.refreshing]);

  useEffect(() => {
    if (query.error && cursor) requestedCursorsRef.current.delete(cursor);
  }, [cursor, query.error]);

  return (
    <GlassCard className="lite-recovery-card lite-recovery-history-card lite-recovery-point-library" data-recovery-history-lazy="true" data-recovery-history-r3="cursor">
      <div className="lite-recovery-card-head">
        <div>
          <h3>Restore Point Library</h3>
          <p>Choose a recorded restore point. Selection is not a restore request.</p>
        </div>
        <StatusBadge status={items.length ? 'healthy' : query.loading ? 'checking' : 'unknown'}>{items.length} saved</StatusBadge>
      </div>
      <LiteHistorySection
        title="Browse restore points"
        initiallyOpen={selectionOnly}
        summary={items.length ? `${items.length} saved restore point${items.length === 1 ? '' : 's'} loaded.` : query.loading ? 'Loading backup history…' : 'History will appear after your first backup.'}
        items={items}
        enabled
        savedState={historySavedStateOnly}
        emptyMessage={query.error ? 'Backup history could not be loaded. Retry when Pocket Lab is reachable.' : 'Use Backup Now to create your first encrypted local backup.'}
        domain="recoveryHistory"
        datasetKey="recovery:backups"
        hasMore={hasMore}
        loadingMore={query.refreshing && Boolean(cursor)}
        onLoadMore={loadMore}
      >
        <div className="lite-recovery-history-action-list" aria-label="Timestamped restore points">
          {history.length ? history.map((backup) => {
            const id = backup.backup_id || backup.id || backup.snapshot_id;
            const eligibility = recoveryHistoryEligibility({
              backup, selectedBackupId, preview: latestPreview, saved: historySavedStateOnly,
            });
            const { selected, verified, locationUnavailable, canRecover } = eligibility;
            return <article key={id} className={`lite-recovery-history-action-row${selected ? ' is-selected' : ''}`}
              data-restore-point-state={locationUnavailable ? 'unavailable' : verified ? 'verified' : 'verification-required'}>
              <button type="button" className="lite-recovery-history-select" onClick={() => onSelectBackup?.(backup)} aria-pressed={selected}>
                <strong>{backup.created_at ? formatLiteTime(backup.created_at) : 'Timestamp unavailable'}</strong>
                <span>{backup.backup_type || backup.kind || 'Workspace backup'} · {verified ? 'Verified' : 'Verification needed'}</span>
                <small>{backup.location?.display_name || 'Location not reported'} · {formatSize(backup.size_bytes)}</small>
                {locationUnavailable ? <small>Destination unavailable</small> : null}
                {selected ? <small>{eligibility.reason}</small> : null}
              </button>
              {selected && !selectionOnly ? <div className="lite-recovery-point-details" aria-label="Selected restore point details">
                <strong>Selected restore point</strong>
                <p>{eligibility.reason}</p>
                <div className="lite-recovery-history-row-actions">
                  <LiteButton tone="secondary" onClick={() => onVerify?.(backup)} disabled={!id || locationUnavailable || historySavedStateOnly}>Verify</LiteButton>
                  <LiteButton tone="secondary" onClick={() => onPreview?.(backup)} disabled={!id || !verified || locationUnavailable || historySavedStateOnly}>Preview</LiteButton>
                  <LiteButton tone="danger" onClick={() => onRecover?.(backup)} disabled={!canRecover}>Review Restore</LiteButton>
                </div>
              </div> : null}
            </article>;
          }) : <p>{query.loading ? 'Loading backup history…' : 'No timestamped restore points yet.'}</p>}
        </div>
      </LiteHistorySection>
      {query.error ? (
        <div className="lite-recovery-history-actions">
          <LiteButton tone="secondary" onClick={query.refresh}>Retry</LiteButton>
        </div>
      ) : null}
    </GlassCard>
  );
});

export default RecoveryBackupHistory;
