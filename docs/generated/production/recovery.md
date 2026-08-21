---
title: "Backup and restore"
description: "Recovery is backend/worker-owned. The UI can request a backup, verification, restore preview, and confirmed restore only through supported FastAPI endpoints."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 8b7e457bdeb6cbdf9bf6dc80faa75c6bbcbe4b1a448ea3d2c75c39d81a65f0a0
schema_revision: 1
validation_status: generated
---

# Backup and restore

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Recovery is backend/worker-owned. The UI can request a backup, verification, restore preview, and confirmed restore only through supported FastAPI endpoints.

Restore requires explicit confirmation, a pre-restore checkpoint, and post-restore health validation. Saved-state display never fakes action success.
