---
title: "Architecture diagram catalog"
description: "Generated light and dark architecture diagrams for Pocket Lab Lite."
status: verified
generated: true
audience: development
generator: scripts/docs/graphviz/generate_lite_diagrams.py
schema_revision: 1
validation_status: generated
---

# Architecture diagram catalog

These diagrams are generated from `architecture/metadata/diagrams.json`. Edit the metadata, then run `task lite:docs:generate`; never hand-edit generated DOT or SVG files.

## Agent and supervisor recovery

Disconnected agents reconnect; stopped agents are recovered by a separate supervisor; identity mismatch fails closed.

![Agent and supervisor recovery](../../assets/diagrams/agent-supervisor-recovery.light.svg#only-light)

![Agent and supervisor recovery](../../assets/diagrams/agent-supervisor-recovery.dark.svg#only-dark)

## App Catalog lifecycle

Catalog discovery, validated lifecycle actions, worker execution, canonical state, readiness, evidence, and recovery remain backend-owned and auditable.

![App Catalog lifecycle](../../assets/diagrams/app-catalog-lifecycle.light.svg#only-light)

![App Catalog lifecycle](../../assets/diagrams/app-catalog-lifecycle.dark.svg#only-dark)

## Backup retention and explicit retirement

Verified backups follow bounded retention while device or app retirement remains explicit, dependency-aware, transactional, and historically auditable.

![Backup retention and explicit retirement](../../assets/diagrams/backup-retention-retirement.light.svg#only-light)

![Backup retention and explicit retirement](../../assets/diagrams/backup-retention-retirement.dark.svg#only-dark)

## Command acknowledgement and reconciliation

Commands move from validated admission through durable delivery, acknowledgement, execution evidence, timeout reconciliation, and prepared lifecycle reads without deleting devices.

![Command acknowledgement and reconciliation](../../assets/diagrams/command-acknowledgement-reconciliation.light.svg#only-light)

![Command acknowledgement and reconciliation](../../assets/diagrams/command-acknowledgement-reconciliation.dark.svg#only-dark)

## Pocket Lab Lite control plane

Same-origin UI requests flow through Caddy and FastAPI to NATS, workers, agents, evidence, and prepared reads.

![Pocket Lab Lite control plane](../../assets/diagrams/control-plane.light.svg#only-light)

![Pocket Lab Lite control plane](../../assets/diagrams/control-plane.dark.svg#only-dark)

## Device offline-retention lifecycle

Enrollment remains durable when live discovery disappears; devices transition to offline or stale until explicit repair, rejoin, retirement, or removal.

![Device offline-retention lifecycle](../../assets/diagrams/device-offline-retention.light.svg#only-light)

![Device offline-retention lifecycle](../../assets/diagrams/device-offline-retention.dark.svg#only-dark)

## Device onboarding lifecycle

Backend-owned invite creation and fail-closed identity checks lead to agent and supervisor heartbeats.

![Device onboarding lifecycle](../../assets/diagrams/device-onboarding.light.svg#only-light)

![Device onboarding lifecycle](../../assets/diagrams/device-onboarding.dark.svg#only-dark)

## Frontend state ownership

TanStack Query owns server synchronization, Dexie owns durable offline snapshots, Zustand owns lightweight UI preferences, and XState owns bounded workflows; selectors merge them into truthful Lite screens.

![Frontend state ownership](../../assets/diagrams/frontend-state-ownership.light.svg#only-light)

![Frontend state ownership](../../assets/diagrams/frontend-state-ownership.dark.svg#only-dark)

## Prepared projection flow

Canonical events are admitted through bounded schedulers and promoted atomically to prepared SQLite reads.

![Prepared projection flow](../../assets/diagrams/projection-flow.light.svg#only-light)

![Prepared projection flow](../../assets/diagrams/projection-flow.dark.svg#only-dark)

## Backup and restore state machine

Backup, verification, preview, checkpoint, restore, health validation, and rollback remain backend and worker owned.

![Backup and restore state machine](../../assets/diagrams/recovery-state-machine.light.svg#only-light)

![Backup and restore state machine](../../assets/diagrams/recovery-state-machine.dark.svg#only-dark)

## Release subprocess and atomic rollback

Release checks and applies run outside the API process, validate identity and artifacts, stage dist.zip, promote atomically, verify health, and roll back to the last known good release on failure.

![Release subprocess and atomic rollback](../../assets/diagrams/release-atomic-rollback.light.svg#only-light)

![Release subprocess and atomic rollback](../../assets/diagrams/release-atomic-rollback.dark.svg#only-dark)

## Lite release flow

Annotated date-based tags produce verified dist.zip artifacts and atomic PWA promotion with rollback.

![Lite release flow](../../assets/diagrams/release-flow.light.svg#only-light)

![Lite release flow](../../assets/diagrams/release-flow.dark.svg#only-dark)

## Runtime deployment

Development documentation tools remain outside the Android/Termux production runtime.

![Runtime deployment](../../assets/diagrams/runtime-deployment.light.svg#only-light)

![Runtime deployment](../../assets/diagrams/runtime-deployment.dark.svg#only-dark)

## Security scan lifecycle

Quick and full safety checks progress through bounded admission, isolated execution, canonical findings, sanitized evidence, and truthful UI summaries.

![Security scan lifecycle](../../assets/diagrams/security-scan-lifecycle.light.svg#only-light)

![Security scan lifecycle](../../assets/diagrams/security-scan-lifecycle.dark.svg#only-dark)

## Tailscale remote-access readiness

Startup-owned Tailscale side effects and safe read APIs verify tailscaled, Tailnet IPv4, NATS binding, secondary connectivity, and agent health before declaring remote access ready.

![Tailscale remote-access readiness](../../assets/diagrams/tailscale-remote-readiness.light.svg#only-light)

![Tailscale remote-access readiness](../../assets/diagrams/tailscale-remote-readiness.dark.svg#only-dark)

## Trust boundaries

The browser cannot execute shell commands, access NATS directly, or hold backend secrets.

![Trust boundaries](../../assets/diagrams/trust-boundaries.light.svg#only-light)

![Trust boundaries](../../assets/diagrams/trust-boundaries.dark.svg#only-dark)
