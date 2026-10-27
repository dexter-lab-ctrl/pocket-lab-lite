---
title: "Data retention"
description: "Enrollment, audit, backup, Security, and lifecycle history are retained independently from live connectivity."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 23b69816f224abebd5033f1a1e65e29e081d47691fcc87be78787af7e5e997ce
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
