---
title: Shared Device Facts, Telemetry & Capability Projection
description: Canonical architecture for resource observations, capability verification, runtime services, software posture, and Lite API/UI projection.
status: implemented
audience: architecture
---

# Shared Device Facts, Telemetry & Capability Projection

Pocket Lab Lite uses one canonical Device Facts path for Server Host and secondary-device resource truth. Home and Devices do not own independent telemetry semantics.

## Data flow

```text
Server central sampler / node agent
        ↓
resource_telemetry providers
        ↓
canonical resource observations
        ↓
lite_device_facts reconciliation
        ↓
prepared SQLite / Phase3 projections
        ↓
/status · /fleet · /devices/{id} · /devices/{id}/health
        ↓
liteDeviceFacts frontend normalization
        ↓
Home compact facts · Devices detailed facts
```

Execution remains outside this read path:

```text
UI → FastAPI /api/lite/* → NATS/JetStream → worker/agent/supervisor
```

The frontend never talks to NATS, executes shell commands, or stores backend secrets.

## Resource observations

Each supported metric is collected independently so one failure cannot invalidate the rest of the sample. Canonical observations carry:

- metric and bounded value;
- unit;
- collection/status state;
- source;
- observation time and freshness;
- reason code and support state;
- schema version/revision where available.

States distinguish available/current truth from stale, missing, unsupported, permission-denied, transient/unavailable, blocked, and not-applicable evidence. Missing or unsupported metrics are never represented as fabricated `0` values.

### Provider behavior

- **Memory:** bounded `/proc/meminfo` parsing; denial or malformed data is non-fatal.
- **Storage:** `statvfs`; no `df` shell call.
- **CPU utilization:** `/proc/stat` delta; first sample may be verification-pending.
- **Load:** optional platform load provider; failure does not affect CPU or other metrics.
- **Uptime:** monotonic boot clock first, `/proc/uptime` only as fallback.
- **Thermal:** dynamic CPU/SoC-oriented thermal discovery; battery/modem/peripheral sensors and sentinel/unrealistic values are rejected.

Providers are bounded and require no root privileges.

## Reconciliation and freshness

`lite_device_facts` selects the strongest current observation per metric. Fresh canonical telemetry wins over stale `system_health` compatibility data. Heartbeat freshness, resource freshness, system-profile freshness, capability freshness, runtime-service freshness, and software freshness remain independent.

Observation-only refreshes update prepared Device Facts without fabricating semantic health transitions.

## Capability lifecycle

Capabilities are backend-owned records generated from the capability registry and verification adapters. The lifecycle is:

```text
not_advertised
advertised
verification_pending
verified
unavailable
unsupported
stale
blocked
not_applicable
```

Advertisement is evidence that a device claims support; it is not proof that the capability is usable. `verified_at` exists only after authoritative runtime verification.

Verification uses the real domain source where available:

- control-plane readiness for `serve_control_plane`;
- hosted-app runtime for `host_apps`;
- command-delivery evidence for `receive_commands`;
- supervisor evidence for recovery;
- Tailscale/Tailnet plus NATS readiness for `remote_access`;
- security execution evidence for safety checks;
- configured storage/backup/restore readiness for storage capabilities;
- media permission/readiness for phone-media access.

A capability record is descriptive and never bypasses FastAPI/OPA/approval/confirmation authorization.

## Runtime services

Runtime services are dynamic backend-owned facts. Server Host process collection enumerates the prepared process-manager snapshot without encoding a fixed Pocket Lab process list. Secondary devices expose only services reported for that device through agent/supervisor evidence.

Public service facts contain only bounded fields such as service id, label, category, manager, state, reported time, freshness, restart support/reason, source, and schema version. Environment contents, command arguments, credentials, private paths, and NATS secrets are excluded.

## Software posture

Agent and supervisor versions are reconciled from authoritative runtime/supervisor evidence and last-good system profile data. Exact version observations are preserved with source and freshness. Current, stale, outdated, incompatible, unknown, and verification-pending conditions remain distinguishable rather than collapsing to `unknown`.

## Android and Termux limitations

Android may restrict `/proc` and thermal sysfs access. These are expected partial-support conditions, not fatal errors. Pocket Lab Lite therefore:

- does not require `/proc/loadavg`;
- does not require `/proc/uptime` when a monotonic boot clock is available;
- tolerates permission denial per metric;
- treats thermal data as optional;
- keeps the rest of the Device Facts sample usable when one provider fails.

## Backward compatibility

Legacy telemetry aliases remain readable while Home and Devices migrate to canonical `device_facts`. Older agents that omit a metric render it as unsupported/not reported instead of broken. Unknown future capability and runtime-service identifiers render dynamically without requiring a frontend switch statement.

## Read-side safety

Opening Home, Devices, device details, or health performs prepared reads only. Read routes do not start Tailscale, restart agents/supervisors, run scans, queue commands, or execute repairs. Startup scripts, workers, agents, and supervisors retain side-effect ownership.
