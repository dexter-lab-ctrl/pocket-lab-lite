---
title: "PROot Ubuntu application container"
description: "Hosts verified applications such as PhotoPrism without making documentation tooling or the browser a runtime dependency."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 1
---

# PROot Ubuntu application container

Hosts verified applications such as PhotoPrism without making documentation tooling or the browser a runtime dependency.

## Why it exists

Hosts verified applications such as PhotoPrism without making documentation tooling or the browser a runtime dependency.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:proot-ubuntu` |
| Owner | Application runtime |
| Execution owner | PM2-launched PROot process |
| Data owner | Application-owned state |
| Recovery owner | App lifecycle worker |
| Runtime owner | proot-distro |
| Runtime process | PM2-launched PROot process |
| Runtime platform | Android/Termux server host |
| Security boundary | application-container |
| Confidence | verified |

## Responsibilities

- Hosts verified applications such as PhotoPrism without making documentation tooling or the browser a runtime dependency.

## Inputs

- Generated app environment

## Outputs

- App process

## Health signals

- process status

## Failure modes

- guest unavailable

## Recovery behavior

- explicit install/repair

## Supported platforms

- Android/Termux
- ARM64

## Depends on / uses

- depends_on: `PhotoPrism`
- protected_by: `Application-container boundary`
- protected_by: `Application-container boundary`
- recovers_with: `PhotoPrism unavailable`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `PM2 process manager`
- uses: `PhotoPrism operation`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/proot-ubuntu.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/install-proot-ubuntu.sh`
- `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/lite/install-photoprism-proot.sh`
