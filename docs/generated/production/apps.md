---
title: "Apps and PhotoPrism"
description: "The App Catalog is a backend-owned action surface. PhotoPrism is served through the same-origin `/apps/photoprism/` route when installed and route-ready."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 6a7576a6242d285a8943d05aeb402cd27f1ee0cd4264c592d29b8dfebad04409
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
