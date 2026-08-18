---
title: "Release subprocess"
description: "Owns network, download, verification, staging, apply, and rollback work outside the FastAPI event loop."
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

# Release subprocess

Owns network, download, verification, staging, apply, and rollback work outside the FastAPI event loop.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/release.svg" alt="" loading="lazy" decoding="async" /><span>Release</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/python.svg" alt="" loading="lazy" decoding="async" /><span>Python</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/release-subprocess.light.svg" aria-label="Open full-size Release subprocess mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/release-subprocess.light.svg" alt="Release subprocess mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/release-subprocess.dark.svg" alt="Release subprocess mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Release subprocess mini architecture. <a href="../../../../../assets/diagrams/production/components/release-subprocess.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Owns network, download, verification, staging, apply, and rollback work outside the FastAPI event loop. |
| Primary inputs | Release check/apply command |
| Primary outputs | Verified staged release, release evidence |
| Protocols / uses | IPC queue, HTTPS |
| Evidence | release stage results |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | Dedicated subprocess |
| Started / runtime owner | pocket-worker |
| Process owner | release subprocess |
| Execution owner | Release runtime |
| Data owner | SQLite release state and staging area |
| Recovery owner | Last-known-good rollback |
| Security boundary | Messaging and execution boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | semantic-release |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | brand-python |

## Inputs

- Release check/apply command

## Outputs

- Verified staged release
- release evidence

## Protocols

- IPC queue
- HTTPS

## Durable state

- release_runtime_projection

## Health and readiness

- subprocess generation
- deadline counters

## Evidence

- release stage results

## Failure behavior

- download failure
- verification failure
- post-switch health failure

## Recovery behavior

- bounded backoff
- atomic rollback

## Connections

### Incoming

- Worker process — admits release work
- Download staging and release verification — verified stage

### Outgoing

- apply — Atomic PWA promotion
- updates release state — Installed release and runtime state
- records sanitized lifecycle — Completion and audit evidence

## Source verification

- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/release_update_process.py`
- `sqlite_table` — `release_runtime_projection`

## Existing documentation

- [release.md](../../release.md)
- [rollback.md](../../rollback.md)

## Related architecture views

- [Audit and evidence flow](../audit-evidence.md)
- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Release subprocess and atomic rollback](../release-rollback.md)
- [Runtime and PM2 process topology](../runtime-topology.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
