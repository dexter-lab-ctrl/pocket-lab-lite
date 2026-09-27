---
title: "Data retention"
description: "Enrollment, audit, backup, Security, and lifecycle history are retained independently from live connectivity."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 5992c183196fe0257c8a73df7fae017870c4d211d46403777e6023c288dacb94
schema_revision: 1
validation_status: generated
---

# Data retention

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Enrollment, audit, backup, Security, and lifecycle history are retained independently from live connectivity.

Offline devices are not deleted implicitly. Command cleanup cannot remove enrollment. Removal/retirement is explicit, transactional, dependency-aware, and preserves historical audit records. Bounded generated validation evidence follows user retention policy and never enters `dist.zip`.
