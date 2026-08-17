---
title: "Lite HTTP API contract"
description: "Canonical FastAPI Lite OpenAPI contract and validation summary."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_contracts.py
source_fingerprint: 9adfc958872933f6b5895d1b0052e6c60357c275131e60df9a64d934db0403fb
schema_revision: 1
validation_status: generated
---

# Lite HTTP API contract

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

FastAPI OpenAPI is the canonical HTTP contract. This generated Lite view contains **124 paths** and **126 operations**.

- Source: `pocket-lab-final-structure/runtime/api_fastapi/main.py`
- Contract: `contracts/generated/lite-openapi.json`
- Validation: Redocly plus frontend route usage comparison

Write actions remain FastAPI-owned. Browser tests do not invoke internal Python services directly.
