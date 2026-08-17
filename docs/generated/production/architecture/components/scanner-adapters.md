---
title: "Lynis and Trivy scanner adapters"
description: "Run bounded backend-owned scanners with target-aware exclusions and sanitized evidence; the browser never executes scanners."
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

# Lynis and Trivy scanner adapters

Run bounded backend-owned scanners with target-aware exclusions and sanitized evidence; the browser never executes scanners.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/scanner.svg" alt="" loading="lazy" decoding="async" /><span>Scanner</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/trivy.svg" alt="" loading="lazy" decoding="async" /><span>Trivy</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/scanner.svg" alt="" loading="lazy" decoding="async" /><span>Scanner</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/scanner-adapters.light.svg" aria-label="Open full-size Lynis and Trivy scanner adapters mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/scanner-adapters.light.svg" alt="Lynis and Trivy scanner adapters mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/scanner-adapters.dark.svg" alt="Lynis and Trivy scanner adapters mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Lynis and Trivy scanner adapters mini architecture. <a href="../../../../../assets/diagrams/production/components/scanner-adapters.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Run bounded backend-owned scanners with target-aware exclusions and sanitized evidence; the browser never executes scanners. |
| Primary inputs | Verified scan plan |
| Primary outputs | normalized findings, coverage summary |
| Protocols / uses | Local subprocess |
| Evidence | sanitized scanner evidence |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | Security worker subprocesses |
| Started / runtime owner | pocket-worker |
| Process owner | scanner subprocess group |
| Execution owner | Security execution |
| Data owner | Sanitized Security evidence |
| Recovery owner | Worker cleanup / retry |
| Security boundary | Messaging and execution boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | semantic-scanner |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | brand-trivy, semantic-scanner |

## Inputs

- Verified scan plan

## Outputs

- normalized findings
- coverage summary

## Protocols

- Local subprocess

## Durable state

- security_scan_tool_runs
- security_scan_evidence_refs

## Health and readiness

- tool status
- timeout status

## Evidence

- sanitized scanner evidence

## Failure behavior

- tool unavailable
- timeout

## Recovery behavior

- kill process group
- record partial state

## Connections

### Incoming

- Security scan coordinator — runs bounded plan
- Quick, Full, and App safety checks — defines targets/exclusions

### Outgoing

- writes normalized results — Security findings and run state

## Source verification

- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/lite_security_policy.py`
- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/lite_security_evidence.py`

## Existing documentation

- [security-profiles.md](../../../development/security-profiles.md)

## Related architecture views

- [Security and safety](../security.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
