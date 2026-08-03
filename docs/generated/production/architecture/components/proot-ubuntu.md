---
title: "PROot Ubuntu application container"
description: "Hosts verified applications such as PhotoPrism without making documentation tooling or the browser a runtime dependency."
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

# PROot Ubuntu application container

Hosts verified applications such as PhotoPrism without making documentation tooling or the browser a runtime dependency.

![PROot Ubuntu application container mini architecture](../../../../assets/diagrams/production/components/proot-ubuntu.light.svg#only-light)
![PROot Ubuntu application container mini architecture](../../../../assets/diagrams/production/components/proot-ubuntu.dark.svg#only-dark)


## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | Android/Termux server host |
| Started / runtime owner | proot-distro |
| Process owner | PM2-launched PROot process |
| Execution owner | Application runtime |
| Data owner | Application-owned state |
| Recovery owner | App lifecycle worker |
| Security boundary | Application-container boundary |
| Supported platforms | Android/Termux, ARM64 |
| Verification | verified |

## Inputs

- Generated app environment

## Outputs

- App process

## Protocols

- Local process / HTTP

## Durable state

- None declared

## Health and readiness

- process status

## Evidence

- None declared

## Failure behavior

- guest unavailable

## Recovery behavior

- explicit install/repair

## Connections

### Incoming

- PM2 process manager — starts app process

### Outgoing

- hosts process — PhotoPrism

## Source verification

- `path` — `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/install-proot-ubuntu.sh`
- `path` — `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/lite/install-photoprism-proot.sh`

## Existing documentation

- [android-termux.md](../../android-termux.md)
- [apps.md](../../apps.md)

## Related architecture views

- [App Catalog lifecycle](../apps.md)
- [Runtime and PM2 process topology](../runtime-topology.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
