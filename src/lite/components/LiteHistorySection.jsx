import React, { useMemo, useState } from 'react';
import LiteVirtualList from './LiteVirtualList.jsx';

const HISTORY_SECTION_COLLAPSED_BY_DEFAULT = true;
const HISTORY_CONTENT_MOUNTS_ONLY_WHEN_OPENED = true;
const LITE_HISTORY_SECTION_ROW_LIMIT = 120;
void HISTORY_SECTION_COLLAPSED_BY_DEFAULT;
void HISTORY_CONTENT_MOUNTS_ONLY_WHEN_OPENED;

function safeHistoryItems(items) {
  return (Array.isArray(items) ? items : [])
    .filter(Boolean)
    .map((item) => {
      if (item && typeof item === 'object') {
        return {
          id: String(item.id || item.run_id || item.operation_id || item.backup_id || item.restore_id || ''),
          title: String(item.title || item.summary || item.status || 'Run').slice(0, 120),
          meta: String(item.meta || item.completed_at || item.updated_at || item.started_at || '').slice(0, 120),
        };
      }
      return { id: '', title: String(item).slice(0, 120), meta: '' };
    })
    .slice(0, LITE_HISTORY_SECTION_ROW_LIMIT);
}

export default function LiteHistorySection({
  title = 'Run history',
  summary = '',
  items = [],
  enabled = true,
  loading = false,
  error = '',
  savedState = false,
  emptyMessage = 'History will appear here after more runs.',
  onOpenChange,
  children = null,
  domain = 'appActionHistory',
  datasetKey = 'default',
  hasMore = false,
  loadingMore = false,
  onLoadMore,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const safeItems = useMemo(() => safeHistoryItems(items), [items]);
  const sourceCount = Array.isArray(items) ? items.filter(Boolean).length : 0;
  const count = safeItems.length;
  const collapsedSummary = summary || (count ? `${count} saved run${count === 1 ? '' : 's'}.` : emptyMessage);
  const shouldMountHistory = Boolean(isOpen && enabled);
  const wasTruncated = sourceCount > count;
  const boundedHasMore = Boolean(hasMore && count < LITE_HISTORY_SECTION_ROW_LIMIT);

  const toggle = () => {
    setIsOpen((current) => {
      const next = !current;
      onOpenChange?.(next);
      return next;
    });
  };

  return (
    <section className="lite-history-section" data-lazy-history="true" data-history-open={isOpen}>
      <button
        type="button"
        className="lite-progressive-disclosure-toggle"
        aria-expanded={isOpen}
        onClick={toggle}
      >
        <span>{title}</span>
        <small>{isOpen ? 'Hide' : count ? `${count} saved` : 'Open'}</small>
      </button>
      <p className="lite-progressive-disclosure-summary">{collapsedSummary}</p>
      {shouldMountHistory ? (
        <div className="lite-history-section-body">
          {loading ? <p>Loading history…</p> : null}
          {error ? <p role="alert">History needs a moment. {String(error).slice(0, 140)}</p> : null}
          {savedState ? <p>Showing saved state.</p> : null}
          {children}
          {!children && !loading && !error ? (
            <LiteVirtualList
              items={safeItems}
              domain={domain}
              datasetKey={datasetKey}
              getItemKey={(item) => item.id}
              estimateSize={68}
              ariaLabel={title}
              normalClassName="lite-history-section-list"
              virtualClassName="lite-history-section-list is-virtualized"
              savedState={savedState}
              hasMore={boundedHasMore}
              loadingMore={loadingMore}
              onLoadMore={onLoadMore}
              emptyState={<p>{emptyMessage}</p>}
              endState={(wasTruncated || (hasMore && count >= LITE_HISTORY_SECTION_ROW_LIMIT)) ? <p className="lite-virtual-list__end">Loaded history limit reached.</p> : null}
              renderItem={(item, _index, context) => context.virtual ? (
                <div className="lite-history-section-row">
                  <span>{item.title}</span>
                  {item.meta ? <small>{item.meta}</small> : null}
                </div>
              ) : (
                <>
                  <span>{item.title}</span>
                  {item.meta ? <small>{item.meta}</small> : null}
                </>
              )}
            />
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
