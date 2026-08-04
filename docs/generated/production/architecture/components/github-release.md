---
title: "GitHub Release"
description: "Publishes the verified Lite release manifest, checksums, and dist.zip assets for the release subprocess."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: 20bffc9aa51b0c5cedb30ae9e2be0a9cfb0925972f81f056d9792accd7d4e7ee
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# GitHub Release

Publishes the verified Lite release manifest, checksums, and dist.zip assets for the release subprocess.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/github.svg" alt="" loading="lazy" decoding="async" /><span>GitHub</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/git.svg" alt="" loading="lazy" decoding="async" /><span>Git</span></span></div>

> This component is represented in domain diagrams; a dedicated mini diagram is intentionally omitted.


## Function and use

| Field | Value |
| --- | --- |
| Function | Publishes the verified Lite release manifest, checksums, and dist.zip assets for the release subprocess. |
| Primary inputs | Annotated Lite tag |
| Primary outputs | Release assets |
| Protocols / uses | HTTPS |
| Evidence | None |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | external |
| Runs on | GitHub |
| Started / runtime owner | GitHub Actions |
| Process owner | release-dist workflow |
| Execution owner | Release workflow |
| Data owner | Release assets |
| Recovery owner | Release workflow rerun/fix |
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

- Annotated Lite tag

## Outputs

- Release assets

## Protocols

- HTTPS

## Durable state

- None declared

## Health and readiness

- asset manifest validation

## Evidence

- None declared

## Failure behavior

- missing asset

## Recovery behavior

- do not apply; publish corrected release

## Connections

### Incoming

- GitHub repository — annotated tag workflow

### Outgoing

- publishes assets — Date-based Lite tag, dist.zip, checksums, and release manifest

## Source verification

- `literal` — `.github/workflows/release-dist.yml` contains `dist.zip`
- `literal` — `.github/workflows/release-dist.yml` contains `checksums.txt`
- `literal` — `.github/workflows/release-dist.yml` contains `pocketlab-lite-release.json`

## Existing documentation

- [release.md](../../release.md)

## Related architecture views

- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Network and trust boundaries](../network-boundaries.md)
- [Release subprocess and atomic rollback](../release-rollback.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
