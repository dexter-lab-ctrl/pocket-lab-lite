---
title: "Remote-access readiness checks"
description: "Combines tailscaled state, Tailnet IPv4, NATS listener reachability, agent/supervisor status, and safe guidance."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: 70e1e3dd1be588ab4eada0a05875282ebd5daa117f0b647e4f50d7977fccef16
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# Remote-access readiness checks

Combines tailscaled state, Tailnet IPv4, NATS listener reachability, agent/supervisor status, and safe guidance.

![Remote-access readiness checks mini architecture](../../../../assets/diagrams/production/components/remote-readiness.light.svg#only-light)
![Remote-access readiness checks mini architecture](../../../../assets/diagrams/production/components/remote-readiness.dark.svg#only-dark)


## Ownership and placement

| Field | Value |
| --- | --- |
| Category | decision |
| Runs on | FastAPI read surface |
| Started / runtime owner | pocket-api |
| Process owner | FastAPI |
| Execution owner | Lite API |
| Data owner | Prepared status |
| Recovery owner | startup scripts / user guidance |
| Security boundary | Control API boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |

## Inputs

- Tailscale and NATS posture

## Outputs

- Ready or Remote access not ready

## Protocols

- HTTP JSON

## Durable state

- None declared

## Health and readiness

- readiness reasons

## Evidence

- None declared

## Failure behavior

- remote unavailable

## Recovery behavior

- truthful guidance
- safe startup side effects outside reads

## Connections

### Incoming

- Primary and secondary NATS listeners — listener reachability
- tailscaled daemon — daemon status

### Outgoing

- readiness summary — Prepared read, health, readiness, diagnostics, and evidence APIs

## Source verification

- `route` — `GET /api/lite/remote-access/readiness`
- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/lite_status.py`

## Existing documentation

- [remote-access.md](../../remote-access.md)

## Related architecture views

- [Network and trust boundaries](../network-boundaries.md)
- [Tailscale readiness](../remote-access.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
