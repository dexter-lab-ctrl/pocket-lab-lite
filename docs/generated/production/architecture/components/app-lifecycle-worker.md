---
title: "App lifecycle worker"
description: "Owns install, repair, media import, backup, restore preview, update readiness/apply, and removal paths only where implemented and safe."
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

# App lifecycle worker

Owns install, repair, media import, backup, restore preview, update readiness/apply, and removal paths only where implemented and safe.

![App lifecycle worker mini architecture](../../../../assets/diagrams/production/components/app-lifecycle-worker.light.svg#only-light)
![App lifecycle worker mini architecture](../../../../assets/diagrams/production/components/app-lifecycle-worker.dark.svg#only-dark)

The mini diagram deterministically collapses **1** additional connections.


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
