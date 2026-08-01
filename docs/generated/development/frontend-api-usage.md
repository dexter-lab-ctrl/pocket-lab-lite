---
title: "Frontend API usage"
description: "Frontend Lite route usage compared with the generated FastAPI contract."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_contracts.py
source_fingerprint: 726211e0090a05fc2beefe776d8ca40541097700e3dd99a2af1cf1e5ed1914fa
schema_revision: 1
validation_status: generated
---

# Frontend API usage

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

## Unsupported frontend route references
- None

## Backend Lite routes with no detected frontend consumer
- `/api/lite/catalog/remove`
- `/api/lite/diagnostics/runtime/full`
- `/api/lite/fleet/agent/bootstrap-blocked`
- `/api/lite/fleet/agent/bootstrap.env`
- `/api/lite/fleet/agent/bootstrap.sh`
- `/api/lite/fleet/invites/latest`
- `/api/lite/recovery/apps/{app_id}/backup`
- `/api/lite/recovery/apps/{app_id}/backup-to-target`
- `/api/lite/recovery/apps/{app_id}/restore/preview`
- `/api/lite/recovery/restore/checkpoints/{checkpoint_id}`
- `/api/lite/recovery/restore/runs/{restore_id}`
- `/api/lite/security/evidence/{run_id}`
- `/api/lite/security/scan`

The second list is informational: worker callbacks, diagnostics, compatibility aliases, and user-only endpoints may intentionally have no normal UI consumer.
