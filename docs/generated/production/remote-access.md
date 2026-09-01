---
title: "Remote access"
description: "Tailscale and Caddy provide private same-origin access where configured. The Devices tab shows Tailscale IP only when readiness is verified."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 4a1f2cf64180dfd6a19c437f4770e4192db9cf7eb5347417c9f7a401837e2b8f
schema_revision: 1
validation_status: generated
---

# Remote access

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Tailscale and Caddy provide private same-origin access where configured. The Devices tab shows Tailscale IP only when readiness is verified.

When unavailable, the product says **Remote access not ready**. Startup scripts may safely start `tailscaled`; read APIs remain side-effect free.
