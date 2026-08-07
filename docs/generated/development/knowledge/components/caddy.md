---
title: "Caddy same-origin proxy"
description: "Serves the PWA and routes /api/lite/* and managed app paths without exposing backend secrets."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 1
---

# Caddy same-origin proxy

Serves the PWA and routes /api/lite/* and managed app paths without exposing backend secrets.

## Why it exists

Serves the PWA and routes /api/lite/* and managed app paths without exposing backend secrets.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:caddy` |
| Owner | Same-origin access |
| Execution owner | caddy-proxy |
| Data owner | None |
| Recovery owner | Startup scripts / PM2 |
| Runtime owner | PM2 |
| Runtime process | caddy-proxy |
| Runtime platform | Server host |
| Security boundary | server-host |
| Confidence | verified |

## Responsibilities

- Serves the PWA and routes /api/lite/* and managed app paths without exposing backend secrets.

## Inputs

- HTTPS requests

## Outputs

- Static PWA
- FastAPI requests
- managed app routes

## Health signals

- Caddy validation
- route probes

## Failure modes

- route unavailable
- certificate unavailable

## Recovery behavior

- regenerate validated config
- bounded PM2 restart

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- affected_by: `FastAPI owns the browser-facing control API`
- depends_on: `FastAPI /api/lite/*`
- depends_on: `PhotoPrism`
- protected_by: `Server-host boundary`
- protected_by: `Server-host boundary`
- recovers_with: `FastAPI unavailable`
- recovers_with: `Caddy unavailable`
- recovers_with: `PhotoPrism unavailable`
- recovers_with: `Pocket Lab UI unavailable`
- verified_by: `tests/backend/test_lite_api.py`
- verified_by: `tests/backend/test_lite_device_system_profile.py`
- verified_by: `tests/backend/test_lite_security_s6_frontend_contract.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Atomic PWA promotion`
- depends_on: `Local LAN`
- depends_on: `React / Vite PWA`
- depends_on: `Tailscale remote access`
- uses: `App installation`
- uses: `PhotoPrism operation`
- uses: `Pocket Lab Lite startup`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/caddy.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/lite/restart-caddy-proxy.sh`
- `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh`
