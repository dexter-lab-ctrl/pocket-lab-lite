import React from 'react';
import { Check, CircleAlert, X } from 'lucide-react';
import { LiteButton, StateSurface } from '../LiteUi.jsx';

const STATUS_LABELS = Object.freeze({
  pending_approval: 'Waiting for your approval',
  approved: 'Approved · waiting to start',
  executing: 'Executing',
  verifying: 'Verifying',
  completed: 'Completed',
  rejected: 'Rejected',
  expired: 'Expired',
  cancelled: 'Cancelled',
  failed: 'Failed',
  blocked: 'Blocked safely',
});

function operationStatus(operation) {
  return STATUS_LABELS[operation?.status] || 'Status not reported';
}

function canDecide(operation, fresh, busy) {
  return fresh && operation?.status === 'pending_approval' && !busy;
}

export default function OwnerOperationApprovals({
  operations = [],
  fresh = false,
  busy = '',
  onApprove,
  onReject,
  compact = false,
}) {
  if (!Array.isArray(operations) || operations.length === 0) return null;
  return <section className={`lite-owner-operation-approvals${compact ? ' is-compact' : ''}`} aria-label="Pending approvals">
    <header className="lite-owner-operation-heading">
      <div><span className="lite-identity-soft-badge">Owner review</span><h2>Pending approvals</h2></div>
      <p>Review the exact server-owned scope before anything starts.</p>
    </header>
    {!fresh ? <StateSurface tone="degraded" title="Live approval data unavailable" description="Saved access details cannot authorize an approval. Refresh while Pocket Lab is reachable." /> : null}
    <div className="lite-owner-operation-list">
      {operations.map((operation) => {
        const decisionEnabled = canDecide(operation, fresh, busy);
        return <article className="lite-owner-operation-card" key={operation.operation_id}>
          <div className="lite-owner-operation-card-head">
            <div><span className="lite-owner-operation-kicker">Photo Backup check</span><h3>{operationStatus(operation)}</h3></div>
            {operation.status === 'pending_approval' ? <CircleAlert size={18} aria-hidden="true" /> : operation.status === 'completed' ? <Check size={18} aria-hidden="true" /> : null}
          </div>
          <dl className="lite-owner-operation-facts">
            <div><dt>Requested by</dt><dd>{operation.requester_display_name || 'Registered qualification client'}</dd></div>
            <div><dt>Device</dt><dd>{operation.target_label || operation.target_node_id || 'Not reported'}</dd></div>
            <div><dt>Destination</dt><dd>{operation.destination || 'PhotoPrism on this server'}</dd></div>
            <div><dt>Scope</dt><dd>One generated test photo · Pictures · one safe repeat</dd></div>
            <div><dt>Approval expires</dt><dd>{operation.approval_deadline || 'Not reported'}</dd></div>
          </dl>
          <p className="lite-owner-operation-reason">{operation.reason || 'Production Photo Backup acceptance'}</p>
          {operation.status === 'pending_approval' ? <details className="lite-owner-operation-details">
            <summary>What this approval includes</summary>
            <ul>{(operation.disclosures || []).map((item) => <li key={item}>{item}</li>)}</ul>
          </details> : null}
          {operation.terminal_reason ? <p className="lite-owner-operation-terminal">{operation.terminal_reason}</p> : null}
          {operation.status === 'pending_approval' ? <div className="lite-owner-operation-actions">
            <LiteButton type="button" onClick={() => onApprove?.(operation)} disabled={!decisionEnabled}>{busy === `approve:${operation.operation_id}` ? 'Approving…' : 'Approve'}</LiteButton>
            <LiteButton type="button" variant="secondary" onClick={() => onReject?.(operation)} disabled={!decisionEnabled}><X size={16} aria-hidden="true" /> Reject</LiteButton>
          </div> : null}
        </article>;
      })}
    </div>
  </section>;
}
