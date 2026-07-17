import React, { useMemo, useState } from 'react';

const HISTORY_SECTION_COLLAPSED_BY_DEFAULT = true;
const HISTORY_CONTENT_MOUNTS_ONLY_WHEN_OPENED = true;
void HISTORY_SECTION_COLLAPSED_BY_DEFAULT;
void HISTORY_CONTENT_MOUNTS_ONLY_WHEN_OPENED;

function safeHistoryItems(items) {
  return (Array.isArray(items) ? items : [])
    .filter(Boolean)
    .map((item, index) => {
      if (item && typeof item === 'object') {
        return {
          id: String(item.id || item.run_id || item.operation_id || `history-${index}`),
          title: String(item.title || item.summary || item.status || 'Run').slice(0, 120),
          meta: String(item.meta || item.completed_at || item.updated_at || item.started_at || '').slice(0, 120),
        };
      }
      return { id: `history-${index}`, title: String(item).slice(0, 120), meta: '' };
    })
    .slice(0, 20);
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
}) {
  const [isOpen, setIsOpen] = useState(false);
  const safeItems = useMemo(() => safeHistoryItems(items), [items]);
  const count = safeItems.length;
  const collapsedSummary = summary || (count ? `${count} saved run${count === 1 ? '' : 's'}.` : emptyMessage);
  const shouldMountHistory = Boolean(isOpen && enabled);

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
          {!children && !loading && !error && safeItems.length ? (
            <ol className="lite-history-section-list">
              {safeItems.map((item) => (
                <li key={item.id}>
                  <span>{item.title}</span>
                  {item.meta ? <small>{item.meta}</small> : null}
                </li>
              ))}
            </ol>
          ) : null}
          {!children && !loading && !error && !safeItems.length ? <p>{emptyMessage}</p> : null}
        </div>
      ) : null}
    </section>
  );
}
