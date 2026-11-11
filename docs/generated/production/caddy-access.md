---
title: "Caddy and same-origin access"
description: "Caddy serves the PWA and proxies `/api/lite/*`; app routes such as `/apps/photoprism/*` remain backend-owned and are excluded from PWA fallback capture."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 1870175a68c3624378abf9f8e4a9ead4526a85a8cbaf13460ff90d7f36f45ed0
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
