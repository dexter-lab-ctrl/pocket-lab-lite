<!-- GENERATED FILE: do not edit by hand. Regenerate with `task docs:observability`. -->

# Observability Runtime Map

This map connects current Lite-native UI surfaces to the authoritative control-plane paths. Legacy pages remain as generated retirement notices so historical links do not become misleading setup instructions.

| Surface | Route | Authority | Consumer / replacement |
| --- | --- | --- | --- |
| Native System Health | /health, /healthz, /ready, /api/health-engine.json, /api/lite/system/health | Prepared native projection | LiteSystemHealth / LiteHome |
| Native Identity & Access | /api/lite/identity | SQLite-backed identity readiness | LiteIdentity |
| Native telemetry / diagnostics | /api/telemetry.json, /api/telemetry/live/status, /api/nats/status, /api/workers/status | Prepared runtime observations | System Health / diagnostics |
| Events | /api/events/recent, /ws/events | NATS / event journal | Operation activity |
| Retired observability status | /api/observability/status | Deterministic HTTP 410 | Native System Health and diagnostics |
| Retired GitOps compatibility | /api/pipeline_status.json, /api/gitops/health.json, /api/git_history.json | Deterministic HTTP 410 | Native release/source and drift checks |

## Source groups

| Group | Files |
| --- | --- |
| bootstrap_native | 4 |
| fastapi_runtime_observability | 3 |
| frontend_active_lite | 5 |
| native_health_authority | 3 |
| native_telemetry | 4 |
| retirement_documentation | 2 |
| runtime_contracts | 3 |

## Validation boundary

Static generation proves source fingerprints and documentation freshness only. Runtime readiness, performance, disposable installation/upgrade, mocked browser behavior, CI, and physical Android qualification must be reported separately.
