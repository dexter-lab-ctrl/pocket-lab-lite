---
title: "Security findings and run state"
description: "Stores scan runs, tools, progress, findings, profile snapshots, and sanitized evidence references."
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

# Security findings and run state

Stores scan runs, tools, progress, findings, profile snapshots, and sanitized evidence references.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/security-state.light.svg" aria-label="Open full-size Security findings and run state mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/security-state.light.svg#only-light" alt="Security findings and run state mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/security-state.dark.svg#only-dark" alt="Security findings and run state mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Security findings and run state mini architecture. <a href="../../../../../assets/diagrams/production/components/security-state.light.svg">View full-size diagram</a></figcaption>
</figure>


## Ownership and placement

| Field | Value |
| --- | --- |
| Category | database |
| Runs on | SQLite and compact sanitized files |
| Started / runtime owner | Security worker |
| Process owner | security services |
| Execution owner | Security domain |
| Data owner | SQLite |
| Recovery owner | Security maintenance / retry |
| Security boundary | Durable-state boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |

## Inputs

- scanner results

## Outputs

- compact Security reads

## Protocols

- SQLite
- JSON

## Durable state

- security_scan_runs
- security_scan_findings

## Health and readiness

- active key
- progress freshness

## Evidence

- sanitized evidence refs

## Failure behavior

- stale accepted run
- scanner timeout

## Recovery behavior

- terminal recovery
- maintenance

## Connections

### Incoming

- Lynis and Trivy scanner adapters — writes normalized results
- Security scan coordinator — updates scan state

### Outgoing

- stored in — SQLite control-plane store

## Source verification

- `sqlite_table` — `security_scan_runs`
- `sqlite_table` — `security_scan_findings`
- `sqlite_table` — `security_scan_evidence_refs`

## Existing documentation

- [security.md](../../security.md)

## Related architecture views

- [SQLite and projection architecture](../data-projections.md)
- [Security and safety](../security.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
