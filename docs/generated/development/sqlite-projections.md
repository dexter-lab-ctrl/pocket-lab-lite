---
title: "SQLite and prepared projections"
description: "SQLite store modules are the source for durable enrollment, Security, Recovery, command lifecycle, and prepared read behavior."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 9f8a72eccd6819f89b97d0c2042b1e8fd19666bff325a7f4c4e5e0585788267c
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
