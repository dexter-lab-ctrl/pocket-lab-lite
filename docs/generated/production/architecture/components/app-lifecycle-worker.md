---
title: "App lifecycle worker"
description: "Owns install, repair, media import, backup, restore preview, update readiness/apply, and removal paths only where implemented and safe."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: f82d3e269a91212087e920fb458fe3869473b363b8e0a4874489074018141ec5
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# App lifecycle worker

Owns install, repair, media import, backup, restore preview, update readiness/apply, and removal paths only where implemented and safe.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/worker.svg" alt="" loading="lazy" decoding="async" /><span>Worker</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/app-lifecycle-worker.light.svg" aria-label="Open full-size App lifecycle worker mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/app-lifecycle-worker.light.svg" alt="App lifecycle worker mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/app-lifecycle-worker.dark.svg" alt="App lifecycle worker mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>App lifecycle worker mini architecture. <a href="../../../../../assets/diagrams/production/components/app-lifecycle-worker.light.svg">View full-size diagram</a></figcaption>
</figure>

The mini diagram deterministically collapses **1** additional connections.


## Function and use

| Field | Value |
| --- | --- |
| Function | Owns install, repair, media import, backup, restore preview, update readiness/apply, and removal paths only where implemented and safe. |
| Primary inputs | App command |
| Primary outputs | App lifecycle state, sanitized details |
| Protocols / uses | NATS, SQLite, local process |
| Evidence | app action lifecycle |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | pocket-worker |
| Started / runtime owner | PM2 |
| Process owner | pocket-worker |
| Execution owner | Apps execution |
| Data owner | App lifecycle SQLite state |
| Recovery owner | Worker retry / repair |
| Security boundary | Messaging and execution boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | semantic-worker |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | None |

## Inputs

- App command

## Outputs

- App lifecycle state
- sanitized details

## Protocols

- NATS
- SQLite
- local process

## Durable state

- app_current_state
- app_action_lifecycle

## Health and readiness

- action progress
- route health

## Evidence

- app action lifecycle

## Failure behavior

- operation failed

## Recovery behavior

- non-destructive repair
- explicit retry

## Connections

### Incoming

- Worker process — runs app work

### Outgoing

- runs backup/update paths — App backup, restore preview, and update lifecycle
- refreshes canonical readiness — Media readiness and app health probes
- updates app state — App, command, and workflow state
- records sanitized lifecycle — Completion and audit evidence

## Source verification

- `path` — `pocket-lab-final-structure/runtime/workers/pocketlab_worker.py`
- `nats_subject` — `pocketlab.commands.lite.app.repair`
- `nats_subject` — `pocketlab.commands.lite.app.update.check`

## Existing documentation

- [apps.md](../../apps.md)

## Related architecture views

- [App Catalog lifecycle](../apps.md)
- [Audit and evidence flow](../audit-evidence.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
