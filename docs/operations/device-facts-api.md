---
title: Device Facts API projection
description: Operator-facing canonical fields and parity expectations for Lite status, fleet, device details, and device health.
status: implemented
audience: operations
---

# Device Facts API projection

Device Facts are the canonical sanitized resource/capability/service/software facts returned by Pocket Lab Lite read APIs.

## Read surfaces

The following routes derive from the same canonical facts:

```text
GET /api/lite/status
GET /api/lite/fleet
GET /api/lite/devices/{device_id}
GET /api/lite/devices/{device_id}/health
```

`/status` exposes Server Host `device_facts` for Home. Fleet/device/health expose the same resource semantics for Devices. Detailed endpoints may include more metadata, but values, reason codes, provenance, and freshness must not contradict the fleet/status projection for the same observation revision.

## Canonical fields

A Device Facts payload contains:

```text
schema_version
device_id
resources
software
observed_at
sanitized
```

Each resource observation can include:

```text
metric
value
unit
status
collection_status
source
observed_at
freshness
reason_code
support_state
schema_version
revision
```

Device projections can additionally expose:

```text
capability_states
runtime_services
proactive_health
restart_agent_assessment
dependencies
```

## Interpreting state

- `available/current`: use the value.
- `stale`: saved value is visible but must not be described as current.
- `unsupported`: the platform/provider does not support the metric.
- `permission_denied`: collection was blocked by platform permissions.
- `missing`: no usable observation exists.
- `transient/unavailable`: collection failed temporarily.

Do not substitute numeric zero for any unavailable state.

## Sanitization

Public payloads never include process environment contents, command-line arguments, NATS credentials, tokens, API keys, Tailscale auth keys, or private filesystem paths. Unexpected secret-like metadata is dropped rather than surfaced.

## Troubleshooting

When Home and Devices appear inconsistent, compare the observation `source`, `observed_at`, `freshness`, and `reason_code` on all four read surfaces before treating the UI as a collector problem. For an offline secondary device, stale last-good facts are expected and should remain visibly stale until fresh agent evidence arrives.

The generated field/registry contract is available at **Build & Test → Device Facts contract**.
