# Phase 9 — Event-native Health and Native Telemetry (historical implementation note)

This note records the event-native sampler work. The current Lite health
authority is the native prepared `system.health` projection; the compatibility
health read does not collect, publish, probe, or write during a GET request.

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
- `GET /api/telemetry.json` reads the supported telemetry path.
- `GET /api/health-engine.json` reads the prepared native `system.health` projection.
- `GET /api/fleet/health.json` reads the supported fleet projection.
- `POST /api/health/check` explicitly requests a bounded health collection.

## Frontend

The active Lite screens under `src/lite/` consume FastAPI prepared reads and
the supported event stream. The former NOC/health-engine hook and tab surface
are retired; native System Health remains available through the Lite screen
registry.
