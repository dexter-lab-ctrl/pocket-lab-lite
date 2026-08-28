---
title: "Remote access"
description: "Tailscale and Caddy provide private same-origin access where configured. The Devices tab shows Tailscale IP only when readiness is verified."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: ae852e970e2385b9f84509e4a446d978365eb0e16ee80c312f96ab8f18ee8983
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
