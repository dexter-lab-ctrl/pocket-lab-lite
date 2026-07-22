import React, {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { defaultRangeExtractor, useVirtualizer } from '@tanstack/react-virtual';
import {
  liteVirtualizationDiagnostics,
  normalizeLiteVirtualRows,
  readLiteVirtualScrollState,
  saveLiteVirtualScrollState,
  selectLiteVirtualMode,
} from '../../lib/liteVirtualization.js';

const DEFAULT_ESTIMATED_ROW_HEIGHT = 92;
const DEFAULT_OVERSCAN = 5;
const HIDDEN_MEASUREMENT_ROW_LIMIT = 12;

class LiteVirtualListErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidUpdate(previousProps) {
    if (this.state.failed && previousProps.resetKey !== this.props.resetKey) {
      this.setState({ failed: false });
    }
  }

  retry = () => this.setState({ failed: false });

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="lite-virtual-list-error" role="alert" data-lite-virtual-list-error="true">
        <strong>This list needs a moment</strong>
        <p>Other Pocket Lab areas remain available. Retry this list without reloading the app.</p>
        <button type="button" onClick={this.retry}>Retry list</button>
      </div>
    );
  }
}

function useCompactVirtualPolicy() {
  const [compact, setCompact] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return undefined;
    const media = window.matchMedia('(max-width: 720px), (pointer: coarse)');
    const update = () => setCompact(Boolean(media.matches));
    update();
    if (typeof media.addEventListener === 'function') media.addEventListener('change', update);
    else media.addListener?.(update);
    return () => {
      if (typeof media.removeEventListener === 'function') media.removeEventListener('change', update);
      else media.removeListener?.(update);
    };
  }, []);

  return compact;
}

function boundedPositive(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : fallback;
}

