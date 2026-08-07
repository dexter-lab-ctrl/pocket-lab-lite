---
title: "SQLite control-plane store"
description: "Stores canonical Lite lifecycle state and prepared projections; the frontend never accesses it directly."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# SQLite control-plane store

Stores canonical Lite lifecycle state and prepared projections; the frontend never accesses it directly.

## Why it exists

Stores canonical Lite lifecycle state and prepared projections; the frontend never accesses it directly.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:sqlite` |
| Owner | Lite control plane store |
| Execution owner | SQLite clients |
| Data owner | Pocket Lab Lite |
| Recovery owner | Database backup/restore |
| Runtime owner | FastAPI and workers |
| Runtime process | SQLite clients |
| Runtime platform | Server host |
| Security boundary | durable-state |
| Confidence | verified |

## Responsibilities

- Stores canonical Lite lifecycle state and prepared projections; the frontend never accesses it directly.

## Inputs

- Transactional lifecycle writes

## Outputs

- Canonical state
- prepared reads

## Health signals

- PRAGMA quick_check
- WAL pressure

## Failure modes

- corruption
- write contention

## Recovery behavior

- checkpoint
- verified database restore

## Evidence

- schema migrations
- quick_check

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- affected_by: `SQLite is durable authority for control-plane state`
- protected_by: `Durable-state boundary`
- protected_by: `Durable-state boundary`
- verified_by: `tests/backend/test_lite_api.py`
- verified_by: `tests/backend/test_lite_control_plane_sqlite_p3.py`
- verified_by: `tests/backend/test_lite_device_health_d4.py`
- verified_by: `tests/backend/test_lite_devices_durable_enrollment.py`
- verified_by: `tests/backend/test_lite_phase3b_security_system_probe_revisions.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `App, command, and workflow state`
- depends_on: `Enrollment and device lifecycle state`
- depends_on: `Invite and identity lifecycle`
- depends_on: `FastAPI /api/lite/*`
- depends_on: `Audit index, projection refresh, prepared projections, and domain revisions`
- depends_on: `Backup, restore, and checkpoint state`
- depends_on: `Installed release and runtime state`
- depends_on: `Explicit retirement and database recovery`
- depends_on: `Security findings and run state`
- uses: `Change Password / identity rotation`
- uses: `Backend-to-Frontend parity capture and verification`
- uses: `Recovery reconciliation`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/sqlite.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_control_plane_store.py`
