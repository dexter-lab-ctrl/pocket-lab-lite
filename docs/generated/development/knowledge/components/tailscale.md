---
title: "Tailscale remote access"
description: "Provides private Tailnet connectivity and HTTPS identity without becoming a browser-held secret or control owner."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 1
---

# Tailscale remote access

Provides private Tailnet connectivity and HTTPS identity without becoming a browser-held secret or control owner.

## Why it exists

Provides private Tailnet connectivity and HTTPS identity without becoming a browser-held secret or control owner.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:tailscale` |
| Owner | Remote access |
| Execution owner | tailscaled |
| Data owner | Tailscale local state |
| Recovery owner | Startup scripts |
| Runtime owner | tailscaled |
| Runtime process | tailscaled |
| Runtime platform | Server host and joined devices |
| Security boundary | tailnet |
| Confidence | verified |

## Responsibilities

- Provides private Tailnet connectivity and HTTPS identity without becoming a browser-held secret or control owner.

## Inputs

- Tailnet identity

## Outputs

- Tailnet IPv4
- private reachability

## Health signals

- Tailnet IPv4
- peer reachability

## Failure modes

- tailscaled stopped
- no Tailnet IP

## Recovery behavior

- safe startup
- readiness guidance

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `Caddy same-origin proxy`
- depends_on: `Primary and secondary NATS listeners`
- protected_by: `Private network and Tailnet boundary`
- protected_by: `Private network and Tailnet boundary`
- recovers_with: `Device offline or reconnecting`
- recovers_with: `Remote access not ready`
- recovers_with: `Tailscale unavailable`
- uses: `GET /api/lite/remote-access/readiness`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `tailscaled daemon`
- uses: `Tailscale and remote access readiness`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/tailscale.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/install-tailscale.sh`
