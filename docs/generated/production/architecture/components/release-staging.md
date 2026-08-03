---
title: "Download staging and release verification"
description: "Downloads on explicit/manual or stable cadence, verifies repository/tag/manifest/assets/checksums, and stages without touching the active PWA."
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

# Download staging and release verification

Downloads on explicit/manual or stable cadence, verifies repository/tag/manifest/assets/checksums, and stages without touching the active PWA.

![Download staging and release verification mini architecture](../../../../assets/diagrams/production/components/release-staging.light.svg#only-light)
![Download staging and release verification mini architecture](../../../../assets/diagrams/production/components/release-staging.dark.svg#only-dark)


## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | Release subprocess |
| Started / runtime owner | pocket-worker |
| Process owner | release subprocess |
| Execution owner | Release runtime |
| Data owner | Staging directory and release SQLite state |
| Recovery owner | Discard staging / backoff |
| Security boundary | Messaging and execution boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |

## Inputs

- GitHub release metadata

## Outputs

- verified staged release

## Protocols

- HTTPS
- SHA256

## Durable state

- release_runtime_projection

## Health and readiness

- artifact_verified

## Evidence

- download/verification stages

## Failure behavior

- network/checksum/identity failure

## Recovery behavior

- preserve active release
- bounded backoff

## Connections

### Incoming

- Date-based Lite tag, dist.zip, checksums, and release manifest — download and verify

### Outgoing

- verified stage — Release subprocess

## Source verification

- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/release_orchestrator.py`
- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/lite_release_contract.py`

## Existing documentation

- [release.md](../../release.md)

## Related architecture views

- [Release subprocess and atomic rollback](../release-rollback.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
