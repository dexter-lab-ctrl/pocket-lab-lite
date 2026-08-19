---
title: "Android and Termux runtime verification"
description: "Sanitized promoted evidence for the Pocket Lab Lite Android/Termux server runtime."
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

# Android and Termux runtime verification

**Current classification:** Promoted runtime verified.

The canonical architecture remains authoritative for what Pocket Lab Lite is designed to contain. Promoted runtime evidence verifies current claims when available; an unavailable phone does not imply that a canonical component is missing.

## Platform

| Field | Classification |
| --- | --- |
| Platform | android-termux |
| Android release | 16 |
| Architecture | arm64 |
| ABI | other |
| Termux prefix | termux |

## Runtime services

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

## SQLite runtime metadata

| Role | Presence | Integrity | Journal | Expected tables | Schema revision |
| --- | --- | --- | --- | --- | --- |
| control-plane-state | present | ok | wal | yes | 24 |

## Agent and supervisor relationship

| Agent | Supervisor | Command owner | NATS | Recovery | Evidence freshness |
| --- | --- | --- | --- | --- | --- |
| present | present | present | ready | supervised | unknown |

No hostname, username, private address, Tailnet name, certificate path, PID, exact memory, uptime, restart timestamp, database row, media filename, or user path is retained in this page.