function LiteVirtualListContent({
  items = [],
  domain = 'default',
  datasetKey = 'default',
  getItemKey,
  renderItem,
  estimateSize = DEFAULT_ESTIMATED_ROW_HEIGHT,
  overscan = DEFAULT_OVERSCAN,
  ariaLabel = 'History',
  className = '',
  normalClassName = '',
  virtualClassName = '',
  disabled = false,
  savedState = false,
  hasMore = false,
  loadingMore = false,
  loadMoreLabel = 'Load more',
  loadingMoreLabel = 'Loading…',
  savedLoadMoreLabel = 'Reconnect to load more',
  onLoadMore,
  emptyState = null,
  endState = null,
  pinnedItemKeys = [],
  viewportHeight = 560,
  lanes = 1,
  compactLanes = 1,
  laneGap = 0,
  totalCount = null,
  testId = '',
}) {
  const compact = useCompactVirtualPolicy();
  const laneCount = Math.max(1, Math.floor(boundedPositive(compact ? compactLanes : lanes, 1)));
  const resolvedLaneGap = Math.max(0, Number(laneGap) || 0);
  const normalized = useMemo(
    () => normalizeLiteVirtualRows(items, { domain, getKey: getItemKey }),
    [domain, getItemKey, items],
  );
  const { rows, keys, duplicateCount, fallbackCount, fallbackCollisionCount } = normalized;
  const virtualModeRef = useRef(false);
  const shouldVirtualize = selectLiteVirtualMode({
    count: rows.length,
    domain,
    compact,
    previousMode: virtualModeRef.current,
    disabled,
  });
  virtualModeRef.current = shouldVirtualize;

  const scrollRef = useRef(null);
  const scrollFrameRef = useRef(0);
  const loadMorePendingRef = useRef(false);
  const [viewportReady, setViewportReady] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const initialOffset = useMemo(
    () => readLiteVirtualScrollState(domain, datasetKey),
    [datasetKey, domain],
  );
  const pinnedIndexes = useMemo(() => {
    const wanted = new Set((Array.isArray(pinnedItemKeys) ? pinnedItemKeys : []).map(String));
    return keys.reduce((indexes, key, index) => {
      const rawKey = typeof getItemKey === 'function' ? getItemKey(rows[index]) : '';
      if (wanted.has(String(key)) || wanted.has(String(rawKey || ''))) indexes.push(index);
      return indexes;
    }, []);
  }, [getItemKey, keys, pinnedItemKeys, rows]);

  const rangeExtractor = useCallback((range) => {
    const indexes = new Set(defaultRangeExtractor(range));
    if (focusedIndex >= 0 && focusedIndex < rows.length) indexes.add(focusedIndex);
    pinnedIndexes.forEach((index) => {
      if (index >= 0 && index < rows.length) indexes.add(index);
    });
    return [...indexes].sort((left, right) => left - right);
  }, [focusedIndex, pinnedIndexes, rows.length]);

  const virtualItemKey = useCallback((index) => keys[index], [keys]);
  const estimatedItemSize = useCallback(
    () => boundedPositive(estimateSize, DEFAULT_ESTIMATED_ROW_HEIGHT),
    [estimateSize],
  );

  const rowVirtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    getItemKey: virtualItemKey,
    estimateSize: estimatedItemSize,
    overscan: Math.max(1, Math.floor(boundedPositive(overscan, DEFAULT_OVERSCAN))),
    initialOffset,
    rangeExtractor,
    lanes: laneCount,
    gap: resolvedLaneGap,
    enabled: Boolean(shouldVirtualize && viewportReady),
  });

  useLayoutEffect(() => {
    const element = scrollRef.current;
    if (!shouldVirtualize || !element) {
      setViewportReady(false);
      return undefined;
    }
    let active = true;
    const update = () => {
      if (!active) return;
      const ready = element.clientHeight > 0 && element.clientWidth > 0;
      setViewportReady((current) => (current === ready ? current : ready));
      if (ready) rowVirtualizer.measure();
    };
    update();
    if (typeof ResizeObserver === 'undefined') {
      if (typeof window !== 'undefined') window.addEventListener?.('resize', update, { passive: true });
      return () => {
        active = false;
        if (typeof window !== 'undefined') window.removeEventListener?.('resize', update);
      };
    }
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => {
      active = false;
      observer.disconnect();
    };
  }, [rowVirtualizer, shouldVirtualize]);

  useEffect(() => () => {
    if (scrollFrameRef.current && typeof cancelAnimationFrame === 'function') {
      cancelAnimationFrame(scrollFrameRef.current);
    }
    const element = scrollRef.current;
    if (element) saveLiteVirtualScrollState(domain, datasetKey, element.scrollTop);
  }, [datasetKey, domain]);

  useEffect(() => {
    if (!import.meta.env.DEV || (!duplicateCount && !fallbackCount && !fallbackCollisionCount)) return;
    console.warn('[Pocket Lab Lite] virtual list key guard', {
      domain,
      duplicateCount,
      fallbackCount,
      fallbackCollisionCount,
    });
  }, [domain, duplicateCount, fallbackCollisionCount, fallbackCount]);

  const onScroll = useCallback((event) => {
    if (scrollFrameRef.current || typeof requestAnimationFrame !== 'function') return;
    const offset = event.currentTarget.scrollTop;
    scrollFrameRef.current = requestAnimationFrame(() => {
      scrollFrameRef.current = 0;
      saveLiteVirtualScrollState(domain, datasetKey, offset);
    });
  }, [datasetKey, domain]);

  const onFocusCapture = useCallback((event) => {
    const row = event.target?.closest?.('[data-lite-virtual-index]');
    const index = Number(row?.getAttribute?.('data-lite-virtual-index'));
    if (Number.isInteger(index)) setFocusedIndex(index);
  }, []);

  const onBlurCapture = useCallback((event) => {
    const next = event.relatedTarget;
    if (next && scrollRef.current?.contains(next)) return;
    setFocusedIndex(-1);
  }, []);

  const loadMore = useCallback(async () => {
    if (!onLoadMore || loadingMore || savedState || loadMorePendingRef.current) return;
    loadMorePendingRef.current = true;
    try {
      await onLoadMore();
    } finally {
      loadMorePendingRef.current = false;
    }
  }, [loadingMore, onLoadMore, savedState]);

  const diagnostics = liteVirtualizationDiagnostics({
    domain,
    enabled: shouldVirtualize,
    loadedCount: rows.length,
    hasMore,
    savedState,
    duplicateCount,
    fallbackCount,
    fallbackCollisionCount,
  });
  const listDescription = savedState
    ? `Showing ${rows.length} saved row${rows.length === 1 ? '' : 's'}. The saved list may be incomplete.`
    : `Showing ${rows.length}${Number.isFinite(Number(totalCount)) ? ` of ${Number(totalCount)}` : ''} row${rows.length === 1 ? '' : 's'}.${hasMore ? ' More rows are available.' : ''}`;
  const footer = hasMore ? (
    <button
      type="button"
      className="lite-virtual-list__load-more"
      onClick={loadMore}
      disabled={Boolean(loadingMore || savedState)}
    >
      {savedState ? savedLoadMoreLabel : loadingMore ? loadingMoreLabel : loadMoreLabel}
    </button>
  ) : endState;

  if (!rows.length) {
    return emptyState || null;
  }

  if (!shouldVirtualize) {
    return (
      <div
        className={`lite-virtual-list-shell is-normal ${className}`.trim()}
        data-lite-virtual-domain={domain}
        data-lite-virtualization="disabled"
        data-loaded-row-count={rows.length}
        data-next-page-available={diagnostics.next_page_available ? 'true' : 'false'}
        data-saved-state={savedState ? 'true' : 'false'}
        data-duplicate-row-count={diagnostics.duplicate_row_count}
        data-fallback-key-count={diagnostics.fallback_key_count}
        data-fallback-collision-count={diagnostics.fallback_collision_count}
        data-testid={testId || undefined}
      >
        <p className="sr-only" aria-live="polite">{listDescription}</p>
        <ol className={normalClassName || 'lite-virtual-list__normal'} aria-label={ariaLabel}>
          {rows.map((item, index) => (
            <li key={keys[index]} data-lite-row-key-kind={keys[index].includes('fallback') ? 'fallback' : 'stable'}>
              {renderItem(item, index, { key: keys[index], virtual: false })}
            </li>
          ))}
        </ol>
        {footer}
      </div>
    );
  }

  const virtualItems = viewportReady ? rowVirtualizer.getVirtualItems() : [];
  const pendingRows = viewportReady ? [] : rows.slice(0, HIDDEN_MEASUREMENT_ROW_LIMIT);

  return (
    <div
      className={`lite-virtual-list-shell is-virtual ${className}`.trim()}
      data-lite-virtual-domain={domain}
      data-lite-virtualization="enabled"
      data-loaded-row-count={rows.length}
      data-next-page-available={diagnostics.next_page_available ? 'true' : 'false'}
      data-saved-state={savedState ? 'true' : 'false'}
      data-duplicate-row-count={diagnostics.duplicate_row_count}
      data-fallback-key-count={diagnostics.fallback_key_count}
      data-fallback-collision-count={diagnostics.fallback_collision_count}
      data-testid={testId || undefined}
    >
      <p className="sr-only" aria-live="polite">{listDescription}</p>
      <div
        ref={scrollRef}
        className={`lite-virtual-list__viewport ${virtualClassName}`.trim()}
        style={{ '--lite-virtual-viewport-height': `${boundedPositive(viewportHeight, 560)}px` }}
        role="list"
        aria-label={ariaLabel}
        tabIndex={0}
        onScroll={onScroll}
        onFocusCapture={onFocusCapture}
        onBlurCapture={onBlurCapture}
      >
        {viewportReady ? (
          <div className="lite-virtual-list__spacer" style={{ height: `${rowVirtualizer.getTotalSize()}px` }}>
            {virtualItems.map((virtualRow) => {
              const item = rows[virtualRow.index];
              return (
                <div
                  key={keys[virtualRow.index]}
                  ref={rowVirtualizer.measureElement}
                  className="lite-virtual-list__item"
                  role="listitem"
                  aria-posinset={virtualRow.index + 1}
                  aria-setsize={Number.isFinite(Number(totalCount)) ? Number(totalCount) : hasMore ? -1 : rows.length}
                  data-index={virtualRow.index}
                  data-lite-virtual-index={virtualRow.index}
                  data-lite-row-key-kind={keys[virtualRow.index].includes('fallback') ? 'fallback' : 'stable'}
                  style={{
                    insetInlineStart: laneCount > 1 ? `calc(${virtualRow.lane * (100 / laneCount)}% + ${virtualRow.lane * resolvedLaneGap / laneCount}px)` : 0,
                    inlineSize: laneCount > 1 ? `calc(${100 / laneCount}% - ${resolvedLaneGap * (laneCount - 1) / laneCount}px)` : '100%',
                    transform: `translateY(${virtualRow.start}px)`,
                  }}
                >
                  {renderItem(item, virtualRow.index, { key: keys[virtualRow.index], virtual: true })}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="lite-virtual-list__measurement-fallback" aria-busy="true">
            {pendingRows.map((item, index) => (
              <div key={keys[index]} role="listitem" data-lite-virtual-index={index}>
                {renderItem(item, index, { key: keys[index], virtual: true })}
              </div>
            ))}
          </div>
        )}
      </div>
      {footer}
    </div>
  );
}

export default function LiteVirtualList(props) {
  const resetKey = `${String(props?.domain || 'default')}::${String(props?.datasetKey || 'default')}::${Array.isArray(props?.items) ? props.items.length : 0}`;
  return (
    <LiteVirtualListErrorBoundary resetKey={resetKey}>
      <LiteVirtualListContent {...props} />
    </LiteVirtualListErrorBoundary>
  );
}
