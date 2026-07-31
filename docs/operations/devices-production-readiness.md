# Devices production readiness — Phases A–F

## Objective

Keep one durable device identity while runtime facts converge independently. The frontend remains a consumer of FastAPI projections and never talks to NATS or executes device commands directly.

## Phase A — Canonical device facts

- SQLite remains authoritative for enrolled identities, system profiles, supervisor evidence, health dimensions, command lifecycle, and removal receipts.
- The protected Server Host uses one canonical node ID and deterministic source precedence: fresh agent profile, prepared local projection, last-good SQLite profile, then explicit unknown values.
- Raw architecture and normalized architecture family are retained separately. Friendly model labels never overwrite technical identity.

## Phase B — Agent convergence and transport

- One connection manager owns NATS reconnect behavior.
- Reconnect uses bounded exponential backoff with jitter and a 30-second ceiling.
- Noncritical heartbeat, telemetry, and periodic profile events do not force a flush.
- Startup and reconnect publish identity, profile, capabilities, then a fresh heartbeat.
- Unchanged profiles are periodically republished so missed events self-heal without bloating every heartbeat.
- Repeated library failures are reduced to bounded reason-code logging.

## Phase C — Supervisor truth

- Supervisor evidence is persisted in `device_supervisor_state` independently of PM2 discovery.
- Process presence, supervisor health, NATS reachability, repair evidence, schema version, and freshness remain separate facts.
- Out-of-order evidence cannot replace a newer SQLite row.

## Phase D — Health and capability semantics

- Operational health, software posture, recovery posture, profile completeness, and field freshness are independent dimensions.
- Missing version evidence is `verification_pending`; only a proven older version is `behind`.
- Capabilities distinguish `not_advertised`, `verification_pending`, `verified`, and `unavailable`.

## Phase E — Guarded lifecycle

- The Server Host is permanently protected.
- A joined secondary device can be retired after explicit confirmation when no active dependency, recovery, or command blocker exists.
- Online state is a warning, not a permanent removal prohibition.
- Stale commands are terminalized independently as timed out or undeliverable and retain audit evidence.
- Retirement remains transactional and keeps lifecycle history and a removal receipt.

## Phase F — Frontend convergence

- Device cards use normalized model, architecture, multidimensional health, and field-specific pending states.
- Only verified capabilities contribute to verified counts.
- History totals never render fewer total rows than the loaded page.
- Existing TanStack Query, Dexie snapshots, Zustand state, and XState action flows are retained; no parallel polling or browser-side execution path is introduced.

## Production acceptance

- Server Host model and architecture survive API restarts through last-good SQLite profile data.
- Secondary devices publish profile and capabilities within the reconnect convergence window.
- A missing supervisor heartbeat does not masquerade as PM2 truth.
- Healthy operational metrics are not downgraded merely because software verification is pending.
- The Server Host cannot be removed; secondary devices use confirmation and exact blockers.
- Device history counts, capability counts, and removal labels remain truthful on mobile and desktop.
