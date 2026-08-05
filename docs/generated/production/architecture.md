---
title: "Production architecture"
description: "The deployable flow is UI \u2192 Caddy \u2192 FastAPI \u2192 SQLite/NATS \u2192 worker/agent/supervisor \u2192 sanitized events and prepared reads \u2192 UI."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 2bbbafe64ee958254b4e1d9dc2da05a18d5a6c2310f065d9666f22ad2a7569b4
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
