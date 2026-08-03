---
title: "Quick, Full, and App safety checks"
description: "Defines bounded profile-specific targets, exclusions, timeouts, coverage summaries, and truthful partial/failed states."
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

# Quick, Full, and App safety checks

Defines bounded profile-specific targets, exclusions, timeouts, coverage summaries, and truthful partial/failed states.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/security-profiles.light.svg" aria-label="Open full-size Quick, Full, and App safety checks mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/security-profiles.light.svg#only-light" alt="Quick, Full, and App safety checks mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/security-profiles.dark.svg#only-dark" alt="Quick, Full, and App safety checks mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Quick, Full, and App safety checks mini architecture. <a href="../../../../../assets/diagrams/production/components/security-profiles.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Defines bounded profile-specific targets, exclusions, timeouts, coverage summaries, and truthful partial/failed states. |
| Primary inputs | Profile and optional app id |
| Primary outputs | Coverage and findings |
| Protocols / uses | NATS, Local scanners |
| Evidence | coverage_summary |

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
| Architecture icon | infra-security |

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
