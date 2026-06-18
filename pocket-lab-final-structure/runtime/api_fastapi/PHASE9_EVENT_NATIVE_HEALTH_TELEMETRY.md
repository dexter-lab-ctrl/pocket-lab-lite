# Phase 9 — Event-native Health Engine and NOC Telemetry

Phase 9 turns System Status/NOC from request-only snapshots into a live control-plane stream.

## Runtime services

FastAPI starts `LiveStatusSampler` during application lifespan unless disabled with:

```bash
export POCKETLAB_LIVE_STATUS_ENABLED=0
```

The sampler publishes health, telemetry, and fleet status through the Pocket Lab event bus. NATS/JetStream is required in production; unavailable NATS surfaces as degraded/unready state rather than silent fallback.

## Intervals

```bash
export POCKETLAB_TELEMETRY_SAMPLE_SECONDS=5
export POCKETLAB_HEALTH_SAMPLE_SECONDS=15
export POCKETLAB_FLEET_SAMPLE_SECONDS=15
export POCKETLAB_TELEMETRY_CHANGE_THRESHOLD=2.0
```

## Events

- `pocketlab.events.telemetry.sampled`
- `pocketlab.events.telemetry.changed`
- `pocketlab.events.health.checked`
- `pocketlab.events.health.changed`
- `pocketlab.events.health.service_changed`
- `pocketlab.events.fleet.health_sampled`
- `pocketlab.events.fleet.health_changed`
- `pocketlab.events.live_status.started`
- `pocketlab.events.live_status.stopped`
- `pocketlab.events.live_status.*_error`

## APIs

- `GET /api/live-status/status`
- `POST /api/live-status/sample`
- `POST /api/live-status/restart`
- `GET /api/telemetry/live/status`
- `GET /api/telemetry.json` now samples and publishes a telemetry event.
- `GET /api/health-engine.json` now samples and publishes health events.
- `GET /api/fleet/health.json` now samples and publishes fleet events.

## Frontend

`useTelemetry()` and `useHealthEngine()` now prefer `/ws/events` and `/api/events/recent` over tight polling. Polling remains a degraded fallback. `NocTelemetryTab`/System Status consumes live events directly and shows FastAPI/NATS streaming state.
