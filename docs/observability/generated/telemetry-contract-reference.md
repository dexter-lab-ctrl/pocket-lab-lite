<!-- GENERATED FILE: do not edit by hand. Regenerate with `task docs:observability`. -->

# Telemetry Contract Reference

Pocket Lab Lite uses the edge-first native flow:

```text
React / Vite PWA → Caddy → FastAPI → NATS / JetStream → workers and agents → prepared SQLite reads → UI
```

## Native health authority

| Property | Value |
| --- | --- |
| Source | prepared-lite-native |
| Request side effects | False |
| Collector owner | LiveStatusSampler / worker-owned projection scheduler |
| Status vocabulary | healthy, degraded, unhealthy, starting, repairing, unknown, stale, unsupported, not_configured, maintenance |

## FastAPI routes

| Method | Route | Function | Source |
| --- | --- | --- | --- |
| GET | /health | health | pocket-lab-final-structure/runtime/api_fastapi/routers/health.py |
| GET | /healthz | health | pocket-lab-final-structure/runtime/api_fastapi/routers/health.py |
| GET | /ready | ready | pocket-lab-final-structure/runtime/api_fastapi/routers/health.py |
| GET | /api/health-engine.json | health_engine | pocket-lab-final-structure/runtime/api_fastapi/routers/health.py |
| POST | /api/health/check | health_check | pocket-lab-final-structure/runtime/api_fastapi/routers/health.py |
| GET | /api/lite/system/health | get_lite_system_health | pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py |

## Native frontend consumers

| Screen | Purpose | Source |
| --- | --- | --- |
| LiteSystemHealth | Native health, readiness, freshness, incidents, and runtime evidence. | src/lite/LiteSystemHealth.jsx |
| LiteHome | Prepared workspace status and next-step presentation. | src/lite/LiteHome.jsx |
| LiteIdentity | Native Identity & Access readiness and authentication state. | src/lite/LiteIdentity.jsx |

## Contract references

| Contract | Values |
| --- | --- |
| OpenAPI paths | /health, /healthz, /ready, /api/health-engine.json, /api/health/check, /api/lite/system/health |
| AsyncAPI subjects | pocketlab.events.health.checked, pocketlab.events.telemetry.sampled, pocketlab.events.command.retired |
| Redaction rules | credentials, tokens, raw logs, private paths |
| Sources | contracts/generated/openapi.json, contracts/asyncapi/pocketlab-nats-jetstream.yaml, contracts/operations/pocketlab-typed-operations.json |

Health GETs read prepared evidence and do not call Gatus, launch PM2 subprocesses, run scanners, migrate databases, or perform live external fan-out. Explicit sampling remains an owned background/command path. The browser reaches telemetry only through FastAPI; it never connects directly to NATS.
