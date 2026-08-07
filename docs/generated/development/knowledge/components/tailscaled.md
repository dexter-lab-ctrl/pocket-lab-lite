---
title: "tailscaled daemon"
description: "Owns Tailscale networking; startup scripts may detect/start it safely while read APIs remain side-effect-free."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 1
---

# tailscaled daemon

Owns Tailscale networking; startup scripts may detect/start it safely while read APIs remain side-effect-free.

## Why it exists

Owns Tailscale networking; startup scripts may detect/start it safely while read APIs remain side-effect-free.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:tailscaled` |
| Owner | Remote access runtime |
| Execution owner | tailscaled |
| Data owner | Local Tailscale state |
| Recovery owner | startup scripts |
| Runtime owner | startup scripts |
| Runtime process | tailscaled |
| Runtime platform | Android/Termux server host |
| Security boundary | server-host |
| Confidence | verified |

## Responsibilities

- Owns Tailscale networking; startup scripts may detect/start it safely while read APIs remain side-effect-free.

## Inputs

- Tailscale configuration

## Outputs

- Tailnet interface/IP

## Health signals

- daemon state

## Failure modes

- daemon unavailable

## Recovery behavior

- start when safe

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `Remote-access readiness checks`
- depends_on: `Tailscale remote access`
- protected_by: `Server-host boundary`
- protected_by: `Server-host boundary`
- recovers_with: `Remote access not ready`
- recovers_with: `Tailscale unavailable`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- uses: `Tailscale and remote access readiness`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/tailscaled.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/install-tailscale.sh`
