---
title: "Post-switch health validation"
description: "Validates Caddy/FastAPI/PWA health after promotion before declaring the release current."
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

# Post-switch health validation

Validates Caddy/FastAPI/PWA health after promotion before declaring the release current.

![Post-switch health validation mini architecture](../../../../assets/diagrams/production/components/post-switch-health.light.svg#only-light)
![Post-switch health validation mini architecture](../../../../assets/diagrams/production/components/post-switch-health.dark.svg#only-dark)


## Ownership and placement

| Field | Value |
| --- | --- |
| Category | decision |
| Runs on | Release subprocess against local services |
| Started / runtime owner | release subprocess |
| Process owner | release validation stage |
| Execution owner | Release validation |
| Data owner | Release runtime state |
| Recovery owner | Rollback |
| Security boundary | Server-host boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |

## Inputs

- Promoted release

## Outputs

- healthy/current or rollback trigger

## Protocols

- HTTP

## Durable state

- release_runtime_projection

## Health and readiness

- /health
- /ready

## Evidence

- post-switch health

## Failure behavior

- health gate fails

## Recovery behavior

- rollback immediately

## Connections

### Incoming

- Atomic PWA promotion — validate switched release

### Outgoing

- mark current/failed — Installed release and runtime state
- failure trigger — Last-known-good state and rollback

## Source verification

- `route` — `GET /health`
- `route` — `GET /ready`
- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/release_runtime.py`

## Existing documentation

- [release.md](../../release.md)

## Related architecture views

- [Release subprocess and atomic rollback](../release-rollback.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
