import React, { useMemo } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { formatLiteTime, liteApi } from '../../lib/liteApi.js';
import { liteQueryKeys } from '../../lib/liteQueryClient.js';
import { mergeSecurityHistoryPages } from '../../lib/liteViewModels.js';
import LiteVirtualList from '../components/LiteVirtualList.jsx';

const SECURITY_HISTORY_IS_LAZY = true;
const SECURITY_HISTORY_ROWS_MOUNT_ONLY_WHEN_OPENED = true;
const SECURITY_HISTORY_CURSOR_V2 = 'security-history-cursor-v2';
const SECURITY_HISTORY_BROWSER_ROW_LIMIT = 200;
void SECURITY_HISTORY_IS_LAZY;
void SECURITY_HISTORY_ROWS_MOUNT_ONLY_WHEN_OPENED;
void SECURITY_HISTORY_CURSOR_V2;

function formatDuration(durationMs, durationSeconds) {
  const milliseconds = Number(durationMs || 0);
  const seconds = milliseconds > 0 ? milliseconds / 1000 : Number(durationSeconds || 0);
  if (!Number.isFinite(seconds) || seconds <= 0) return 'Duration not available';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  return `${Math.round(seconds / 60)}m`;
}

function safeToolLabels(toolStatus = []) {
  return (Array.isArray(toolStatus) ? toolStatus : []).slice(0, 4).map((item) => `${String(item?.tool || 'tool').slice(0, 28)} ${String(item?.status || 'recorded').slice(0, 28)}`);
}

function initialHistoryPage(initialPage, history) {
  if (initialPage && typeof initialPage === 'object' && Array.isArray(initialPage.history)) return initialPage;
  return { view_model: SECURITY_HISTORY_CURSOR_V2, history: Array.isArray(history) ? history.slice(0, 20) : [], has_more: false, next_cursor: null, sanitized: true };
}

export default function SecurityHistoryLazy({ history = [], initialPage = null, latestScore, trendLabel = '', trendDetail = '', savedStateOnly = false, profile = 'quick' }) {
  const firstPage = useMemo(() => initialHistoryPage(initialPage, history), [history, initialPage]);
  const query = useInfiniteQuery({
    queryKey: [...liteQueryKeys.securityHistory(20), 'cursor-v2'],
    queryFn: ({ pageParam = '' }) => liteApi.securityHistory(20, pageParam),
    initialPageParam: '',
    getNextPageParam: (page) => (page?.has_more && page?.next_cursor ? page.next_cursor : undefined),
    initialData: firstPage.history.length ? { pages: [firstPage], pageParams: [''] } : undefined,
    enabled: !savedStateOnly,
    staleTime: 60_000,
    gcTime: 30 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: true,
  });
  const pages = query.data?.pages?.length ? query.data.pages : [firstPage];
  const allRows = useMemo(() => mergeSecurityHistoryPages(pages), [pages]);
  const rows = useMemo(() => allRows.slice(0, SECURITY_HISTORY_BROWSER_ROW_LIMIT), [allRows]);
  const latestPage = pages[pages.length - 1] || firstPage;
  const hasOlder = Boolean(rows.length < SECURITY_HISTORY_BROWSER_ROW_LIMIT && latestPage?.has_more && latestPage?.next_cursor);
  return (
    <div className="lite-security-history-lazy" data-security-history-lazy="true" data-security-history-cursor-v2="true">
      <div className="lite-security-trend-summary">
        <div><span>Latest score</span><strong>{latestScore ?? '—'}</strong></div>
        <div><span>Trend</span><strong>{trendLabel || 'Not enough history'}</strong>{trendDetail ? <small>{trendDetail}</small> : null}</div>
      </div>
      {savedStateOnly ? <p className="lite-security-s7-saved-note">Showing saved history. Reconnect to load older checks.</p> : null}
      {query.error ? <p role="alert">History needs a moment. {String(query.error?.message || query.error).slice(0, 140)}</p> : null}
      <LiteVirtualList
        items={rows}
        domain="securityHistory"
        datasetKey={`security:${profile || 'quick'}`}
        getItemKey={(entry) => entry?.run_id}
        estimateSize={116}
        overscan={6}
        ariaLabel="Security check history"
        normalClassName="lite-security-s7-history-list"
        virtualClassName="lite-security-s7-history-list is-virtualized"
        savedState={savedStateOnly}
        hasMore={hasOlder}
        loadingMore={query.isFetchingNextPage}
        loadMoreLabel="Load older checks"
        loadingMoreLabel="Loading older checks…"
        savedLoadMoreLabel="Reconnect to load older checks"
        onLoadMore={() => query.fetchNextPage({ cancelRefetch: false })}
        emptyState={<p>History will appear here after completed safety checks.</p>}
        endState={rows.length ? <p className="lite-virtual-list__end">{allRows.length >= SECURITY_HISTORY_BROWSER_ROW_LIMIT && latestPage?.has_more ? 'Loaded Security history limit reached.' : 'End of loaded Security history.'}</p> : null}
        testId="security-history-list"
        renderItem={(entry) => {
          const counts = entry?.finding_counts || {};
          const reviewCount = Number(counts.critical || 0) + Number(counts.high || 0);
          const tools = safeToolLabels(entry?.tool_status);
          const completedAt = entry?.completed_at || entry?.updated_at || '';
          return (
            <div className="lite-security-s7-history-row">
              <div>
                <strong>{entry?.summary || (reviewCount ? `${reviewCount} item${reviewCount === 1 ? '' : 's'} need attention` : 'Protected')}</strong>
                <span>{entry?.label || String(entry?.profile || 'quick')} · Score {entry?.score ?? '—'} · {formatDuration(entry?.duration_ms, entry?.duration_seconds)}</span>
                {tools.length ? <small>{tools.join(' · ')}</small> : null}
                {entry?.timeout?.summary ? <small>{entry.timeout.summary}</small> : null}
                {!entry?.timeout?.summary && entry?.status === 'failed' ? <small>{entry?.failure_message || 'The safety check did not finish.'}</small> : null}
                {entry?.evidence_saved ? <small>Evidence saved</small> : null}
              </div>
              <time dateTime={completedAt || undefined} title={completedAt ? formatLiteTime(completedAt) : 'Time unavailable'}>{completedAt ? formatLiteTime(completedAt) : 'Time unavailable'}</time>
            </div>
          );
        }}
      />
    </div>
  );
}
