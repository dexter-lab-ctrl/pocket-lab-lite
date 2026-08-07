---
title: "Local LAN"
description: "Provides local-device access to the same-origin Caddy endpoint without hardcoded addresses."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 1
---

# Local LAN

Provides local-device access to the same-origin Caddy endpoint without hardcoded addresses.

## Why it exists

Provides local-device access to the same-origin Caddy endpoint without hardcoded addresses.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:lan` |
| Owner | Private network |
| Execution owner | Network stack |
| Data owner | None |
| Recovery owner | Network owner |
| Runtime owner | Network |
| Runtime process | Network stack |
| Runtime platform | Private local network |
| Security boundary | tailnet |
| Confidence | verified |

## Responsibilities

- Provides local-device access to the same-origin Caddy endpoint without hardcoded addresses.

## Inputs

- Browser traffic

## Outputs

- Caddy connectivity

## Health signals

- route reachability

## Supported platforms

- Private LAN

## Depends on / uses

- depends_on: `Caddy same-origin proxy`
- protected_by: `Private network and Tailnet boundary`
- protected_by: `Private network and Tailnet boundary`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

No verified backlinks.

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/lan.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `docs/generated/production/caddy-access.md`
