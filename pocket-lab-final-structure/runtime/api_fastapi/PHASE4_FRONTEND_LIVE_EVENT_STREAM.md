# Phase 4: Frontend Live Event Stream

Phase 4 wires the React PWA to the FastAPI/NATS event layer delivered in Phases 1-3.

## What changed

- Added a reusable frontend event client:
  - `src/lib/pocketLabEvents.js`
  - `src/hooks/usePocketLabEvents.js`
  - `src/components/LiveEventPanel.jsx`
- Updated Simple Mode dashboard to show one live progress feed for installs, updates, backups, device invites, safety checks, and system health.
- Updated major professional/simple tabs to consume matching event subjects:
  - App Store / Apps & Services
  - GitOps / Keep My Environment Updated
  - Blueprint
  - Drift Center / Health & Issues
  - Fleet Scaling / My Devices
  - Release Workflow / Updates
  - Security Posture / Safety Center
  - NOC Telemetry / System Status
  - Identity & Vault / Passwords & Access
  - Disaster Recovery / Backups
- Updated the guided Simple Mode action wizard to queue operations without blocking the UI and send the user to the live progress feed.
- Updated telemetry, health, drift, fleet, release, and security FastAPI routes to publish lightweight events whenever existing polling endpoints are called.

## Frontend behavior

The frontend connects to:

```text
/ws/events
```

It replays recent events from:

```text
/api/events/recent
```

When WebSocket is unavailable, the hook uses the recent-events endpoint as a polling fallback. This preserves Android/Termux and offline-harness usability.

## Simple Mode behavior

Simple Mode translates event subjects into outcome language, for example:

- `pocketlab.events.operation.created` -> **Action queued**
- `pocketlab.events.operation.started` -> **Action is running**
- `pocketlab.events.operation.succeeded` -> **Action completed**
- `pocketlab.events.operation.failed` -> **Action needs attention**
- `pocketlab.events.health.changed` -> **System health updated**
- `pocketlab.events.fleet.*` -> **Device status changed**

Technical payloads are hidden from Simple Mode by default.

## Professional Mode behavior

Professional Mode shows:

- event subject
- event type
- raw event payload in an advanced details drawer
- WebSocket/polling status
- recent replay controls

## Backend event additions

The existing FastAPI routes now publish lightweight events on read/write flows so the UI has useful live data even before deeper subsystem agents are added.

Examples:

```text
pocketlab.events.telemetry.sampled
pocketlab.events.health.changed
pocketlab.events.fleet.health
pocketlab.events.release.status
pocketlab.events.security.evaluated
pocketlab.events.security.log_query
```

Operation and worker events from Phase 3 remain the primary source of long-running job progress.
