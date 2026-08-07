---
title: "Security threat models"
description: "Trust-boundary threat/failure views derived from canonical architecture."
generated: true
audience: knowledgebase
confidence: inferred
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 1
---

# Security threat models

Threat/failure modes are labeled inferred when they are derived from verified boundary/component failure metadata rather than a historical incident.

## Application-container boundary

PROot Ubuntu and managed application runtime.

**Assets:** PhotoPrism, PROot Ubuntu application container

**Entry points:** HTTP behind Caddy, Local process / HTTP

**Threats/failure modes:** guest unavailable, process stopped, route 404

**Mitigations/recovery:** explicit install/repair, process recovery, route-aware repair

## Browser trust boundary

User device, browser, PWA, and safe local frontend state.

**Assets:** Browser, Frontend state ownership, React / Vite PWA, User

**Entry points:** Fetch API, HTTPS, HTTPS JSON, IndexedDB

**Threats/failure modes:** backend unavailable, offline, saved state stale, stale snapshot

**Mitigations/recovery:** quiet revalidation, read-only saved state, refetch on reconnect, write actions stay disabled

## Control API boundary

FastAPI validation, side-effect-free reads, and command admission.

**Assets:** Fleet, Apps, Security, Recovery, and Release APIs, Identity, authentication, and invite guards, Prepared read, health, readiness, diagnostics, and evidence APIs, App Catalog, FastAPI /api/lite/*, Media readiness and app health probes, Remote-access readiness checks, Security scan coordinator

**Entry points:** HTTP JSON, HTTP probes, HTTPS JSON, NATS, SQLite

**Threats/failure modes:** NATS unavailable, SQLite unavailable, action blocked, command undeliverable, domain stale, duplicate device, identity mismatch, media not connected, remote unavailable, route not ready, route unavailable, scanner timeout, stale projection, worker start timeout

**Mitigations/recovery:** connect media safely, consumer recovery, explicit repair/rejoin, explicit retry, fail closed, fail writes closed, focused invalidation, reconciliation, repair, repair/check, safe disabled reason, safe startup side effects outside reads, serve last committed generation, serve safe last committed reads, terminal recovery, truthful guidance

## Durable-state boundary

SQLite canonical state, indexes, revisions, and prepared projections.

**Assets:** App, command, and workflow state, Enrollment and device lifecycle state, Invite and identity lifecycle, Audit index, projection refresh, prepared projections, and domain revisions, Backup, restore, and checkpoint state, Installed release and runtime state, Security findings and run state, SQLite control-plane store

**Entry points:** JSON, SQLite, restic metadata

**Threats/failure modes:** corruption, duplicate, health validation failure, identity mismatch, mismatch, offline, orphan command, restore blocked, scanner timeout, stale, stale accepted run, stale action, stale generation, verification failed, write contention

**Mitigations/recovery:** checkpoint, explicit confirmation, explicit repair, last-known-good rollback, maintenance, preserve enrollment, preview, rebuild affected domain, reconcile independently, rejoin/repair, revoke, serve last valid, terminal recovery, verified database restore

## External release boundary

GitHub source and immutable release assets.

**Assets:** GitHub Release, GitHub repository, Date-based Lite tag, dist.zip, checksums, and release manifest

**Entry points:** Git/HTTPS, HTTPS, JSON, SHA256, ZIP

**Threats/failure modes:** missing asset, tag or manifest mismatch, workflow failure

**Mitigations/recovery:** do not apply; publish corrected release, fix via PR, reject release

## Managed-device boundary

Joined-device PM2 agent/supervisor runtime.

**Assets:** Device command executor, Reconnect watchdog and supervisor recovery, Heartbeat, telemetry, and health publishers, Lite agent supervisor, Lite node agent

**Entry points:** Local process control, NATS, NATS when reachable

**Threats/failure modes:** agent disconnected, disconnected, identity mismatch, signal stale, stopped, supervisor absent, undeliverable

**Mitigations/recovery:** UI recovery guidance, do not fake delivery, explicit repair, explicit repair/rejoin, fresh publish after reconnect, guidance, reconnect, reconnect watchdog, retry after reconnect, supervisor restart

## Messaging and execution boundary

NATS/JetStream, workers, subprocesses, queues, and lifecycle execution.

**Assets:** App lifecycle worker, App backup, restore preview, and update lifecycle, Backup and verification engine, Bounded queues and reconciliation, Checkpoints and retention policy, Command admission and lifecycle, Completion and audit evidence, NATS / JetStream, Projection subprocesses, Download staging and release verification, Release subprocess, Restore preview and confirmed restore, Explicit retirement and database recovery, Lynis and Trivy scanner adapters, Quick, Full, and App safety checks, Worker process, Workflow execution

**Entry points:** HTTP JSON, HTTPS, IPC queue, In-process queue, JSON files, JetStream, Local scanners, Local subprocess, NATS, NATS events, SHA256, SQLite, filesystem, local process, restic

**Threats/failure modes:** checkpoint failure, consumer stale, consumer stalled, download failure, evidence write failure, health failed, healthy device removal blocked, listener unavailable, network/checksum/identity failure, operation failed, orphan state, orphaned command, partial/missing target, post-switch health failure, pressure deferral, preview unsafe, projection lag, queue pressure, redelivery, repository unavailable, restore verification failed, subprocess exit, subprocess timeout, timeout, tool unavailable, verification blocked, verification failed, verification failure

**Mitigations/recovery:** abort destructive operation, atomic rollback, bounded backoff, bounded retry, cancel, checkpoint rollback, coalesce, consumer re-enrollment, durable consumer re-enrollment, explicit retry, fail action truthfully, kill process group, non-destructive repair, preserve active release, preview first, rebuild from journal, reconcile without deleting device, reconnect, record partial state, repair repository, restart and reconcile, restart projection subprocess, retry, retry bounded write, rollback, serve last committed, terminal redelivery protection, transactional reconciliation, truthful partial state, use verified backup

## Server-host boundary

Android/Termux or Ubuntu host processes and local networking.

**Assets:** Atomic PWA promotion, Caddy same-origin proxy, Last-known-good state and rollback, Primary and secondary NATS listeners, PM2 process manager, Post-switch health validation, tailscaled daemon

**Entry points:** Filesystem atomic rename, Filesystem atomic switch, HTTP, HTTP reverse proxy, HTTPS, Local process control, NATS/TCP, SQLite, Tailscale

**Threats/failure modes:** certificate unavailable, daemon unavailable, health gate fails, listener bound incorrectly, process stopped, promotion failure, rollback failure, route unavailable

**Mitigations/recovery:** bounded PM2 restart, bounded restart, manual recovery guidance, regenerate config, regenerate validated config, retain previous active release, rollback immediately, separate supervisor, start when safe, verify connectivity

## Private network and Tailnet boundary

LAN and Tailscale private connectivity.

**Assets:** Local LAN, Tailscale remote access

**Entry points:** HTTPS, TCP/IP, WireGuard/Tailscale

**Threats/failure modes:** no Tailnet IP, tailscaled stopped

**Mitigations/recovery:** readiness guidance, safe startup
