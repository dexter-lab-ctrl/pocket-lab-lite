---
title: "Caddy and same-origin access"
description: "Caddy serves the PWA and proxies `/api/lite/*`; app routes such as `/apps/photoprism/*` remain backend-owned and are excluded from PWA fallback capture."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 3ffdc3e01fe1268519d71f92deb29a6e89cd71a0487664cb7778b66c72cd9093
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
