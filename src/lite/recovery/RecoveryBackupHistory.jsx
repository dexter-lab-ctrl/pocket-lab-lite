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
    .filter((item) => item.id);
}

function formatSize(bytes) {
  const value = Number(bytes || 0);
  if (!value) return 'Size unavailable';
  return value >= 1024 * 1024 ? `${(value / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(value / 1024))} KB`;
}

const RecoveryBackupHistory = memo(function RecoveryBackupHistory({ initialHistory = [], latestPreviewReady = false, savedStateOnly = false, selectedBackupId = '', onSelectBackup, onVerify, onPreview, onRecover }) {
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
    });
  }, [pageItems, pageOrder]);
  const items = useMemo(() => safeHistoryItems(history, latestPreviewReady), [history, latestPreviewReady]);
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
    <GlassCard className="lite-recovery-card mt-4 lite-recovery-history-card" data-recovery-history-lazy="true" data-recovery-history-r3="cursor">
      <div className="lite-recovery-card-head">
        <div>
          <h2>Backup history</h2>
          <p>Restore points load in small pages only when History is opened.</p>
        </div>
        <StatusBadge status={items.length ? 'healthy' : query.loading ? 'checking' : 'unknown'}>{items.length} saved</StatusBadge>
      </div>
      <LiteHistorySection
        title="Backup history"
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
            const selected = id === selectedBackupId;
            const verified = backup.verification_status === 'verified';
            return (
              <article key={id} className={`lite-recovery-history-action-row${selected ? ' is-selected' : ''}`}>
                <button type="button" className="lite-recovery-history-select" onClick={() => onSelectBackup?.(backup)} aria-pressed={selected}>
                  <strong>{backup.created_at ? formatLiteTime(backup.created_at) : 'Timestamp unavailable'}</strong>
                  <span>{verified ? 'Verified' : 'Needs verification'} · {formatSize(backup.size_bytes)} · {backup.summary || 'Pocket Lab restore point'}</span>
                </button>
                <div className="lite-recovery-history-row-actions">
                  <LiteButton tone="secondary" onClick={() => onSelectBackup?.(backup)}>View details</LiteButton>
                  <LiteButton tone="secondary" onClick={() => onVerify?.(backup)} disabled={!id}>Verify</LiteButton>
                  <LiteButton tone="secondary" onClick={() => onPreview?.(backup)} disabled={!id}>Preview</LiteButton>
                  <LiteButton tone="danger" onClick={() => onRecover?.(backup)} disabled={!verified || !selected || !latestPreviewReady}>Recover</LiteButton>
                </div>
              </article>
            );
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
