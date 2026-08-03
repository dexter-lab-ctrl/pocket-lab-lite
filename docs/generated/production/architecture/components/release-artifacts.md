---
title: "Date-based Lite tag, dist.zip, checksums, and release manifest"
description: "Defines immutable release identity and the exact assets required for a Lite installation."
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

# Date-based Lite tag, dist.zip, checksums, and release manifest

Defines immutable release identity and the exact assets required for a Lite installation.

![Date-based Lite tag, dist.zip, checksums, and release manifest mini architecture](../../../../assets/diagrams/production/components/release-artifacts.light.svg#only-light)
![Date-based Lite tag, dist.zip, checksums, and release manifest mini architecture](../../../../assets/diagrams/production/components/release-artifacts.dark.svg#only-dark)


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

- [Release subprocess and atomic rollback](../release-rollback.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
