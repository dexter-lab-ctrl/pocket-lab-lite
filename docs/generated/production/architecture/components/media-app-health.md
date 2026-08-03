---
title: "Media readiness and app health probes"
description: "Verifies approved media mapping, base-path route health, and app readiness without scanning or exposing user media in documentation."
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

# Media readiness and app health probes

Verifies approved media mapping, base-path route health, and app readiness without scanning or exposing user media in documentation.

![Media readiness and app health probes mini architecture](../../../../assets/diagrams/production/components/media-app-health.light.svg#only-light)
![Media readiness and app health probes mini architecture](../../../../assets/diagrams/production/components/media-app-health.dark.svg#only-dark)


## Ownership and placement

| Field | Value |
| --- | --- |
| Category | decision |
| Runs on | FastAPI / worker |
| Started / runtime owner | Lite API / worker |
| Process owner | app services |
| Execution owner | Apps domain |
| Data owner | Sanitized app projection |
| Recovery owner | App repair |
| Security boundary | Control API boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |

## Inputs

- Route/runtime/storage posture

## Outputs

- route_ready
- media readiness

## Protocols

- HTTP probes
- SQLite

## Durable state

- None declared

## Health and readiness

- operational status

## Evidence

- None declared

## Failure behavior

- media not connected
- route not ready

## Recovery behavior

- connect media safely
- repair

## Connections

### Incoming

- App lifecycle worker — refreshes canonical readiness

### Outgoing

- base-path probe — PhotoPrism

## Source verification

- `route` — `GET /api/lite/apps/photoprism/storage-preview`
- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/lite_catalog_live.py`

## Existing documentation

- [apps.md](../../apps.md)

## Related architecture views

- [App Catalog lifecycle](../apps.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
