---
title: "Quick, Full, and App safety checks"
description: "Defines bounded profile-specific targets, exclusions, timeouts, coverage summaries, and truthful partial/failed states."
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

# Quick, Full, and App safety checks

Defines bounded profile-specific targets, exclusions, timeouts, coverage summaries, and truthful partial/failed states.

![Quick, Full, and App safety checks mini architecture](../../../../assets/diagrams/production/components/security-profiles.light.svg#only-light)
![Quick, Full, and App safety checks mini architecture](../../../../assets/diagrams/production/components/security-profiles.dark.svg#only-dark)


## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | Security worker |
| Started / runtime owner | pocket-worker |
| Process owner | Security coordinator |
| Execution owner | Security policy |
| Data owner | Security state |
| Recovery owner | Explicit retry |
| Security boundary | Messaging and execution boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |

## Inputs

- Profile and optional app id

## Outputs

- Coverage and findings

## Protocols

- NATS
- Local scanners

## Durable state

- security_profile_snapshots

## Health and readiness

- profile freshness

## Evidence

- coverage_summary

## Failure behavior

- partial/missing target

## Recovery behavior

- truthful partial state
- explicit retry

## Connections

### Incoming

- Security scan coordinator — selects Quick/Full/App

### Outgoing

- defines targets/exclusions — Lynis and Trivy scanner adapters

## Source verification

- `contract` — `contracts/generated/security-profiles.json`
- `nats_subject` — `pocketlab.commands.lite.security.scan`

## Existing documentation

- [security.md](../../security.md)
- [security-profiles.md](../../../development/security-profiles.md)

## Related architecture views

- [Security and safety](../security.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
