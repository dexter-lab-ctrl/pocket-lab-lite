---
title: "Health and diagnostics"
description: "Start with safe reads and prepared diagnostics."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: d2c746aef06578690fde91eed58cee472bf9824cb8897cea21662a62a0f1fb12
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
