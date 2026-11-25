# Historical Phase 4: Frontend Live Event Stream

> Historical implementation evidence. The active Lite entry point is
> `src/App.jsx` → `src/lite/LiteApp.jsx`; the old tab shell and legacy panels
> listed in this report are no longer reachable. Native event and audit
> contracts remain supported through the active Lite consumers.

Phase 4 wires the React PWA to the FastAPI/NATS event layer delivered in Phases 1-3.

## What changed

- Added the reusable frontend event client and event contract used by the
  current Lite surface:
  - `src/lib/pocketLabEvents.js`
  - `src/hooks/usePocketLabEvents.js`
  - active `src/lite` consumers
- The active Lite screens consume matching event subjects for Apps, Devices,
  Safety, Recovery, Rules, Identity & Access, Home, and System Health.
- Active Lite action surfaces queue operations without blocking the UI and send
  the user to the native progress/evidence surfaces.
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
