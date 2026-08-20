---
title: "Release rollback"
description: "Rollback returns to a previously verified PWA artifact and last-known-good identity."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 4c506f3c2d7eb0f19e0dc657293a3905cafc1cf98b6dc043ee40e1e881280a7a
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
