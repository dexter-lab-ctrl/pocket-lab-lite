---
title: "Health and diagnostics"
description: "Start with safe reads and prepared diagnostics."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: af565ccf20cd7261b44f75f6f59dd4f775f699a95ff7aff70b15c7f81e5ddad3
schema_revision: 1
validation_status: generated
---

# Health and diagnostics

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Start with safe reads and prepared diagnostics.

Expected entry points include `/health`, `/ready`, `/api/lite/status`, and domain-specific Lite reads. Verify SQLite quick-check/parity, projection freshness/revisions, NATS durable-consumer health, PM2 state, Tailnet reachability, and recent sanitized evidence before recovery action.
