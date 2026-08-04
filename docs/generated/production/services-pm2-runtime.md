---
title: "Services and PM2 runtime verification"
description: "Sanitized process-presence and ownership evidence for Pocket Lab Lite services."
audience: production
status: verified
generated: true
generated_at: uncommitted
source_commit: uncommitted
generator: scripts/docs/runtime/generate_termux_runtime_docs.py
generator_version: 1
schema_revision: 1
validation_status: verified
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source-derived</span><span class="pl-status pl-status--verified">Verified</span></div>

# Services and PM2 runtime verification

**Current classification:** Promoted runtime verified.

PM2 evidence is normalized to logical role, presence, status, runtime type, execution owner, restart bucket, memory bucket, and repository expectation match. Full command lines and PM2 environments are never retained.

| Role | Presence | Status | Runtime | Source match |
| --- | --- | --- | --- | --- |
| same-origin proxy | present | healthy | native | matched |
| server-host recovery supervisor | present | online | python | matched |
| FastAPI control API | present | online | python | matched |
| NATS/JetStream service | present | ready | native | matched |
| server-host node agent | present | online | python | matched |
| managed PhotoPrism application | present | online | proot | matched |
| Termux process manager | present | ready | node | matched |
| PROot Ubuntu application runtime | missing | unavailable | proot | not-evaluated |
| SQLite control-plane store | present | healthy | sqlite | matched |
| private remote-access daemon | present | ready | native | matched |
| worker execution plane | present | online | python | matched |

A stopped, disconnected, repairing, and unavailable service are distinct states. Runtime evidence does not authorize automatic restart or repair from documentation tooling.
