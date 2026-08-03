---
title: "GitHub repository"
description: "Hosts source and release workflow definitions; it is not a Lite runtime apply owner."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: 13dae80367ddf3ba183f4f77c57075516b1e463d27336c7aa834c23b5cce75a2
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# GitHub repository

Hosts source and release workflow definitions; it is not a Lite runtime apply owner.

> This component is represented in domain diagrams; a dedicated mini diagram is intentionally omitted.


## Function and use

| Field | Value |
| --- | --- |
| Function | Hosts source and release workflow definitions; it is not a Lite runtime apply owner. |
| Primary inputs | Merged source |
| Primary outputs | Tagged workflow |
| Protocols / uses | Git/HTTPS |
| Evidence | None |

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
| Architecture icon | infra-github |

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
