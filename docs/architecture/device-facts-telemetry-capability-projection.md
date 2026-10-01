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

## Governed device roles and effective capabilities

Pocket Lab Lite separates **human authority**, **device responsibility**, and
**runtime capability**.

```text
human identity
  → human membership role (Owner/Admin/Operator/Auditor/Viewer)
  → Rules / OPA decision
  → durable device-role assignment (Compute / Storage)
  → node-agent role attestation and capability advertisement
  → FastAPI identity/freshness/runtime verification
  → effective capability projection
```

Human roles answer **who may request a Fleet change**. Device roles answer
**what responsibilities a device is authorized to assume**. Runtime capability
evidence answers **what the device currently reports and can actually provide**.
The browser is not authoritative for any of those decisions.

The canonical joinable role set is a bounded list:

```json
{
  "device_roles": ["compute", "storage"]
}
```

`server_host` remains protected and non-joinable. A joined device may be
Compute-only, Storage-only, or Compute + Storage. The legacy single `role` field
remains only as a lossy compatibility projection for older consumers.

Durable desired/active assignment state is stored in normalized SQLite role
assignment rows. Role changes carry a generation and request fingerprint so a
stale response or delayed device acknowledgement cannot overwrite newer desired
state. Agent/supervisor environment compatibility is preserved with
`POCKETLAB_NODE_ROLE`, while canonical agents also carry `POCKETLAB_NODE_ROLES`
and the role generation.

### Authorization and verification are distinct

Assigned roles authorize a bounded capability set, but assignment alone never
makes a capability effective. Device-advertised roles and capabilities are
observations only and cannot self-escalate authority.

Conceptually:

```text
effective capability =
  authorized by assigned device role
  ∩ advertised/observed by the device
  ∩ verified by FastAPI/runtime evidence
  ∩ fresh enough for the capability
  ∩ not blocked by current Rules or lifecycle state
```

This permits partial degradation. A Compute + Storage device can keep Compute
ready while Storage is not advertised, unavailable, or stale.

Photo Backup Source remains independent from the Storage role. A phone may have
photo-source capabilities such as media access or backup tooling without being
authorized as a Storage target. Conversely, assigning Storage does not imply
photo-library source access.

### Human governance

Personal Mode keeps the local Owner as the human authority, subject to hard
safety checks. Enterprise Mode projects Fleet actions into the shared Identity &
Access action matrix and evaluates mutations through Rules/OPA. Higher-risk
Storage assignment/removal can require the existing independent approval
continuation for delegated Admin/Operator flows. Continuations are server-owned
and bound to the exact action, device, role-set fingerprint, authorization
version, policy revision, and expiry; the frontend cannot fabricate approval.

Role removal changes authorization/responsibility only. External backup/media
data is not implicitly deleted. Removing Storage is blocked while backend
dependency evidence still shows active backup, restore, or storage mappings.

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
