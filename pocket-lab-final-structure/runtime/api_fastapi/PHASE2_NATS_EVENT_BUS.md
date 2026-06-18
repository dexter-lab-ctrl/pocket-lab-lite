# Pocket Lab Phase 2 — NATS Event Bus Wrapper

Phase 2 adds an internal event bus wrapper for FastAPI without changing the React PWA API contract.

## Runtime behavior

- Uses NATS at `POCKETLAB_NATS_URL` when `nats-py` and `nats-server` are available.
- Creates JetStream streams for commands, events, audit messages, and telemetry when JetStream is enabled.
- Fails closed when NATS/JetStream is unavailable; `POCKETLAB_NATS_REQUIRED=1` is the default.
- Browser clients still connect to FastAPI over REST/WebSocket; the browser never connects directly to NATS.

## Core subjects

- `pocketlab.commands.operation.execute`
- `pocketlab.commands.drift.scan`
- `pocketlab.commands.fleet.join`
- `pocketlab.commands.release.check`
- `pocketlab.commands.release.apply`
- `pocketlab.events.operation.*`
- `pocketlab.events.health.*`
- `pocketlab.events.telemetry.*`
- `pocketlab.events.drift.*`
- `pocketlab.events.fleet.*`
- `pocketlab.events.release.*`
- `pocketlab.audit.*`

## New endpoints

- `GET /api/events/status`
- `GET /api/nats/status`
- `GET /api/events/recent`
- `POST /api/events/publish`
- `WS /ws/events`
- `WS /ws/operations/{job_id}`

## Environment variables

- `POCKETLAB_NATS_URL=nats://127.0.0.1:4222`
- `POCKETLAB_NATS_NAME=pocketlab-fastapi`
- `POCKETLAB_NATS_JETSTREAM=1`
- `POCKETLAB_NATS_REQUIRE_JETSTREAM=1`
- `POCKETLAB_NATS_REQUIRED=1`
- `POCKETLAB_EVENT_HISTORY_LIMIT=500`
- `POCKETLAB_NATS_CONNECT_TIMEOUT=1.5`

## Phase 3 readiness

Phase 2 publishes command events and observable lifecycle events. Phase 3 can add durable workers that consume `pocketlab.commands.>` subjects and execute operations independently from the FastAPI process.
