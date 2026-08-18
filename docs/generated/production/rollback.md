---
title: "Release rollback"
description: "Rollback returns to a previously verified PWA artifact and last-known-good identity."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 9a3315bec7d9d8bab7eca1653eedcac05ea544ed0bb81a797678b6fd8ee790b8
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
