---
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 8937f6e2e2ba4f68e0af975279bf8bf383342aff03d7c9c0e4a5c4a564aea291
schema_revision: 1
validation_status: generated
---

# Health and diagnostics

Start with safe reads and prepared diagnostics.

Expected entry points include `/health`, `/ready`, `/api/lite/status`, and domain-specific Lite reads. Verify SQLite quick-check/parity, projection freshness/revisions, NATS durable-consumer health, PM2 state, Tailnet reachability, and recent sanitized evidence before recovery action.
