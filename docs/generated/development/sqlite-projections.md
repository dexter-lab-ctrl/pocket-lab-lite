---
title: "SQLite and prepared projections"
description: "SQLite store modules are the source for durable enrollment, Security, Recovery, command lifecycle, and prepared read behavior."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: ae852e970e2385b9f84509e4a446d978365eb0e16ee80c312f96ab8f18ee8983
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
