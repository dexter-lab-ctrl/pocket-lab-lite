import React from 'react';
import { AlertTriangle, Inbox, ShieldAlert, WifiOff } from 'lucide-react';


const STATE_CLASS = {
  empty: 'border-dashed border-blue-300/20 bg-blue-500/10 text-blue-100',
  degraded: 'border-amber-300/25 bg-amber-500/10 text-amber-100',
  offline: 'border-slate-300/20 bg-slate-500/10 text-slate-100',
  blocked: 'border-rose-300/25 bg-rose-500/10 text-rose-100',
};

function stateIcon(tone) {
  if (tone === 'degraded') return AlertTriangle;
  if (tone === 'offline') return WifiOff;
  if (tone === 'blocked') return ShieldAlert;
  return Inbox;
}


const STATUS_LANGUAGE = {
  healthy: { label: 'Healthy', tone: 'success' },
  ready: { label: 'Ready', tone: 'success' },
  online: { label: 'Online', tone: 'success' },
  success: { label: 'Done', tone: 'success' },
  succeeded: { label: 'Done', tone: 'success' },
  running: { label: 'Running', tone: 'info' },
  worker_claimed: { label: 'Worker claimed', tone: 'info' },
  working: { label: 'Working', tone: 'info' },
  queued: { label: 'Queued', tone: 'info' },
  pending: { label: 'Waiting', tone: 'info' },
  loading: { label: 'Loading', tone: 'info' },
  pending_approval: { label: 'Approval Required', tone: 'warning' },
  approval_required: { label: 'Approval Required', tone: 'warning' },
  waiting_for_approval: { label: 'Approval Required', tone: 'warning' },
  paused: { label: 'Paused', tone: 'warning' },
  auto_approved: { label: 'Auto-approved', tone: 'success' },
  degraded: { label: 'Degraded', tone: 'warning' },
  warning: { label: 'Needs Attention', tone: 'warning' },
  unavailable: { label: 'Unavailable', tone: 'danger' },
  unhealthy: { label: 'Unhealthy', tone: 'danger' },
  failed: { label: 'Failed', tone: 'danger' },
  error: { label: 'Failed', tone: 'danger' },
  blocked: { label: 'Blocked', tone: 'danger' },
  offline: { label: 'Offline', tone: 'neutral' },
  unknown: { label: 'Unknown', tone: 'neutral' },
};

function normalizeStatus(status) {
  return String(status || 'unknown').toLowerCase().replace(/[\s-]+/g, '_');
}

export function statusLanguage(status, { simpleMode = false } = {}) {
  const normalized = normalizeStatus(status);
  const entry = STATUS_LANGUAGE[normalized] || STATUS_LANGUAGE.unknown;
  if (!simpleMode) return entry;
  const simpleLabels = {
    approval_required: 'Waiting for review',
    pending_approval: 'Waiting for review',
    waiting_for_approval: 'Waiting for review',
    warning: 'Needs attention',
    degraded: 'Needs attention',
    failed: 'Needs attention',
    error: 'Needs attention',
    blocked: 'Paused for safety',
    running: 'Working',
    worker_claimed: 'Worker picked it up',
    auto_approved: 'Approved safely',
    queued: 'Getting ready',
    succeeded: 'Done',
    success: 'Done',
  };
  return { ...entry, label: simpleLabels[normalized] || entry.label };
}

