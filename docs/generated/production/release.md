---
title: "Release and dist.zip"
description: "Pocket Lab Lite releases use a date-based annotated tag and a GitHub release containing `dist.zip`, `checksums.txt`, and the release manifest."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: a0834a8d08afe99a140586199c30eed89f80a6d951db32da01858a6b9fb4ae35
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
