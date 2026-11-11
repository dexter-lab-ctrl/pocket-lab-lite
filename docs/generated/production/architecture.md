---
title: "Production architecture"
description: "The deployable flow is UI \u2192 Caddy \u2192 FastAPI \u2192 SQLite/NATS \u2192 worker/agent/supervisor \u2192 sanitized events and prepared reads \u2192 UI."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 37ee89db14b20c26cd201355869f9c32507333d2f2e95bb7c5c3b46d63b6045d
schema_revision: 1
validation_status: generated
---

# Production architecture

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

The deployable flow is UI → Caddy → FastAPI → SQLite/NATS → worker/agent/supervisor → sanitized events and prepared reads → UI.

The frontend never talks directly to NATS, executes shell commands, or stores backend secrets. FastAPI is the control API. Agents and supervisors own execution and recovery.
