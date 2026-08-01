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

# Security boundaries and redaction

Secrets and raw operational payloads remain backend-only.

The UI and generated artifacts exclude passwords, tokens, authorization headers, cookies, NATS credentials, Restic passwords, Tailscale auth keys, private keys, raw environment values, scanner payloads, raw logs, and private Android paths.
