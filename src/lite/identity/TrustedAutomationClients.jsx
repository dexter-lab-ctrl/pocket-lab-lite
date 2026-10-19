import React from 'react';
import { Check, CircleAlert, Shield, UserX, X } from 'lucide-react';
import { LiteButton, StateSurface } from '../LiteUi.jsx';

const OPERATION_TYPE = 'photo_backup.bounded_acceptance.v1';

const STATUS_LABELS = Object.freeze({
  pending: 'Waiting for Owner registration',
  registered: 'Registered',
  rejected: 'Rejected',
  expired: 'Expired',
  cancelled: 'Cancelled',
  active: 'Active',
  revoked: 'Revoked',
});

function statusLabel(value) {
  return STATUS_LABELS[value] || 'Status not reported';
}

function capabilityLabel(item) {
  const capability = Array.isArray(item?.capabilities) ? item.capabilities[0] : '';
  return capability || OPERATION_TYPE;
}

function PairingCard({ pairing, fresh, busy, onApprove, onReject }) {
  const pending = pairing?.status === 'pending';
  const enabled = Boolean(fresh && pending && !busy);
  const id = pairing?.pairing_id || 'unknown-pairing';
  return <article className="lite-owner-client-card">
    <div className="lite-owner-client-card-head">
      <div><span className="lite-owner-client-kicker">Pending client registration</span><h3>{pairing?.display_name || pairing?.client_id || 'Automation client'}</h3></div>
      {pending ? <CircleAlert size={18} aria-hidden="true" /> : pairing?.status === 'registered' ? <Check size={18} aria-hidden="true" /> : <X size={18} aria-hidden="true" />}
    </div>
    <dl className="lite-owner-client-facts">
      <div><dt>Requester identity</dt><dd>{pairing?.client_id || 'Not reported'}</dd></div>
      <div><dt>Public-key fingerprint</dt><dd>{pairing?.public_key_fingerprint || 'Not reported'}</dd></div>
      <div><dt>Capability</dt><dd>{capabilityLabel(pairing)}</dd></div>
      <div><dt>Pairing expires</dt><dd>{pairing?.expires_at || 'Not reported'}</dd></div>
      <div><dt>Status</dt><dd>{statusLabel(pairing?.status)}</dd></div>
    </dl>
    {pairing?.terminal_reason ? <p className="lite-owner-client-terminal">{pairing.terminal_reason}</p> : null}
    {pending ? <div className="lite-owner-client-actions">
      <LiteButton type="button" onClick={() => onApprove?.(pairing)} disabled={!enabled}>{busy === `register:${id}` ? 'Registering…' : 'Register client'}</LiteButton>
      <LiteButton type="button" variant="secondary" onClick={() => onReject?.(pairing)} disabled={!enabled}><X size={16} aria-hidden="true" /> Reject registration</LiteButton>
    </div> : null}
  </article>;
}

function ClientCard({ client, fresh, busy, onRevoke }) {
  const active = client?.status === 'active';
  const id = client?.client_id || 'unknown-client';
  const enabled = Boolean(fresh && active && !busy);
  return <article className="lite-owner-client-card">
    <div className="lite-owner-client-card-head">
      <div><span className="lite-owner-client-kicker">Trusted automation client</span><h3>{client?.display_name || id}</h3></div>
      {active ? <Shield size={18} aria-hidden="true" /> : <UserX size={18} aria-hidden="true" />}
    </div>
    <dl className="lite-owner-client-facts">
      <div><dt>Requester identity</dt><dd>{id}</dd></div>
      <div><dt>Public-key fingerprint</dt><dd>{client?.public_key_fingerprint || 'Not reported'}</dd></div>
      <div><dt>Capability</dt><dd>{capabilityLabel(client)}</dd></div>
      <div><dt>Registered</dt><dd>{client?.created_at || 'Not reported'}</dd></div>
      <div><dt>Status</dt><dd>{statusLabel(client?.status)}</dd></div>
    </dl>
    {client?.revoked_at ? <p className="lite-owner-client-terminal">Revoked {client.revoked_at}{client.revoke_reason ? ` · ${client.revoke_reason}` : ''}</p> : null}
    {active ? <div className="lite-owner-client-actions">
      <LiteButton type="button" variant="secondary" onClick={() => onRevoke?.(client)} disabled={!enabled}><UserX size={16} aria-hidden="true" /> Revoke client</LiteButton>
    </div> : null}
  </article>;
}

export default function TrustedAutomationClients({
  clients = [],
  pairings = [],
  fresh = false,
  busy = '',
  onApprove,
  onReject,
  onRevoke,
}) {
  const safeClients = Array.isArray(clients) ? clients : [];
  const safePairings = Array.isArray(pairings) ? pairings : [];
  const hasItems = safeClients.length > 0 || safePairings.length > 0;
  return <section className="lite-owner-client-enrollment" aria-label="Trusted automation clients">
    <header className="lite-owner-client-heading">
      <div><span className="lite-identity-soft-badge">Owner-managed access</span><h2>Trusted automation clients</h2></div>
      <p>Review a requester’s identity and fixed capability before it can submit a bounded operation. Pairing never grants Owner access.</p>
    </header>
    {!fresh ? <StateSurface tone="degraded" title="Live client data unavailable" description="Saved access details cannot authorize registration or revocation. Refresh while Pocket Lab is reachable." /> : null}
    {!hasItems && fresh ? <StateSurface tone="neutral" title="No trusted automation clients" description="A protected pairing request will appear here when a registered requester asks to connect." /> : null}
    {safePairings.length ? <div className="lite-owner-client-list" aria-label="Automation-client pairing requests">
      {safePairings.map((pairing) => <PairingCard key={pairing.pairing_id} pairing={pairing} fresh={fresh} busy={busy} onApprove={onApprove} onReject={onReject} />)}
    </div> : null}
    {safeClients.length ? <div className="lite-owner-client-list" aria-label="Registered automation clients">
      {safeClients.map((client) => <ClientCard key={client.client_id} client={client} fresh={fresh} busy={busy} onRevoke={onRevoke} />)}
    </div> : null}
  </section>;
}
