<!-- GENERATED FILE: do not edit by hand. Regenerate with `task docs:observability`. -->

# Alerting / SLO Reference

This generated page records the native evidence boundary. It does not claim that an external alerting service is installed or running.

## Current evidence sources

| Source group | Files |
| --- | --- |
| bootstrap_native | 4 |
| fastapi_runtime_observability | 3 |
| frontend_active_lite | 5 |
| native_health_authority | 3 |
| native_telemetry | 4 |
| retirement_documentation | 2 |
| runtime_contracts | 3 |

## Candidate native SLO signals

| Signal |
| --- |
| API liveness and control-plane readiness |
| Prepared health freshness |
| NATS/JetStream and worker-consumer readiness |
| Identity and OPA policy readiness |
| SQLite/storage availability |
| Fleet heartbeat freshness |
| Backup verification and recovery evidence |

Missing or stale observations remain visible as `unknown`/`stale`; they are not converted into green status. Alert routing and notifications are outside this retirement and require separate implementation and qualification.
