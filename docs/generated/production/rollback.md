---
title: "Release rollback"
description: "Rollback returns to a previously verified PWA artifact and last-known-good identity."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 1f7558299edb6b35ba0042c78d5e818f2a4c4cdfcafd785a0c9e510bff3808bc
schema_revision: 1
validation_status: generated
---

# Release rollback

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Rollback returns to a previously verified PWA artifact and last-known-good identity.

Do not overwrite evidence. Restore the prior staged artifact atomically, restart only the serving layer that requires it, then verify Caddy, `/health`, `/ready`, release identity, service worker state, and device/app reads.
