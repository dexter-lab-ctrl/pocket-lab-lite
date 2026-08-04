---
title: "Date-based Lite tag, dist.zip, checksums, and release manifest"
description: "Defines immutable release identity and the exact assets required for a Lite installation."
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

# Date-based Lite tag, dist.zip, checksums, and release manifest

Defines immutable release identity and the exact assets required for a Lite installation.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/artifact.svg" alt="" loading="lazy" decoding="async" /><span>Artifact</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/git.svg" alt="" loading="lazy" decoding="async" /><span>Git</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/release-artifacts.light.svg" aria-label="Open full-size Date-based Lite tag, dist.zip, checksums, and release manifest mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/release-artifacts.light.svg" alt="Date-based Lite tag, dist.zip, checksums, and release manifest mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/release-artifacts.dark.svg" alt="Date-based Lite tag, dist.zip, checksums, and release manifest mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Date-based Lite tag, dist.zip, checksums, and release manifest mini architecture. <a href="../../../../../assets/diagrams/production/components/release-artifacts.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Defines immutable release identity and the exact assets required for a Lite installation. |
| Primary inputs | Source commit |
| Primary outputs | verified release identity |
| Protocols / uses | ZIP, JSON, SHA256 |
| Evidence | release manifest |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | artifact |
| Runs on | GitHub Release / staging |
| Started / runtime owner | Release workflow |
| Process owner | GitHub Actions |
| Execution owner | Release engineering |
| Data owner | Release assets |
| Recovery owner | Release workflow |
| Security boundary | External release boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | semantic-artifact |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | brand-git |

## Inputs

- Source commit

## Outputs

- verified release identity

## Protocols

- ZIP
- JSON
- SHA256

## Durable state

- None declared

## Health and readiness

- checksums match

## Evidence

- release manifest

## Failure behavior

- tag or manifest mismatch

## Recovery behavior

- reject release

## Connections

### Incoming

- GitHub Release — publishes assets

### Outgoing

- download and verify — Download staging and release verification

## Source verification

- `literal` — `.github/workflows/release-dist.yml` contains `lite-`
- `literal` — `.github/workflows/release-dist.yml` contains `dist.zip`

## Existing documentation

- [release.md](../../release.md)

## Related architecture views

- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Release subprocess and atomic rollback](../release-rollback.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