const STATUS_CLASS = {
  healthy: 'pocket-badge pocket-badge-success',
  ready: 'pocket-badge pocket-badge-success',
  online: 'pocket-badge pocket-badge-success',
  success: 'pocket-badge pocket-badge-success',
  succeeded: 'pocket-badge pocket-badge-success',
  degraded: 'pocket-badge pocket-badge-warning',
  warning: 'pocket-badge pocket-badge-warning',
  running: 'pocket-badge pocket-badge-info',
  worker_claimed: 'pocket-badge pocket-badge-info',
  working: 'pocket-badge pocket-badge-info',
  queued: 'pocket-badge pocket-badge-info',
  pending: 'pocket-badge pocket-badge-info',
  loading: 'pocket-badge pocket-badge-info',
  pending_approval: 'pocket-badge pocket-badge-warning',
  approval_required: 'pocket-badge pocket-badge-warning',
  waiting_for_approval: 'pocket-badge pocket-badge-warning',
  paused: 'pocket-badge pocket-badge-warning',
  auto_approved: 'pocket-badge pocket-badge-success',
  unavailable: 'pocket-badge pocket-badge-danger',
  unhealthy: 'pocket-badge pocket-badge-danger',
  failed: 'pocket-badge pocket-badge-danger',
  blocked: 'pocket-badge pocket-badge-danger',
  error: 'pocket-badge pocket-badge-danger',
  offline: 'pocket-badge pocket-badge-neutral',
  unknown: 'pocket-badge pocket-badge-neutral',
};

export function PageShell({ eyebrow, title, description, actions, children, className = '' }) {
  return (
    <section className={`pocket-page ${className}`}>
      {(eyebrow || title || description || actions) && (
        <div className="pocket-page-header">
          <div className="min-w-0">
            {eyebrow ? <p className="pocket-eyebrow">{eyebrow}</p> : null}
            {title ? <h2 className="pocket-title">{title}</h2> : null}
            {description ? <p className="pocket-description">{description}</p> : null}
          </div>
          {actions ? <div className="pocket-page-actions">{actions}</div> : null}
        </div>
      )}
      {children}
    </section>
  );
}

export function GlassCard({ as: Component = 'section', children, className = '', interactive = false, ...props }) {
  return (
    <Component className={`pocket-card ${interactive ? 'pocket-card-interactive' : ''} ${className}`} {...props}>
      {children}
    </Component>
  );
}

export function StatusBadge({ status = 'unknown', children, className = '', simpleMode = false }) {
  const normalized = normalizeStatus(status);
  const language = statusLanguage(normalized, { simpleMode });
  return (
    <span className={`${STATUS_CLASS[normalized] || STATUS_CLASS[language.tone] || STATUS_CLASS.unknown} ${className}`}>
      {children || language.label}
    </span>
  );
}

export function SectionHeader({ eyebrow, title, description, actions, className = '' }) {
  return (
    <div className={`pocket-section-header ${className}`}>
      <div className="min-w-0">
        {eyebrow ? <p className="pocket-eyebrow">{eyebrow}</p> : null}
        <h3 className="pocket-section-title">{title}</h3>
        {description ? <p className="pocket-description">{description}</p> : null}
      </div>
      {actions ? <div className="pocket-section-actions">{actions}</div> : null}
    </div>
  );
}

