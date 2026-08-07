---
title: "SQLite and prepared projections"
description: "SQLite store modules are the source for durable enrollment, Security, Recovery, command lifecycle, and prepared read behavior."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 90334d8a3104e0f77f0483b172adda04240e1bcab143ad5e7a91944c1ed9acdf
schema_revision: 1
validation_status: generated
---

# SQLite and prepared projections

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

SQLite store modules are the source for durable enrollment, Security, Recovery, command lifecycle, and prepared read behavior.

## Store and migration sources

- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_control_plane_store.py`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_restore_transaction.py`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_security_store.py`
- `pocket-lab-final-structure/runtime/api_fastapi/services/runtime_snapshot_store.py`

Prepared projection documentation must distinguish scheduler generation, committed generation, canonical hash, freshness, read degradation, and cache state.
