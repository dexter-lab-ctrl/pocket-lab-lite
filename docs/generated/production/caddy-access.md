---
title: "Caddy and same-origin access"
description: "Caddy serves the PWA and proxies `/api/lite/*`; app routes such as `/apps/photoprism/*` remain backend-owned and are excluded from PWA fallback capture."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: f61f73bdd4e5dc12db478eb6c36644e7da72b6f6dfce6a0327c36cd4f34e8ca0
schema_revision: 1
validation_status: generated
---

# Caddy and same-origin access

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Caddy serves the PWA and proxies `/api/lite/*`; app routes such as `/apps/photoprism/*` remain backend-owned and are excluded from PWA fallback capture.

Tailscale HTTPS uses verified Tailnet readiness and protected certificate material. Certificates, private keys, FQDN-specific secrets, and runtime values are never emitted by generated documentation.
