---
title: "Security boundaries and redaction"
description: "Secrets and raw operational payloads remain backend-only."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 21981d056df577fc1d8994fd3a680e6643534a8727b24624b2ea1f0b2e5f9924
schema_revision: 1
validation_status: generated
---

# Security boundaries and redaction

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Secrets and raw operational payloads remain backend-only.

The UI and generated artifacts exclude passwords, tokens, authorization headers, cookies, NATS credentials, Restic passwords, Tailscale auth keys, private keys, raw environment values, scanner payloads, raw logs, and private Android paths.
