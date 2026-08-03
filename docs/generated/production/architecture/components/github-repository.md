---
title: "GitHub repository"
description: "Hosts source and release workflow definitions; it is not a Lite runtime apply owner."
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

# GitHub repository

Hosts source and release workflow definitions; it is not a Lite runtime apply owner.

> This component is represented in domain diagrams; a dedicated mini diagram is intentionally omitted.


## Ownership and placement

| Field | Value |
| --- | --- |
| Category | external |
| Runs on | External source hosting |
| Started / runtime owner | GitHub |
| Process owner | GitHub Actions |
| Execution owner | Repository maintainers |
| Data owner | Git repository |
| Recovery owner | Repository maintainers |
| Security boundary | External release boundary |
| Supported platforms | External service |
| Verification | verified |

## Inputs

- Merged source

## Outputs

- Tagged workflow

## Protocols

- Git/HTTPS

## Durable state

- None declared

## Health and readiness

- workflow status

## Evidence

- None declared

## Failure behavior

- workflow failure

## Recovery behavior

- fix via PR

## Connections

### Incoming

- None declared

### Outgoing

- annotated tag workflow — GitHub Release

## Source verification

- `path` — `.github/workflows/release-dist.yml`

## Existing documentation

- [release.md](../../release.md)

## Related architecture views

- [Release subprocess and atomic rollback](../release-rollback.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
