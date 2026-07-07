import React from 'react';
import { formatLiteTime } from '../../lib/liteApi.js';
import LiteHistorySection from '../components/LiteHistorySection.jsx';

const SECURITY_HISTORY_IS_LAZY = true;
const SECURITY_HISTORY_ROWS_MOUNT_ONLY_WHEN_OPENED = true;
void SECURITY_HISTORY_IS_LAZY;
void SECURITY_HISTORY_ROWS_MOUNT_ONLY_WHEN_OPENED;

function formatDuration(seconds) {
  const value = Number(seconds || 0);
  if (!Number.isFinite(value) || value <= 0) return 'Duration not available';
  if (value < 60) return `${Math.round(value)}s`;
  return `${Math.round(value / 60)}m`;
}

function historyItems(history = []) {
  return (Array.isArray(history) ? history : []).slice(0, 20).map((entry, index) => {
    const reviewCount = Number(entry?.items_to_review || 0);
    const evidenceCount = Number(entry?.evidence_count || 0);
    const title = reviewCount ? `${reviewCount} review item${reviewCount === 1 ? '' : 's'}` : 'No urgent items';
    const metaParts = [
      entry?.score !== undefined ? `Score ${entry.score}` : '',
      evidenceCount ? `${evidenceCount} evidence file${evidenceCount === 1 ? '' : 's'}` : 'Evidence pending',
      formatDuration(entry?.duration_seconds),
    ].filter(Boolean);
    return {
      id: entry?.run_id || `security-history-${index}`,
      title,
      meta: entry?.completed_at ? `${formatLiteTime(entry.completed_at)} · ${metaParts.join(' · ')}` : metaParts.join(' · '),
    };
  });
}

export default function SecurityHistoryLazy({ history = [], latestScore, trendLabel = '', trendDetail = '', savedStateOnly = false }) {
  const items = historyItems(history);
  return (
    <div className="lite-security-history-lazy" data-security-history-lazy="true">
      <div className="lite-security-trend-summary">
        <div>
          <span>Latest score</span>
          <strong>{latestScore ?? '—'}</strong>
        </div>
        <div>
          <span>Trend</span>
          <strong>{trendLabel || 'Not enough history'}</strong>
          {trendDetail ? <small>{trendDetail}</small> : null}
        </div>
      </div>

      <LiteHistorySection
        title="Security run history"
        summary={items.length ? `${items.length} safe security run${items.length === 1 ? '' : 's'} available.` : 'History will appear here after more safety checks.'}
        items={items}
        enabled
        savedState={savedStateOnly}
        emptyMessage="History will appear here after more safety checks."
      />
    </div>
  );
}