export function EmptyState({ icon: Icon, title, description, action, className = '' }) {
  return (
    <div className={`pocket-empty-state ${className}`}>
      {Icon ? (
        <div className="pocket-empty-icon">
          <Icon className="h-6 w-6" />
        </div>
      ) : null}
      <p className="text-base font-black text-white">{title}</p>
      {description ? <p className="mt-2 max-w-xl text-sm leading-6 text-slate-400">{description}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}


export function StateSurface({ tone = 'empty', title, description, action, icon: IconOverride, className = '' }) {
  const normalized = String(tone || 'empty').toLowerCase();
  const Icon = IconOverride || stateIcon(normalized);
  return (
    <div className={`pocket-state-surface ${STATE_CLASS[normalized] || STATE_CLASS.empty} ${className}`}>
      <div className="pocket-state-icon">
        <Icon className="h-5 w-5" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-black text-white">{title}</p>
        {description ? <p className="mt-1 text-sm leading-6 text-slate-300">{description}</p> : null}
        {action ? <div className="mt-3">{action}</div> : null}
      </div>
    </div>
  );
}


export function ProgressiveDisclosure({
  title = 'Show details',
  children,
  defaultOpen = false,
  simpleMode = false,
  className = '',
}) {
  return (
    <details open={defaultOpen} className={`progressive-disclosure ${simpleMode ? 'progressive-disclosure-simple' : ''} ${className}`}>
      <summary className="progressive-disclosure-summary">
        <span>{simpleMode ? title.replace('Technical', 'Support') : title}</span>
        <span className="progressive-disclosure-caret" aria-hidden="true">⌄</span>
      </summary>
      <div className="progressive-disclosure-body">
        {children}
      </div>
    </details>
  );
}

export function StandardList({ title, description, actions, children, className = '' }) {
  return (
    <section className={`standard-list ${className}`}>
      {(title || description || actions) && (
        <div className="standard-list-header">
          <div className="min-w-0">
            {title ? <h3 className="standard-list-title">{title}</h3> : null}
            {description ? <p className="standard-list-description">{description}</p> : null}
          </div>
          {actions ? <div className="standard-list-actions">{actions}</div> : null}
        </div>
      )}
      <div className="standard-list-body">{children}</div>
    </section>
  );
}

export function StandardListItem({
  icon: Icon,
  title,
  description,
  status,
  simpleMode = false,
  metadata = [],
  actions,
  children,
  className = '',
}) {
  return (
    <article className={`standard-list-item ${className}`}>
      <div className="standard-list-item-main">
        {Icon ? <div className="standard-list-icon"><Icon className="h-5 w-5" /></div> : null}
        <div className="min-w-0 flex-1">
          <div className="standard-list-item-title-row">
            <h4 className="standard-list-item-title">{title}</h4>
            {status ? <StatusBadge status={status} simpleMode={simpleMode} /> : null}
          </div>
          {description ? <p className="standard-list-item-description">{description}</p> : null}
          {metadata.length ? (
            <dl className="standard-list-metadata">
              {metadata.map((item) => (
                <div key={`${item.label}-${item.value}`} className="standard-list-metadata-item">
                  <dt>{item.label}</dt>
                  <dd>{item.value}</dd>
                </div>
              ))}
            </dl>
          ) : null}
          {children ? <div className="mt-3">{children}</div> : null}
        </div>
      </div>
      {actions ? <div className="standard-list-item-actions">{actions}</div> : null}
    </article>
  );
}

export function SegmentedControl({ label, value, options, onChange, className = '' }) {
  return (
    <div className={`space-y-2 ${className}`}>
      {label ? <p className="text-xs font-black uppercase tracking-[0.18em] text-slate-400">{label}</p> : null}
      <div className={`pocket-segmented-control mode-switch-morph mode-switch-${value}`} role="radiogroup" aria-label={label} data-value={value}>
        {options.map((option) => {
          const active = value === option.value;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onChange(option.value)}
              className={`pocket-segment ${active ? 'pocket-segment-active' : ''}`}
            >
              <span className="font-black">{option.label}</span>
              {option.description ? <span className="text-[11px] font-medium text-slate-400">{option.description}</span> : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function SkeletonCards({ count = 3, simpleMode = false, className = '' }) {
  return (
    <div className={`skeleton-card-grid ${className}`} aria-label={simpleMode ? 'Loading content' : 'Loading structured cards'}>
      {Array.from({ length: count }).map((_, index) => (
        <article key={index} className="skeleton-card skeleton-shimmer" aria-hidden="true">
          <div className="skeleton-card-header">
            <span className="skeleton-icon" />
            <div className="skeleton-lines">
              <span className="skeleton-line skeleton-line-title" />
              <span className="skeleton-line skeleton-line-subtitle" />
            </div>
          </div>
          <span className="skeleton-line skeleton-line-wide" />
          <span className="skeleton-line skeleton-line-mid" />
          <div className="skeleton-card-footer">
            <span className="skeleton-pill" />
            <span className="skeleton-button" />
          </div>
        </article>
      ))}
    </div>
  );
}
