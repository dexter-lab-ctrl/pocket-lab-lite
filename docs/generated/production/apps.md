---
title: "Apps and PhotoPrism"
description: "The App Catalog is a backend-owned action surface. PhotoPrism is served through the same-origin `/apps/photoprism/` route when installed and route-ready."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 8f8afc8abd2efd3a6fa02fae02e6d916c7afea569468f48225b6a7f96ab99c4e
schema_revision: 1
validation_status: generated
---

# Apps and PhotoPrism

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

The App Catalog is a backend-owned action surface. PhotoPrism is served through the same-origin `/apps/photoprism/` route when installed and route-ready.

The UI may open the route and request supported actions through FastAPI. It does not run PhotoPrism, PM2, Caddy, storage, backup, repair, or scanner commands directly.
