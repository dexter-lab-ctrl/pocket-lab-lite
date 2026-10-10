---
title: "Security boundaries and redaction"
description: "Secrets and raw operational payloads remain backend-only."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 28ae798ffa54bf6b0ff559cdf0af283e8761ebd3562bc590a734af9b2f818837
schema_revision: 1
validation_status: generated
---

# Security boundaries and redaction

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Secrets and raw operational payloads remain backend-only.

The UI and generated artifacts exclude passwords, recovery codes, session credentials, CSRF material, hashes/verifiers, authorization headers, cookies, NATS credentials, Restic passwords, Tailscale auth keys, private keys, raw environment values, OPA input documents, scanner payloads, raw logs, and private Android paths. Human browser writes require an authenticated HttpOnly session plus CSRF header; service API-token authentication remains separate. OPA remains loopback-only and additive to FastAPI-owned hard invariants.
