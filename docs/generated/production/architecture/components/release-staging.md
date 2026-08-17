---
title: "Download staging and release verification"
description: "Downloads on explicit/manual or stable cadence, verifies repository/tag/manifest/assets/checksums, and stages without touching the active PWA."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: 765d187cae484a494c7f2602216f3c7ab49cafc2bdffd1ea1b8900f7d1e8e672
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# Download staging and release verification

Downloads on explicit/manual or stable cadence, verifies repository/tag/manifest/assets/checksums, and stages without touching the active PWA.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/release.svg" alt="" loading="lazy" decoding="async" /><span>Release</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/release-staging.light.svg" aria-label="Open full-size Download staging and release verification mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/release-staging.light.svg" alt="Download staging and release verification mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/release-staging.dark.svg" alt="Download staging and release verification mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Download staging and release verification mini architecture. <a href="../../../../../assets/diagrams/production/components/release-staging.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Downloads on explicit/manual or stable cadence, verifies repository/tag/manifest/assets/checksums, and stages without touching the active PWA. |
| Primary inputs | GitHub release metadata |
| Primary outputs | verified staged release |
| Protocols / uses | HTTPS, SHA256 |
| Evidence | download/verification stages |

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
| Architecture icon | semantic-release |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | None |

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
