---
title: "GitHub repository"
description: "Hosts source and release workflow definitions; it is not a Lite runtime apply owner."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: f82d3e269a91212087e920fb458fe3869473b363b8e0a4874489074018141ec5
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# GitHub repository

Hosts source and release workflow definitions; it is not a Lite runtime apply owner.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/github.svg" alt="" loading="lazy" decoding="async" /><span>GitHub</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/git.svg" alt="" loading="lazy" decoding="async" /><span>Git</span></span></div>

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
| Architecture icon | brand-github |
| Icon class | brand |
| Icon upstream | GitHub |
| Icon source revision | simple-icons-16.28.0 |
| Icon license | Simple-Icons-CC0 |
| Icon trademark note | GitHub and its logo may be trademarks of GitHub; descriptive use only and no endorsement implied. |
| Technology markers | brand-git |

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

- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Release subprocess and atomic rollback](../release-rollback.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
