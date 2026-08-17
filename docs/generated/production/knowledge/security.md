---
title: "Security model"
description: "Trust boundaries, fail-closed controls, and safe recovery guidance."
generated: true
audience: knowledgebase
confidence: generated
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 3
---

# Security model

| Boundary | Assets | Entry points | Confidence |
| --- | --- | --- | --- |
| Application-container boundary | PhotoPrism, PROot Ubuntu application container | HTTP behind Caddy, Local process / HTTP | inferred |
| Browser trust boundary | Browser, Frontend state ownership, React / Vite PWA, User | Fetch API, HTTPS, HTTPS JSON, IndexedDB | inferred |
| Control API boundary | Fleet, Apps, Security, Recovery, and Release APIs, Identity, authentication, and invite guards, Prepared read, health, readiness, diagnostics, and evidence APIs, App Catalog, FastAPI /api/lite/*, Media readiness and app health probes, OPA Safety Rules policy engine, Remote-access readiness checks, Security scan coordinator | HTTP JSON, HTTP probes, HTTPS JSON, Loopback HTTP JSON, NATS, Rego, SQLite | inferred |
| Durable-state boundary | App, command, and workflow state, Enrollment and device lifecycle state, Invite and identity lifecycle, Audit index, projection refresh, prepared projections, and domain revisions, Backup, restore, and checkpoint state, Installed release and runtime state, Security findings and run state, SQLite control-plane store | JSON, SQLite, restic metadata | inferred |
| External release boundary | GitHub Release, GitHub repository, Date-based Lite tag, dist.zip, checksums, and release manifest | Git/HTTPS, HTTPS, JSON, SHA256, ZIP | inferred |
| Managed-device boundary | Device command executor, Reconnect watchdog and supervisor recovery, Heartbeat, telemetry, and health publishers, Lite agent supervisor, Lite node agent | Local process control, NATS, NATS when reachable | inferred |
| Messaging and execution boundary | App lifecycle worker, App backup, restore preview, and update lifecycle, Backup and verification engine, Bounded queues and reconciliation, Checkpoints and retention policy, Command admission and lifecycle, Completion and audit evidence, NATS / JetStream, Projection subprocesses, Download staging and release verification, Release subprocess, Restore preview and confirmed restore, Explicit retirement and database recovery, Lynis and Trivy scanner adapters, Quick, Full, and App safety checks, Worker process, Workflow execution | HTTP JSON, HTTPS, IPC queue, In-process queue, JSON files, JetStream, Local scanners, Local subprocess, NATS, NATS events, SHA256, SQLite, filesystem, local process, restic | inferred |
| Server-host boundary | Atomic PWA promotion, Caddy same-origin proxy, Last-known-good state and rollback, Primary and secondary NATS listeners, PM2 process manager, Post-switch health validation, tailscaled daemon | Filesystem atomic rename, Filesystem atomic switch, HTTP, HTTP reverse proxy, HTTPS, Local process control, NATS/TCP, SQLite, Tailscale | inferred |
| Private network and Tailnet boundary | Local LAN, Tailscale remote access | HTTPS, TCP/IP, WireGuard/Tailscale | inferred |
