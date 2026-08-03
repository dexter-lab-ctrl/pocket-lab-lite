---
title: "Atomic PWA promotion"
description: "Promotes a verified staged PWA atomically and keeps the previous release available for rollback."
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

# Atomic PWA promotion

Promotes a verified staged PWA atomically and keeps the previous release available for rollback.

![Atomic PWA promotion mini architecture](../../../../assets/diagrams/production/components/atomic-promotion.light.svg#only-light)
![Atomic PWA promotion mini architecture](../../../../assets/diagrams/production/components/atomic-promotion.dark.svg#only-dark)


## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | Server host |
| Started / runtime owner | release subprocess |
| Process owner | release apply stage |
| Execution owner | Release runtime |
| Data owner | Active and staged PWA directories |
| Recovery owner | Rollback |
| Security boundary | Server-host boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |

## Inputs

- Verified stage

## Outputs

- New active PWA

## Protocols

- Filesystem atomic rename

## Durable state

- lite_installed_release_identity

## Health and readiness

- active release identity

## Evidence

- promotion result

## Failure behavior

- promotion failure

## Recovery behavior

- retain previous active release

## Connections

### Incoming

- Release subprocess — apply
- Last-known-good state and rollback — restore prior PWA

### Outgoing

- serves active PWA — Caddy same-origin proxy
- validate switched release — Post-switch health validation

## Source verification

- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/release_runtime.py`

## Existing documentation

- [release.md](../../release.md)

## Related architecture views

- [Release subprocess and atomic rollback](../release-rollback.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
