---
title: "FastAPI /api/lite/*"
description: "Validates requests, owns safe read APIs, admits commands, and never delegates browser execution directly to NATS or shell."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 3
---

# FastAPI /api/lite/*

Validates requests, owns safe read APIs, admits commands, and never delegates browser execution directly to NATS or shell.

## Why it exists

Validates requests, owns safe read APIs, admits commands, and never delegates browser execution directly to NATS or shell.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:lite-api` |
| Owner | Lite API |
| Execution owner | pocket-api |
| Data owner | SQLite prepared reads |
| Recovery owner | PM2 after NATS/SQLite verification |
| Runtime owner | PM2 |
| Runtime process | pocket-api |
| Runtime platform | Server host |
| Security boundary | control-api |
| Confidence | verified |

## Responsibilities

- Validates requests, owns safe read APIs, admits commands, and never delegates browser execution directly to NATS or shell.

## Inputs

- Same-origin requests

## Outputs

- Prepared reads
- validated commands

## Health signals

- GET /health
- GET /ready

## Failure modes

- NATS unavailable
- SQLite unavailable

## Recovery behavior

- fail writes closed
- serve safe last committed reads

## Evidence

- request lifecycle
- command acceptance

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- affected_by: `FastAPI owns the browser-facing control API`
- depends_on: `Fleet, Apps, Security, Recovery, and Release APIs`
- depends_on: `Identity, authentication, and invite guards`
- depends_on: `Prepared read, health, readiness, diagnostics, and evidence APIs`
- depends_on: `SQLite control-plane store`
- protected_by: `Control API boundary`
- protected_by: `Control API boundary`
- recovers_with: `FastAPI unavailable`
- recovers_with: `Caddy unavailable`
- related_to: `pocketlab.commands.lite.backup.create`
- related_to: `pocketlab.commands.lite.backup.verify`
- related_to: `pocketlab.commands.lite.database.backup`
- related_to: `pocketlab.commands.lite.database.backup.verify`
- related_to: `pocketlab.commands.lite.database.restore`
- related_to: `pocketlab.commands.lite.database.restore.preview`
- related_to: `pocketlab.commands.lite.maintenance.checkpoint`
- related_to: `pocketlab.commands.lite.maintenance.retention`
- related_to: `pocketlab.commands.lite.restore.apply`
- related_to: `pocketlab.commands.lite.restore.preview`
- uses: `GET /api/lite/status`
- verified_by: `tests/backend/test_lite_api.py`
- verified_by: `tests/backend/test_lite_control_plane_sqlite_p3.py`
- verified_by: `tests/backend/test_lite_device_health_d4.py`
- verified_by: `tests/backend/test_lite_long_gate_submission_recovery.py`
- verified_by: `tests/backend/test_lite_phase3b_security_system_probe_revisions.py`
- verified_by: `tests/backend/test_lite_phase3c_system_aggregates.py`
- verified_by: `tests/backend/test_lite_revision_sync_n4_n5.py`
- verified_by: `tests/backend/test_lite_security_f11_events_contract.py`
- verified_by: `tests/backend/test_lite_security_f3_summary_contract.py`
- verified_by: `tests/backend/test_lite_security_f7_split_read_contract.py`
- verified_by: `tests/backend/test_lite_security_f9_etag_contract.py`
- verified_by: `tests/backend/test_lite_security_p2b_reboot_generation.py`
- verified_by: `tests/backend/test_lite_security_s6_retention.py`
- verified_by: `tests/backend/test_lite_security_s8_recovery.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/mkdocs.spec.ts`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_enterprise_completion.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Caddy same-origin proxy`
- uses: `Local owner password and session lifecycle`
- uses: `Backend-to-Frontend parity capture and verification`
- uses: `Safety Rules authorization decision`
- uses: `Pocket Lab Lite startup`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/lite-api.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py`
