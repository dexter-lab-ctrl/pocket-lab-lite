---
title: "Remote access"
description: "Tailscale and Caddy provide private same-origin access where configured. The Devices tab shows Tailscale IP only when readiness is verified."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: c940b617cd72278517206ef10ec0b2bcb0800478260b7db3c064f340ceb3f98a
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
