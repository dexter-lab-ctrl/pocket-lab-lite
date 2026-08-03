---
title: "GitHub Release"
description: "Publishes the verified Lite release manifest, checksums, and dist.zip assets for the release subprocess."
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

# GitHub Release

Publishes the verified Lite release manifest, checksums, and dist.zip assets for the release subprocess.

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
| Architecture icon | infra-github |

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

- [Network and trust boundaries](../network-boundaries.md)
- [Release subprocess and atomic rollback](../release-rollback.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
