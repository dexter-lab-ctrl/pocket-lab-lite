---
title: "Release and dist.zip"
description: "Pocket Lab Lite releases use a date-based annotated tag and a GitHub release containing `dist.zip`, `checksums.txt`, and the release manifest."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 22be0323e9adc84aeefc0bd4704652d1a5b940b78124b0faf8cd6ef78b6a5bfb
schema_revision: 1
validation_status: generated
---

# Release and dist.zip

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Pocket Lab Lite releases use a date-based annotated tag and a GitHub release containing `dist.zip`, `checksums.txt`, and the release manifest.

The PWA artifact is promoted atomically and validated after switch. Development documentation/tooling is not included in `dist.zip`.
