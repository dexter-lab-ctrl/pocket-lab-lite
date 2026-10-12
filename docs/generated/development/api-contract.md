---
title: "Lite HTTP API contract"
description: "Canonical FastAPI Lite OpenAPI contract and validation summary."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_contracts.py
source_fingerprint: 6be22d148a6ecc9769efe6ce22cf3fde158293fa2b83a67c839a387e1cfc768f
schema_revision: 1
validation_status: generated
---

# Lite HTTP API contract

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

FastAPI OpenAPI is the canonical HTTP contract. This generated Lite view contains **221 paths** and **234 operations**.

- Source: `pocket-lab-final-structure/runtime/api_fastapi/main.py`
- Contract: `contracts/generated/lite-openapi.json`
- Validation: Redocly plus frontend route usage comparison

Write actions remain FastAPI-owned. Browser tests do not invoke internal Python services directly.
