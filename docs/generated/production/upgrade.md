---
title: "Upgrade and release verification"
description: "An upgrade is valid only when release identity, manifest, artifact checksum, staged PWA contents, and post-switch health agree."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 12b1cd5a2f8732a42027366c3bb68790b0845c8acb3a38f101acea7690ddb60b
schema_revision: 1
validation_status: generated
---

# Upgrade and release verification

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

An upgrade is valid only when release identity, manifest, artifact checksum, staged PWA contents, and post-switch health agree.

Stable healthy systems use a calm release-check cadence. Manual checks are immediate; active download/apply stages may poll faster only during transition. Auto-apply remains disabled unless explicitly configured and validated.
