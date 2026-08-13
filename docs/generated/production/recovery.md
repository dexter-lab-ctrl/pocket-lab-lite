---
title: "Backup and restore"
description: "Recovery is backend/worker-owned. The UI can request a backup, verification, restore preview, and confirmed restore only through supported FastAPI endpoints."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 28df171b72ff9344d9df00174a5d4f81aa4721fec284b226bb68c5c2c1d12a39
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
